"""Daily sales / orders / quantity models, time-ordered cross-validation and selection.

Candidates
  weekday_index    existing production baseline (weekday index x recent level), horizon-aware
  weekday_mean_8w  mean of the same weekday over the last 8 weeks
  glm_cal / glm_cal_temp / glm_schools / glm_schools_temp   Poisson GLM on calendar (+ temperature)
  hgb_cal          gradient boosting (Poisson loss) on calendar features
  prophet_cal / prophet_cal_temp   Prophet (weekly seasonality, holidays, regressors)

Validation: expanding window, monthly blocks, train = strictly earlier dates only.
Precipitation is never a model input. Weather input in CV is the training-layer temperature
(observed), i.e. an optimistic 'perfect forecast' assumption.
"""
import logging
from collections import defaultdict
from datetime import timedelta
from statistics import mean

import numpy as np
import pandas as pd

from sales.services.forecasting import (
    INDEX_WINDOW_DAYS, LEVEL_WINDOW_DAYS, MIN_INDEX_OBSERVATIONS, MIN_LEVEL_OBSERVATIONS, InsufficientHistory,
)

MODEL_VERSION = "v2"
MIN_TRAIN_DAYS = 120
BASE_COLS = ["weekday", "hol", "long_break", "pre_long_break", "post_long_break"]
FEATURE_SETS = {
    "cal": BASE_COLS + ["exam_any", "vacation_any"],
    "schools": BASE_COLS + ["hanyang_exam", "hywoman_exam", "hs_exam",
                            "hanyang_vacation", "hywoman_vacation", "hs_vacation"],
}
TEMP_COL = "temp_avg"
BINARY_EXCLUDE = {"weekday"}
# name -> (kind, feature set, uses temperature)
SPECS = {
    "weekday_index": ("weekday_index", None, False),
    "weekday_mean_8w": ("weekday_mean", None, False),
    "glm_cal": ("glm", "cal", False),
    "glm_cal_temp": ("glm", "cal", True),
    "glm_schools": ("glm", "schools", False),
    "glm_schools_temp": ("glm", "schools", True),
    "hgb_cal": ("hgb", "cal", False),
    "prophet_cal": ("prophet", "cal", False),
    "prophet_cal_temp": ("prophet", "cal", True),
}
SIMPLICITY = list(SPECS)  # earlier = simpler; used to break near-ties
NO_TEMP_FALLBACK = {"glm_cal_temp": "glm_cal", "glm_schools_temp": "glm_schools", "prophet_cal_temp": "prophet_cal"}
TIE_TOLERANCE_PP = 0.10
TARGETS = ("sales", "orders", "quantity")


def feature_columns(model_name):
    kind, fset, temp = SPECS[model_name]
    if fset is None:
        return []
    return FEATURE_SETS[fset] + ([TEMP_COL] if temp else [])


def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    total = y.sum()
    err = p - y
    return {
        "n": int(len(y)),
        "mae": float(np.abs(err).mean()) if len(y) else None,
        "rmse": float(np.sqrt((err ** 2).mean())) if len(y) else None,
        # WAPE uses the sum of actuals, so zero-valued days are handled; None when all actuals are 0.
        "wape_pct": float(np.abs(err).sum() / total * 100) if total > 0 else None,
        "bias_pct": float(err.sum() / total * 100) if total > 0 else None,
        "zero_actual_days": int((y == 0).sum()),
    }


# ---------------------------------------------------------------- individual models
def weekday_index_forecast(train, target_col, targets, as_of):
    """The existing production formula, but with the level taken at `as_of` for any horizon."""
    series = {d.date(): float(v) for d, v in train[target_col].items() if d.date() <= as_of}
    index_start = as_of - timedelta(days=INDEX_WINDOW_DAYS)
    hist = [(d, v) for d, v in series.items() if index_start < d <= as_of]
    if len(hist) < MIN_INDEX_OBSERVATIONS:
        raise InsufficientHistory(f"history too short: {len(hist)} days")
    by_wd = defaultdict(list)
    for d, v in hist:
        by_wd[d.weekday()].append(v)
    wd_mean = {k: mean(v) for k, v in by_wd.items()}
    overall = mean(wd_mean.values())
    if overall <= 0:
        raise InsufficientHistory("all-zero history")
    idx = {k: m / overall for k, m in wd_mean.items()}
    recent = [(d, v) for d, v in hist if d > as_of - timedelta(days=LEVEL_WINDOW_DAYS) and idx.get(d.weekday(), 0) > 0]
    if len(recent) < MIN_LEVEL_OBSERVATIONS:
        raise InsufficientHistory("too few recent days")
    level = mean(v / idx[d.weekday()] for d, v in recent)
    return np.array([max(level * idx.get(t.weekday(), 1.0), 0.0) for t in targets])


def weekday_mean_forecast(train, target_col, targets, weeks=8):
    recent = train[train.index > train.index.max() - timedelta(days=weeks * 7)]
    if len(recent) < 14:
        raise InsufficientHistory("history too short for weekday mean")
    m = recent.groupby(recent.index.weekday)[target_col].mean()
    overall = float(recent[target_col].mean())
    return np.array([float(m.get(t.weekday(), overall)) for t in targets])


def _make_glm(cols):
    from sklearn.compose import ColumnTransformer
    from sklearn.linear_model import PoissonRegressor
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

    binary = [c for c in cols if c not in BINARY_EXCLUDE and c != TEMP_COL]
    parts = [("wd", OneHotEncoder(handle_unknown="ignore", drop="first"), ["weekday"])]
    if binary:
        parts.append(("bin", "passthrough", binary))
    if TEMP_COL in cols:
        parts.append(("temp", make_pipeline(StandardScaler(),
                                            SplineTransformer(n_knots=4, degree=2, extrapolation="linear")), [TEMP_COL]))
    return make_pipeline(ColumnTransformer(parts), PoissonRegressor(alpha=1e-3, max_iter=3000))


def _fit_predict_sklearn(kind, cols, train, test, target_col):
    tr = train.dropna(subset=cols)
    if len(tr) < MIN_TRAIN_DAYS:
        raise InsufficientHistory("too few complete training rows")
    if test[cols].isna().any().any():
        raise InsufficientHistory("missing model inputs for the target dates")
    if kind == "glm":
        model = _make_glm(cols)
    else:
        from sklearn.ensemble import HistGradientBoostingRegressor
        model = HistGradientBoostingRegressor(loss="poisson", max_depth=3, learning_rate=0.05, max_iter=200,
                                              min_samples_leaf=15, random_state=0)
    model.fit(tr[cols], tr[target_col])
    return np.clip(model.predict(test[cols]), 0, None)


def _prophet_fit_predict(cols, train, test, target_col):
    from prophet import Prophet

    logging.getLogger("cmdstanpy").setLevel(logging.WARNING)
    logging.getLogger("prophet").setLevel(logging.WARNING)
    regs = [c for c in cols if c not in ("weekday", "hol")]
    tr = train.dropna(subset=regs)
    if len(tr) < MIN_TRAIN_DAYS:
        raise InsufficientHistory("too few complete training rows")
    if test[regs].isna().any().any():
        raise InsufficientHistory("missing model inputs for the target dates")
    all_days = pd.concat([train, test])
    holidays = pd.DataFrame({"holiday": "public_holiday", "ds": all_days.index[all_days["hol"] == 1]})
    m = Prophet(weekly_seasonality=True, yearly_seasonality=False, daily_seasonality=False,
                uncertainty_samples=0, holidays=holidays if len(holidays) else None)
    for r in regs:
        m.add_regressor(r)
    fit_df = pd.DataFrame({"ds": tr.index, "y": tr[target_col].astype(float).values})
    for r in regs:
        fit_df[r] = tr[r].astype(float).values
    m.fit(fit_df)
    fut = pd.DataFrame({"ds": test.index})
    for r in regs:
        fut[r] = test[r].astype(float).values
    return np.clip(m.predict(fut)["yhat"].values, 0, None)


def fit_predict(model_name, train, test, target_col):
    """Fit on `train` (strictly earlier dates) and predict the rows of `test`."""
    if train.index.max() >= test.index.min():
        raise ValueError("training data must end before the first target date")
    kind, _, _ = SPECS[model_name]
    cols = feature_columns(model_name)
    if kind == "weekday_index":
        return weekday_index_forecast(train, target_col, list(test.index), train.index.max().date())
    if kind == "weekday_mean":
        return weekday_mean_forecast(train, target_col, list(test.index))
    if kind == "prophet":
        return _prophet_fit_predict(cols, train, test, target_col)
    return _fit_predict_sklearn(kind, cols, train, test, target_col)


def predict_with_fallback(model_name, train, test, target_col):
    """-> (predictions, per-row model used, notes). Falls back to simpler models, never raises
    unless even the weekday baselines cannot be computed (InsufficientHistory)."""
    notes = []
    chain = [model_name]
    if model_name in NO_TEMP_FALLBACK:
        chain.append(NO_TEMP_FALLBACK[model_name])
    chain += [m for m in ("weekday_index", "weekday_mean_8w") if m not in chain]
    for name in chain:
        try:
            pred = fit_predict(name, train, test, target_col)
            if name != model_name:
                notes.append(f"{model_name} 사용 불가 → {name}으로 대체")
            return pred, [name] * len(test), notes
        except Exception as exc:  # noqa: BLE001 - any training failure falls through to a simpler model
            notes.append(f"{name} 실패: {type(exc).__name__}")
            last = exc
    raise InsufficientHistory(f"모든 모델이 실패했습니다: {last}")


# ---------------------------------------------------------------- cross-validation
def month_folds(index, first_test):
    """Monthly [start, end] blocks from first_test to the end of the data."""
    folds, s, last = [], pd.Timestamp(first_test), index.max()
    while s <= last:
        e = min(s + pd.offsets.MonthEnd(0), last)
        folds.append((s, e))
        s = e + pd.Timedelta(days=1)
    return folds


def default_first_test(index):
    """First day of the first month starting at least ~11 months after the data begins."""
    start = pd.Timestamp(index.min()) + pd.Timedelta(days=330)
    if start.day == 1:
        return start.normalize()
    return (start.to_period("M") + 1).to_timestamp()


def rolling_cv(df, target_col, model_names, first_test=None):
    """-> predictions DataFrame (date, fold, model, y, pred, fallback)."""
    first_test = first_test or default_first_test(df.index)
    rows = []
    # When weather and non-weather candidates are compared together, score every
    # candidate on the same dates with observed temperature. This prevents a
    # single missing temperature from turning an entire month into fallback rows
    # and keeps the WAPE comparison paired and fair.
    compare_weather = any(SPECS.get(name, (None, None, False))[2] for name in model_names)
    for fold_no, (s, e) in enumerate(month_folds(df.index, first_test)):
        train = df[df.index < s]
        test = df[(df.index >= s) & (df.index <= e)]
        if len(train) < MIN_TRAIN_DAYS or test.empty:
            continue
        assert train.index.max() < test.index.min(), "leakage: training overlaps the validation block"
        eval_test = test
        if compare_weather:
            if TEMP_COL not in test.columns:
                continue
            eval_test = test.dropna(subset=[TEMP_COL])
        if eval_test.empty:
            continue
        for name in model_names:
            fallback = False
            try:
                pred = fit_predict(name, train, eval_test, target_col)
            except Exception:  # noqa: BLE001
                fallback = True
                try:
                    pred = weekday_mean_forecast(train, target_col, list(eval_test.index))
                except Exception:  # noqa: BLE001
                    continue
            for d, y, p in zip(eval_test.index, eval_test[target_col].values, pred):
                rows.append({"date": d, "fold": fold_no, "model": name, "y": float(y), "pred": float(p),
                             "fallback": fallback})
    return pd.DataFrame(rows, columns=["date", "fold", "model", "y", "pred", "fallback"])


def summarize_cv(preds):
    """Overall + by-weekday + by-month metric tables from CV predictions."""
    overall, by_wd, by_month = [], [], []
    for name, g in preds.groupby("model"):
        overall.append({"model": name, "fallback_rows": int(g.fallback.sum()), **metrics(g.y, g.pred)})
        for wd, h in g.groupby(g.date.dt.weekday):
            by_wd.append({"model": name, "weekday": int(wd), **metrics(h.y, h.pred)})
        for mo, h in g.groupby(g.date.dt.to_period("M").astype(str)):
            by_month.append({"model": name, "month": mo, **metrics(h.y, h.pred)})
    return pd.DataFrame(overall), pd.DataFrame(by_wd), pd.DataFrame(by_month)


def select_model(overall: pd.DataFrame):
    """Lowest WAPE among models that never needed a CV fallback; near-ties go to the simpler model."""
    ok = overall[(overall.fallback_rows == 0) & overall.wape_pct.notna()]
    if ok.empty:
        return "weekday_index" if "weekday_index" in set(overall.model) else None
    best = ok.wape_pct.min()
    near = ok[ok.wape_pct <= best + TIE_TOLERANCE_PP]
    return sorted(near.model, key=SIMPLICITY.index)[0]


def interval_ratios(preds, model_name, q=(0.10, 0.90)):
    """Empirical 80% range of actual/predicted ratios from CV (None when too few samples)."""
    g = preds[(preds.model == model_name) & (preds.pred > 0)]
    if len(g) < 30:
        return None
    r = (g.y / g.pred).to_numpy()
    lo, hi = np.quantile(r, q)
    return {"low_ratio": float(lo), "high_ratio": float(hi), "samples": int(len(r)), "coverage_nominal": 0.8}
