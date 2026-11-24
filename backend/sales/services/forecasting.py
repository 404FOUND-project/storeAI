"""Next-day sales / order / per-menu quantity forecasting (pure functions, no database access).

Method ("weekday index x recent level"), chosen by rolling one-day-ahead backtests
against simpler candidates (last-week value, weekday means, exponential smoothing):

  1. weekday index  = mean of each weekday over the previous 12 weeks, divided by
                      the mean of the weekday means;
  2. recent level   = mean of (value / weekday index) over the previous 14 days;
  3. forecast       = level x weekday index of the target day.

Leakage rule: predicting `target` only ever reads days strictly before `target`.
Public holidays and school schedules are NOT inputs (they are not stored in the
database), so holiday / exam / vacation effects are not modelled.

`series` is {date: value} containing only days with data; a missing day is
"no data" and never treated as zero.
"""
from collections import defaultdict
from datetime import timedelta
from statistics import mean

INDEX_WINDOW_DAYS = 12 * 7
LEVEL_WINDOW_DAYS = 14
MIN_INDEX_OBSERVATIONS = 28
MIN_LEVEL_OBSERVATIONS = 7
INTERVAL_BACKTEST_DAYS = 56
MIN_INTERVAL_SAMPLES = 20
INTERVAL_QUANTILES = (0.10, 0.90)
MENU_SHARE_WINDOW_DAYS = 56
MENU_BACKTEST_DAYS = 28
METHOD_NAME = "weekday_index_x_recent_level"


class InsufficientHistory(Exception):
    """Not enough recent data before the target date to forecast."""


def predict_value(series, target):
    """Forecast `series` for `target` using only days before `target`."""
    index_start = target - timedelta(days=INDEX_WINDOW_DAYS)
    hist = [(d, v) for d, v in series.items() if index_start <= d < target]
    if len(hist) < MIN_INDEX_OBSERVATIONS:
        raise InsufficientHistory(
            f"예측에 필요한 과거 데이터가 부족합니다 (최근 12주 중 {len(hist)}일, 최소 {MIN_INDEX_OBSERVATIONS}일 필요)."
        )
    by_weekday = defaultdict(list)
    for d, v in hist:
        by_weekday[d.weekday()].append(v)
    weekday_mean = {wd: mean(vals) for wd, vals in by_weekday.items()}
    overall = mean(weekday_mean.values())
    if overall <= 0:
        raise InsufficientHistory("최근 12주 동안 값이 모두 0이라 예측할 수 없습니다.")
    index = {wd: m / overall for wd, m in weekday_mean.items()}

    level_start = target - timedelta(days=LEVEL_WINDOW_DAYS)
    recent = [(d, v) for d, v in hist if d >= level_start and index.get(d.weekday(), 0) > 0]
    if len(recent) < MIN_LEVEL_OBSERVATIONS:
        raise InsufficientHistory(
            f"예측 기준일 직전 14일 중 데이터가 {len(recent)}일뿐이라 예측할 수 없습니다 (최소 {MIN_LEVEL_OBSERVATIONS}일 필요)."
        )
    level = mean(v / index[d.weekday()] for d, v in recent)
    return max(level * index.get(target.weekday(), 1.0), 0.0)


def _quantile(sorted_values, q):
    pos = q * (len(sorted_values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(sorted_values) - 1)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def backtest(series, as_of, days=INTERVAL_BACKTEST_DAYS):
    """One-day-ahead errors for the last `days` days up to and including `as_of`.

    Each day is predicted only from data before that day, so this never uses
    anything newer than the day being predicted.
    """
    pairs = []
    for k in range(days):
        d = as_of - timedelta(days=k)
        if d not in series:
            continue
        try:
            pairs.append((d, series[d], predict_value(series, d)))
        except InsufficientHistory:
            continue
    return pairs


def accuracy(pairs):
    """WAPE (%) and mean absolute error over (date, actual, predicted) triples."""
    actual_total = sum(a for _, a, _ in pairs)
    if not pairs or actual_total <= 0:
        return {"samples": len(pairs), "wape_pct": None, "mae": None}
    abs_err = [abs(a - p) for _, a, p in pairs]
    return {"samples": len(pairs), "wape_pct": round(sum(abs_err) / actual_total * 100, 2),
            "mae": round(mean(abs_err), 2)}


def interval_from_errors(pairs, prediction):
    """Empirical 80% range from actual/predicted ratios of recent backtest days."""
    ratios = sorted(a / p for _, a, p in pairs if p > 0)
    if len(ratios) < MIN_INTERVAL_SAMPLES:
        return None
    lo, hi = (_quantile(ratios, q) for q in INTERVAL_QUANTILES)
    return {"low": prediction * lo, "high": prediction * hi, "samples": len(ratios), "coverage_nominal": 0.8}


def forecast_next_day(daily, as_of):
    """Forecast sales and order count for as_of + 1 day from data up to as_of.

    `daily` is {date: {"sales": int, "orders": int}}; rows after `as_of` are ignored.
    """
    target = as_of + timedelta(days=1)
    daily = {d: r for d, r in daily.items() if d <= as_of}
    out = {"as_of": as_of.isoformat(), "target_date": target.isoformat(), "method": METHOD_NAME}
    for key, label in (("sales", "predicted_sales"), ("orders", "predicted_order_count")):
        series = {d: float(r[key]) for d, r in daily.items()}
        value = predict_value(series, target)
        pairs = backtest(series, as_of)
        interval = interval_from_errors(pairs, value)
        out[label] = int(round(value))
        out[f"{label}_range_80"] = (
            {"low": int(round(interval["low"])), "high": int(round(interval["high"]))} if interval else None
        )
        out[f"{key}_backtest"] = accuracy(pairs)
    pred_sales, pred_orders = out["predicted_sales"], out["predicted_order_count"]
    out["predicted_average_ticket"] = int(round(pred_sales / pred_orders)) if pred_orders else None
    out["backtest_window_days"] = INTERVAL_BACKTEST_DAYS
    return out


def predict_menu_quantities(menu_daily, target):
    """Expected quantity per menu for `target`: recent menu share x total-quantity forecast.

    `menu_daily` is {menu_id: {date: quantity}}. Returns (total_forecast, {menu_id: value}).
    """
    total_series = defaultdict(float)
    for series in menu_daily.values():
        for d, q in series.items():
            if d < target:
                total_series[d] += q
    total_forecast = predict_value(dict(total_series), target)
    window_start = target - timedelta(days=MENU_SHARE_WINDOW_DAYS)
    sums = {m: sum(q for d, q in s.items() if window_start <= d < target) for m, s in menu_daily.items()}
    grand = sum(sums.values())
    if grand <= 0:
        raise InsufficientHistory("최근 8주 동안 메뉴 판매 데이터가 없습니다.")
    return total_forecast, {m: total_forecast * s / grand for m, s in sums.items() if s > 0}


def forecast_menu_quantities(menu_daily, names, as_of):
    """Per-menu expected quantity for as_of + 1 day, with a pooled backtest accuracy."""
    target = as_of + timedelta(days=1)
    menu_daily = {m: {d: q for d, q in s.items() if d <= as_of} for m, s in menu_daily.items()}
    total_forecast, per_menu = predict_menu_quantities(menu_daily, target)

    abs_err = actual = 0.0
    days_used = 0
    for k in range(MENU_BACKTEST_DAYS):
        d = as_of - timedelta(days=k)
        try:
            _, pred = predict_menu_quantities(menu_daily, d)
        except InsufficientHistory:
            continue
        days_used += 1
        for m in set(pred) | {m for m, s in menu_daily.items() if d in s}:
            y = menu_daily.get(m, {}).get(d, 0)
            abs_err += abs(y - pred.get(m, 0.0))
            actual += y
    menus = [
        {"menu_id": m, "menu_name": names.get(m, ""),
         "expected_quantity": round(v, 2), "expected_quantity_rounded": int(v + 0.5)}
        for m, v in sorted(per_menu.items(), key=lambda kv: (-kv[1], kv[0]))
    ]
    return {
        "as_of": as_of.isoformat(),
        "target_date": target.isoformat(),
        "method": "recent_menu_share_x_total_quantity_forecast",
        "total_expected_quantity": round(total_forecast, 2),
        "menus": menus,
        "backtest": {
            "days": days_used,
            "pooled_menu_wape_pct": round(abs_err / actual * 100, 2) if actual else None,
            "note": "메뉴별 일 판매량이 작은 정수라 메뉴 단위 오차는 큽니다. 합계 수량이 더 안정적입니다.",
        },
    }
