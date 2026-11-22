"""Does ASOS 108 temperature help forecast 404dabang (SYNTHETIC) sales?  Read-only on inputs.

Run:  python -I weather_sales_analysis.py     (writes only into this folder, never overwrites inputs)
Libraries: pandas, numpy, scipy, scikit-learn (already installed; nothing new introduced).
"""
import json, warnings
from pathlib import Path
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, PoissonRegressor
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder, SplineTransformer, StandardScaler

warnings.filterwarnings("ignore")
OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[1]
SALES = ROOT / "data/synthetic_sales/sales_dummy_v1_final"
rng = np.random.default_rng(20261117)
LOG = {}

# ------------------------------------------------------------------ 1. load & join
W = pd.read_csv(ROOT / "data/weather/404dabang_asos_daily_weather.csv", encoding="utf-8-sig", parse_dates=["date"])
F = pd.read_csv(ROOT / "data/processed/404dabang_daily_features.csv", encoding="utf-8-sig", parse_dates=["date"])
DS = pd.read_csv(SALES / "daily_sales.csv", encoding="utf-8-sig", parse_dates=["sales_date"]).rename(columns={"sales_date": "date"})
DM = pd.read_csv(SALES / "daily_menu_sales.csv", encoding="utf-8-sig", parse_dates=["sales_date"]).rename(columns={"sales_date": "date"})

assert W.date.is_unique and F.date.is_unique and DS.date.is_unique
assert (F.avg_temp_c.values == W.avg_temp_c.values).all() and (F.max_temp_c.values == W.max_temp_c.values).all() \
    and (F.min_temp_c.values == W.min_temp_c.values).all(), "features file temps differ from weather CSV"
_chk = DS.merge(F[["date", "is_public_holiday"]], on="date", suffixes=("_ds", "_f"))
assert (_chk.is_public_holiday_ds.astype(bool) == _chk.is_public_holiday_f.astype(bool)).all(), "holiday flag differs between sales and features"
D = DS.drop(columns=["is_public_holiday"]).merge(F, on="date", how="inner", validate="1:1")
LOG["join"] = {"daily_sales_rows": len(DS), "features_rows": len(F), "weather_rows": len(W), "joined_rows": len(D),
               "date_min": str(D.date.min().date()), "date_max": str(D.date.max().date()),
               "temp_nulls": {c: int(D[c].isna().sum()) for c in ("avg_temp_c", "max_temp_c", "min_temp_c")},
               "precip_nulls": int(D.precipitation_mm.isna().sum()), "menu_rows": len(DM), "menus": int(DM.menu_id.nunique())}

# ------------------------------------------------------------------ calendar features (known in advance)
D = D.sort_values("date").reset_index(drop=True)
D["weekday"] = D.date.dt.weekday
D["month"] = D.date.dt.month
D["hol"] = D.is_public_holiday.astype(int)
nonwork = ((D.weekday >= 5) | (D.hol == 1)).astype(int).values
run = np.zeros(len(D), int)
i = 0
while i < len(D):
    if nonwork[i]:
        j = i
        while j < len(D) and nonwork[j]:
            j += 1
        run[i:j] = j - i
        i = j
    else:
        i += 1
D["long_break"] = (run >= 3).astype(int)
D["pre_long_break"] = [int(k + 1 < len(D) and run[k + 1] >= 3 and not nonwork[k]) for k in range(len(D))]
# schedule flags: NaN means "not confirmed" -> only positive confirmations are used, never treated as confirmed-absent
D["exam_confirmed"] = ((D.hanyang_exam == 1) | (D.hywoman_exam == 1) | (D.highschool_exam == 1)).astype(int)
D["vacation_confirmed"] = (D.vacation_any == 1).astype(int)
D["temp_range"] = D.max_temp_c - D.min_temp_c
CAL = ["weekday", "hol", "long_break", "pre_long_break", "exam_confirmed", "vacation_confirmed"]
CAL_M = CAL + ["month"]
T1 = ["avg_temp_c"]
T3 = ["avg_temp_c", "max_temp_c", "min_temp_c"]

# menu panel
MENUS = DM[["menu_id", "menu_name", "category", "temperature_class"]].drop_duplicates().sort_values("menu_id")
P = DM.merge(D[["date"] + CAL_M + T3], on="date", validate="m:1")
LOG["menu_panel_rows"] = len(P)

# ------------------------------------------------------------------ 2. descriptive relationships
desc = {}
def partial_corr(y, x, ctrl_df):
    X = pd.get_dummies(ctrl_df.astype("category"), drop_first=True).astype(float)
    X.insert(0, "c", 1.0)
    def resid(v):
        b, *_ = np.linalg.lstsq(X.values, v, rcond=None)
        return v - X.values @ b
    ry, rx = resid(np.asarray(y, float)), resid(np.asarray(x, float))
    r, p = stats.pearsonr(rx, ry)
    return r, p

for col in ("total_quantity", "order_count", "actual_sales"):
    y = np.log(D[col])
    r_raw, _ = stats.pearsonr(D.avg_temp_c, D[col])
    rho, _ = stats.spearmanr(D.avg_temp_c, D[col])
    ctrl = D[CAL].astype(str).agg("_".join, axis=1) if False else D[CAL]
    rp, pp = partial_corr(y, D.avg_temp_c, D[["weekday", "hol", "long_break", "pre_long_break", "exam_confirmed", "vacation_confirmed"]])
    desc[col] = {"pearson_raw": round(r_raw, 3), "spearman_raw": round(rho, 3), "partial_corr_calendar_adjusted": round(rp, 3), "p_approx(ignores autocorr)": float(f"{pp:.3g}")}
LOG["total_vs_temp"] = desc

bins = [-99, 0, 10, 20, 25, 99]; labels = ["<=0C", "0~10C", "10~20C", "20~25C", ">25C"]
D["tband"] = pd.cut(D.avg_temp_c, bins=bins, labels=labels, right=True)
band = D.groupby("tband", observed=True).agg(n_days=("date", "size"), avg_orders=("order_count", "mean"), avg_qty=("total_quantity", "mean"),
                                            avg_sales=("actual_sales", "mean"), hot_qty=("hot_quantity", "mean"), ice_qty=("ice_quantity", "mean")).round(2)
band.to_csv(OUT / "temp_band_total_summary.csv", encoding="utf-8-sig")

# menu-level: temperature sensitivity net of calendar (descriptive, in-sample)
rows = []
for mid, g in P.groupby("menu_id"):
    g = g.sort_values("date")
    ctrl = g[["weekday", "hol", "long_break", "pre_long_break", "exam_confirmed", "vacation_confirmed"]]
    rp, pp = partial_corr(np.log1p(g.quantity), g.avg_temp_c, ctrl)
    X = pd.get_dummies(ctrl.astype("category"), drop_first=True).astype(float)
    X["t10"] = (g.avg_temp_c.values - g.avg_temp_c.mean()) / 10
    m = PoissonRegressor(alpha=1e-6, max_iter=1000).fit(X.values, g.quantity.values)
    pct = (np.exp(m.coef_[-1]) - 1) * 100
    mm = MENUS[MENUS.menu_id == mid].iloc[0]
    rows.append({"menu_id": mid, "menu_name": mm.menu_name, "category": mm.category, "temperature_class": mm.temperature_class,
                 "mean_daily_qty": round(g.quantity.mean(), 2), "partial_corr_temp": round(rp, 3), "p_approx": float(f"{pp:.3g}"),
                 "pct_change_per_+10C_calendar_adjusted": round(pct, 1)})
menu_temp = pd.DataFrame(rows).sort_values("pct_change_per_+10C_calendar_adjusted")
menu_temp.to_csv(OUT / "menu_temperature_relation.csv", index=False, encoding="utf-8-sig")

# HOT/ICE relation
sel = P.merge(DM[["date", "menu_id", "hot_quantity", "ice_quantity"]], on=["date", "menu_id"], suffixes=("", "_dm"))
sel = sel[sel.menu_id.isin(MENUS[MENUS.temperature_class == "BOTH"].menu_id)]
sel["tband"] = pd.cut(sel.avg_temp_c, bins=bins, labels=labels, right=True)
hi_tbl = sel.groupby("tband", observed=True).agg(hot=("hot_quantity", "sum"), ice=("ice_quantity", "sum"))
hi_tbl["ice_share_pct"] = (hi_tbl.ice / (hi_tbl.hot + hi_tbl.ice) * 100).round(2)
hi_tbl["n_days"] = D.groupby("tband", observed=True).size()
hi_tbl.to_csv(OUT / "hot_ice_by_temp_band.csv", encoding="utf-8-sig")
day_hi = sel.groupby("date").agg(hot=("hot_quantity", "sum"), ice=("ice_quantity", "sum"), t=("avg_temp_c", "first"))
lr = LogisticRegression(C=1e6, max_iter=2000)
Xl = np.r_[day_hi.t.values, day_hi.t.values].reshape(-1, 1)
yl = np.r_[np.zeros(len(day_hi)), np.ones(len(day_hi))]
wl = np.r_[day_hi.hot.values, day_hi.ice.values].astype(float)
lr.fit(Xl, yl, sample_weight=wl)
slope, icpt = float(lr.coef_[0, 0]), float(lr.intercept_[0])
LOG["hot_ice_logistic_all_BOTH_menus"] = {"ice_share_slope_per_C": round(slope, 4), "temp_where_ice_share_50pct_C": round(-icpt / slope, 2),
                                          "temp_where_ice_share_50pct_note": "fitted on all 669 days (descriptive)"}
rows = []
for mid, g in sel.groupby("menu_id"):
    gd = g.groupby("date").agg(hot=("hot_quantity", "sum"), ice=("ice_quantity", "sum"), t=("avg_temp_c", "first"))
    q = g.assign(ice_share=lambda x: x.ice_quantity / (x.hot_quantity + x.ice_quantity).replace(0, np.nan))
    cold = gd[gd.t <= gd.t.quantile(.25)]; hot = gd[gd.t >= gd.t.quantile(.75)]
    rows.append({"menu_id": mid, "menu_name": MENUS.set_index("menu_id").menu_name[mid], "total_hot": int(gd.hot.sum()), "total_ice": int(gd.ice.sum()),
                 "ice_share_coldest_quartile_pct": round(cold.ice.sum() / (cold.hot.sum() + cold.ice.sum()) * 100, 1),
                 "ice_share_hottest_quartile_pct": round(hot.ice.sum() / (hot.hot.sum() + hot.ice.sum()) * 100, 1),
                 "daily_corr_temp_vs_ice_share": round(stats.pearsonr(gd.t, gd.ice / (gd.hot + gd.ice).replace(0, np.nan).fillna(0.5))[0], 3)})
pd.DataFrame(rows).to_csv(OUT / "hot_ice_by_menu.csv", index=False, encoding="utf-8-sig")

# "similar temperature & weekday -> best sellers"
def daygroup(r):
    if r.hol == 1 or r.weekday == 6: return "일요일/공휴일"
    if r.weekday == 5: return "토요일"
    return "평일"
Pq = P.copy()
Pq["day_group"] = Pq.apply(daygroup, axis=1)
Pq["tband"] = pd.cut(Pq.avg_temp_c, bins=[-99, 5, 15, 25, 99], labels=["<=5C", "5~15C", "15~25C", ">25C"])
nd = Pq.drop_duplicates("date").groupby(["tband", "day_group"], observed=True).size().rename("n_days")
agg = Pq.groupby(["tband", "day_group", "menu_id", "menu_name"], observed=True).quantity.sum().reset_index().merge(nd.reset_index(), on=["tband", "day_group"])
agg["avg_daily_qty"] = (agg.quantity / agg.n_days).round(2)
agg["rank"] = agg.groupby(["tband", "day_group"], observed=True).avg_daily_qty.rank(ascending=False, method="first")
top = agg[agg["rank"] <= 5].sort_values(["tband", "day_group", "rank"])
top[["tband", "day_group", "n_days", "rank", "menu_id", "menu_name", "avg_daily_qty"]].to_csv(OUT / "top_menus_by_temp_band_and_daytype.csv", index=False, encoding="utf-8-sig")

# ------------------------------------------------------------------ 3. forecasting experiment (time-ordered)
FIRST_TEST = pd.Timestamp("2026-01-01")
folds = []
s = FIRST_TEST
while s <= D.date.max():
    e = min(s + pd.offsets.MonthEnd(0), D.date.max())
    folds.append((s, e)); s = e + pd.Timedelta(days=1)
LOG["cv"] = {"scheme": "expanding window, monthly blocks; train = all dates strictly before the block start",
             "initial_train": [str(D.date.min().date()), "2025-12-31"], "n_folds": len(folds),
             "folds": [[str(a.date()), str(b.date())] for a, b in folds],
             "weather_input": "observed ASOS temperature on the target date (== perfect weather forecast; optimistic upper bound)"}

def make_glm(cols, spline_temp):
    cat = [c for c in cols if c in ("weekday", "month")]
    num_bin = [c for c in cols if c in ("hol", "long_break", "pre_long_break", "exam_confirmed", "vacation_confirmed")]
    temp = [c for c in cols if c in T3]
    tr = []
    if cat: tr.append(("cat", OneHotEncoder(handle_unknown="ignore", drop="first"), cat))
    if num_bin: tr.append(("bin", "passthrough", num_bin))
    if temp:
        if spline_temp and "avg_temp_c" in temp:
            tr.append(("spl", make_pipeline(StandardScaler(), SplineTransformer(n_knots=4, degree=2, extrapolation="linear")), ["avg_temp_c"]))
            rest = [c for c in temp if c != "avg_temp_c"]
            if rest: tr.append(("tmp", StandardScaler(), rest))
        else:
            tr.append(("tmp", StandardScaler(), temp))
    return make_pipeline(ColumnTransformer(tr), PoissonRegressor(alpha=1e-3, max_iter=3000))

def make_hgb(cols):
    return HistGradientBoostingRegressor(loss="poisson", max_depth=3, learning_rate=0.05, max_iter=200, min_samples_leaf=15, random_state=0)

def fit_predict(kind, cols, tr, te, target):
    if kind == "glm":
        m = make_glm(cols, spline_temp=True); m.fit(tr[cols], tr[target]); return m.predict(te[cols])
    if kind == "hgb":
        m = make_hgb(cols); m.fit(tr[cols], tr[target]); return m.predict(te[cols])

def seasonal_naive(tr, te, target, weeks=8):
    out = []
    for d in te.date:
        past = tr[(tr.weekday == d.weekday())].tail(weeks)[target]
        out.append(past.mean())
    return np.array(out)

def metrics(y, p):
    y, p = np.asarray(y, float), np.asarray(p, float)
    return {"MAE": float(np.mean(np.abs(y - p))), "RMSE": float(np.sqrt(np.mean((y - p) ** 2))),
            "WAPE_pct": float(np.abs(y - p).sum() / y.sum() * 100), "bias_pct": float((p - y).sum() / y.sum() * 100)}

def run_cv(df, target, specs):
    """specs: {name: (kind, cols)}; returns dict name -> DataFrame(date, y, pred). 'naive' handled by kind='naive'."""
    res = {k: [] for k in specs}
    for a, b in folds:
        tr = df[df.date < a]; te = df[(df.date >= a) & (df.date <= b)]
        assert tr.date.max() < te.date.min()
        for k, (kind, cols) in specs.items():
            p = seasonal_naive(tr, te, target) if kind == "naive" else fit_predict(kind, cols, tr, te, target)
            res[k].append(pd.DataFrame({"date": te.date.values, "y": te[target].values, "pred": p}))
    return {k: pd.concat(v, ignore_index=True) for k, v in res.items()}

def block_boot_diff(date_idx, e_a, e_b, block=7, B=2000):
    """paired block bootstrap on (error_a - error_b) summed per date; positive => b better."""
    df = pd.DataFrame({"d": date_idx, "a": e_a, "b": e_b}).groupby("d").sum().sort_index()
    diff = (df.a - df.b).values; n = len(diff); nb = int(np.ceil(n / block))
    starts = np.arange(n - block + 1)
    means = []
    for _ in range(B):
        st = rng.choice(starts, nb)
        idx = np.concatenate([np.arange(s, s + block) for s in st])[:n]
        means.append(diff[idx].mean())
    means = np.array(means)
    return float(diff.mean()), float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5)), float((means <= 0).mean())

SPECS = {
    "naive_weekday_8w": ("naive", None),
    "glm_cal": ("glm", CAL),
    "glm_cal+temp_avg": ("glm", CAL + T1),
    "glm_cal+temp_3": ("glm", CAL + T3),
    "glm_cal+month": ("glm", CAL_M),
    "glm_cal+month+temp_avg": ("glm", CAL_M + T1),
    "glm_cal+month+temp_3": ("glm", CAL_M + T3),
    "hgb_cal": ("hgb", CAL),
    "hgb_cal+temp_3": ("hgb", CAL + T3),
    "hgb_cal+month": ("hgb", CAL_M),
    "hgb_cal+month+temp_3": ("hgb", CAL_M + T3),
}
PAIRS = [("glm_cal", "glm_cal+temp_avg"), ("glm_cal", "glm_cal+temp_3"), ("glm_cal+month", "glm_cal+month+temp_avg"),
         ("glm_cal+month", "glm_cal+month+temp_3"), ("hgb_cal", "hgb_cal+temp_3"), ("hgb_cal+month", "hgb_cal+month+temp_3")]

def eval_target(df, target, specs, pairs, level, store):
    r = run_cv(df, target, specs)
    rows = []
    for k, v in r.items():
        m = metrics(v.y, v.pred); m.update(level=level, target=target, model=k, n_rows=len(v)); rows.append(m)
    pr = []
    for a, b in pairs:
        ea = np.abs(r[a].y.values - r[a].pred.values); eb = np.abs(r[b].y.values - r[b].pred.values)
        d, lo, hi, p = block_boot_diff(r[a].date.values, ea, eb)
        wa = ea.sum() / r[a].y.sum() * 100; wb = eb.sum() / r[b].y.sum() * 100
        pr.append({"level": level, "target": target, "without_temp": a, "with_temp": b, "WAPE_without": round(wa, 3), "WAPE_with": round(wb, 3),
                   "WAPE_change_pp(with-without)": round(wb - wa, 3), "abs_err_reduction_per_date_mean": round(d, 3),
                   "ci95_lo": round(lo, 3), "ci95_hi": round(hi, 3), "boot_share_<=0": round(p, 3)})
    store["metrics"] += rows; store["pairs"] += pr
    return r

ST = {"metrics": [], "pairs": []}
DAILY = D[["date"] + CAL_M + T3 + ["total_quantity", "order_count", "actual_sales", "hot_quantity", "ice_quantity"]].copy()
daily_res = {}
for tgt in ("total_quantity", "order_count", "actual_sales"):
    daily_res[tgt] = eval_target(DAILY, tgt, SPECS, PAIRS, "daily_total", ST)

# HOT / ICE of the 11 temperature-selectable menus (daily)
HI = sel.groupby("date").agg(hot=("hot_quantity", "sum"), ice=("ice_quantity", "sum")).reset_index().merge(D[["date"] + CAL_M + T3], on="date")
for tgt in ("hot", "ice"):
    eval_target(HI, tgt, {k: v for k, v in SPECS.items()}, PAIRS, "daily_HOT_ICE_BOTH_menus", ST)

# menu-level (27 menus; GLM only)
MSPECS = {k: v for k, v in SPECS.items() if k in ("naive_weekday_8w", "glm_cal", "glm_cal+temp_avg", "glm_cal+temp_3", "glm_cal+month", "glm_cal+month+temp_avg", "glm_cal+month+temp_3")}
MPAIRS = [p for p in PAIRS if p[0].startswith("glm")]
menu_preds = {k: [] for k in MSPECS}
for mid, g in P.groupby("menu_id"):
    g = g.sort_values("date").reset_index(drop=True)
    r = run_cv(g, "quantity", MSPECS)
    for k, v in r.items():
        menu_preds[k].append(v.assign(menu_id=mid))
menu_all = {k: pd.concat(v, ignore_index=True) for k, v in menu_preds.items()}
rows = []
for k, v in menu_all.items():
    m = metrics(v.y, v.pred); m.update(level="menu_day_pooled_27", target="quantity", model=k, n_rows=len(v)); rows.append(m)
ST["metrics"] += rows
for a, b in MPAIRS:
    ea = np.abs(menu_all[a].y.values - menu_all[a].pred.values); eb = np.abs(menu_all[b].y.values - menu_all[b].pred.values)
    d, lo, hi, p = block_boot_diff(menu_all[a].date.values, ea, eb)
    wa = ea.sum() / menu_all[a].y.sum() * 100; wb = eb.sum() / menu_all[b].y.sum() * 100
    ST["pairs"].append({"level": "menu_day_pooled_27", "target": "quantity", "without_temp": a, "with_temp": b, "WAPE_without": round(wa, 3), "WAPE_with": round(wb, 3),
                        "WAPE_change_pp(with-without)": round(wb - wa, 3), "abs_err_reduction_per_date_mean": round(d, 3), "ci95_lo": round(lo, 3), "ci95_hi": round(hi, 3), "boot_share_<=0": round(p, 3)})
# per-menu detail for the main comparison
rows = []
for mid in sorted(menu_all["glm_cal"].menu_id.unique()):
    rec = {"menu_id": mid, "menu_name": MENUS.set_index("menu_id").menu_name[mid], "temperature_class": MENUS.set_index("menu_id").temperature_class[mid]}
    for k in ("naive_weekday_8w", "glm_cal", "glm_cal+temp_3", "glm_cal+month", "glm_cal+month+temp_3"):
        v = menu_all[k][menu_all[k].menu_id == mid]; rec[f"WAPE_{k}"] = round(np.abs(v.y - v.pred).sum() / v.y.sum() * 100, 2)
    rec["delta_pp_cal_temp3_minus_cal"] = round(rec["WAPE_glm_cal+temp_3"] - rec["WAPE_glm_cal"], 2)
    rec["delta_pp_calmonth_temp3_minus_calmonth"] = round(rec["WAPE_glm_cal+month+temp_3"] - rec["WAPE_glm_cal+month"], 2)
    rows.append(rec)
mdet = pd.DataFrame(rows)
mdet.to_csv(OUT / "menu_level_wape_by_menu.csv", index=False, encoding="utf-8-sig")

# placebo: circularly shifted temperature (keeps autocorrelation/seasonality, breaks date alignment) -> chance-level improvement
def placebo(df, target, base_cols, shifts):
    base = run_cv(df, target, {"b": ("glm", base_cols)})["b"]
    wb = np.abs(base.y - base.pred).sum() / base.y.sum() * 100
    out = []
    for s in shifts:
        d2 = df.copy()
        for c in T3: d2[c] = np.roll(df[c].values, s)
        r = run_cv(d2, target, {"t": ("glm", base_cols + T3)})["t"]
        out.append(np.abs(r.y - r.pred).sum() / r.y.sum() * 100 - wb)
    return np.array(out), wb
shifts = [int(s) for s in rng.choice(np.arange(30, len(D) - 30), 40, replace=False)]
PL = {}
for name, df, tgt in (("daily_total_quantity", DAILY, "total_quantity"), ("hot_BOTH", HI, "hot"), ("ice_BOTH", HI, "ice")):
    for bname, bcols in (("cal", CAL), ("cal+month", CAL_M)):
        arr, wb = placebo(df, tgt, bcols, shifts)
        real = [p for p in ST["pairs"] if p["target"] == tgt and p["without_temp"] == f"glm_{bname}" and p["with_temp"] == f"glm_{bname}+temp_3" and p["level"].startswith("daily")][0]["WAPE_change_pp(with-without)"]
        PL[f"{name}|{bname}"] = {"base_WAPE": round(wb, 3), "real_change_pp": real, "placebo_mean_change_pp": round(float(arr.mean()), 3),
                                  "placebo_min": round(float(arr.min()), 3), "placebo_max": round(float(arr.max()), 3),
                                  "share_placebo_as_good_or_better": round(float((arr <= real).mean()), 3), "n_placebo": len(arr)}
LOG["placebo_shifted_temperature"] = PL

pd.DataFrame(ST["metrics"]).round(4).to_csv(OUT / "model_metrics_all.csv", index=False, encoding="utf-8-sig")
pd.DataFrame(ST["pairs"]).to_csv(OUT / "weather_vs_noweather_comparison.csv", index=False, encoding="utf-8-sig")

# per-fold daily-total comparison (stability)
rows = []
for tgt in ("total_quantity",):
    for (a, b), (fa, fb) in zip(folds, folds):
        pass
    r = daily_res[tgt]
    for a, b in folds:
        rec = {"fold": f"{a.date()}~{b.date()}"}
        for k in ("naive_weekday_8w", "glm_cal+month", "glm_cal+month+temp_3", "glm_cal", "glm_cal+temp_3"):
            v = r[k][(r[k].date >= a) & (r[k].date <= b)]
            rec[f"WAPE_{k}"] = round(np.abs(v.y - v.pred).sum() / v.y.sum() * 100, 2)
        rows.append(rec)
pd.DataFrame(rows).to_csv(OUT / "daily_total_quantity_by_fold.csv", index=False, encoding="utf-8-sig")

# predictions file (daily total qty; main models)
pred = daily_res["total_quantity"]["glm_cal+month"][["date", "y"]].rename(columns={"y": "actual_total_quantity"})
for k in ("naive_weekday_8w", "glm_cal", "glm_cal+temp_3", "glm_cal+month", "glm_cal+month+temp_3", "hgb_cal+month", "hgb_cal+month+temp_3"):
    pred[f"pred_{k}"] = daily_res["total_quantity"][k].pred.round(2).values
pred.to_csv(OUT / "daily_total_quantity_predictions.csv", index=False, encoding="utf-8-sig")

LOG["test_period"] = {"start": str(pred.date.min().date()), "end": str(pred.date.max().date()), "days": len(pred),
                      "menu_day_rows": len(menu_all["glm_cal"]), "train_rows_first_fold": int((D.date < FIRST_TEST).sum())}
(OUT / "analysis_log.json").write_text(json.dumps(LOG, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps(LOG["join"], ensure_ascii=False)); print(json.dumps(LOG["total_vs_temp"], ensure_ascii=False))
print(band.to_string()); print(hi_tbl.to_string()); print(json.dumps(LOG["hot_ice_logistic_all_BOTH_menus"]))
print(pd.DataFrame(ST["metrics"]).round(3).to_string()); print(pd.DataFrame(ST["pairs"]).to_string())
print(json.dumps(PL, ensure_ascii=False, indent=1)); print(json.dumps(LOG["test_period"]))
