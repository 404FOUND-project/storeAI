"""Sales analysis on top of per-day totals (pure functions, no database access).

`daily` is {date: {"sales": int, "orders": int}} containing only days that have
at least one order. A day without rows is "no data", not "zero sales"; it is
excluded from per-day averages and reported through `days_with_data`.
"""
import calendar
from collections import defaultdict
from datetime import timedelta

WEEKDAY_NAMES = ("월", "화", "수", "목", "금", "토", "일")


def average_ticket(sales, orders):
    """Average order value in won, rounded half up; None when there are no orders."""
    if not orders:
        return None
    return int((2 * sales + orders) // (2 * orders))


def _metrics(sales, orders, days_with_data):
    return {
        "sales": sales,
        "order_count": orders,
        "average_ticket": average_ticket(sales, orders),
        "days_with_data": days_with_data,
    }


def _sum_range(daily, start, end):
    sales = orders = days = 0
    d = start
    while d <= end:
        row = daily.get(d)
        if row:
            sales += row["sales"]
            orders += row["orders"]
            days += 1
        d += timedelta(days=1)
    return _metrics(sales, orders, days)


def summarize(daily):
    return _metrics(
        sum(r["sales"] for r in daily.values()),
        sum(r["orders"] for r in daily.values()),
        len(daily),
    )


def _period_bounds(day, granularity):
    if granularity == "day":
        return day, day
    if granularity == "week":
        start = day - timedelta(days=day.weekday())  # ISO week, Monday start
        return start, start + timedelta(days=6)
    start = day.replace(day=1)
    return start, day.replace(day=calendar.monthrange(day.year, day.month)[1])


def rollup(daily, granularity, start, end):
    """Sales, orders and average ticket per day / ISO week / calendar month.

    Periods cut by the requested [start, end] window are flagged `is_partial`.
    """
    buckets = defaultdict(lambda: [0, 0, 0])
    for day, row in daily.items():
        if not (start <= day <= end):
            continue
        key = _period_bounds(day, granularity)
        b = buckets[key]
        b[0] += row["sales"]
        b[1] += row["orders"]
        b[2] += 1
    series = []
    for (p_start, p_end) in sorted(buckets):
        sales, orders, days = buckets[(p_start, p_end)]
        item = {"period_start": p_start.isoformat(), "period_end": p_end.isoformat(),
                "is_partial": p_start < start or p_end > end}
        item.update(_metrics(sales, orders, days))
        series.append(item)
    return series


def weekday_pattern(daily):
    """Per weekday: totals and per-day averages over days that have data."""
    agg = {wd: [0, 0, 0] for wd in range(7)}
    for day, row in daily.items():
        a = agg[day.weekday()]
        a[0] += row["sales"]
        a[1] += row["orders"]
        a[2] += 1
    out = []
    for wd in range(7):
        sales, orders, days = agg[wd]
        out.append({
            "weekday": wd,
            "weekday_name": WEEKDAY_NAMES[wd],
            "days_with_data": days,
            "total_sales": sales,
            "total_orders": orders,
            "avg_daily_sales": round(sales / days) if days else None,
            "avg_daily_orders": round(orders / days, 1) if days else None,
            "average_ticket": average_ticket(sales, orders),
        })
    return out


def hourly_pattern(hourly, days_with_data):
    """Per hour of day (only hours that have sales), with share of total sales."""
    total_sales = sum(r["sales"] for r in hourly.values())
    out = []
    for hour in sorted(hourly):
        sales, orders = hourly[hour]["sales"], hourly[hour]["orders"]
        out.append({
            "hour": hour,
            "total_sales": sales,
            "total_orders": orders,
            "avg_sales_per_day": round(sales / days_with_data) if days_with_data else None,
            "avg_orders_per_day": round(orders / days_with_data, 2) if days_with_data else None,
            "average_ticket": average_ticket(sales, orders),
            "sales_share_pct": round(sales / total_sales * 100, 2) if total_sales else None,
        })
    return out


def _change(current, base):
    """Absolute and percentage change; percentage is None when base is 0/None."""
    if current is None or base is None:
        return {"current": current, "base": base, "change": None, "change_pct": None}
    change = current - base
    pct = round(change / base * 100, 2) if base else None
    return {"current": current, "base": base, "change": change, "change_pct": pct}


def _compare_block(cur_range, base_range, cur, base):
    note = None
    if base["days_with_data"] == 0:
        note = "비교 기간에 매출 데이터가 없어 변화율을 계산하지 않았습니다."
    elif cur["days_with_data"] == 0:
        note = "대상 기간에 매출 데이터가 없습니다."
    comparable = note is None
    out = {
        "current_period": [cur_range[0].isoformat(), cur_range[1].isoformat()],
        "base_period": [base_range[0].isoformat(), base_range[1].isoformat()],
        "current_days_with_data": cur["days_with_data"],
        "base_days_with_data": base["days_with_data"],
        "note": note,
    }
    for key in ("sales", "order_count", "average_ticket"):
        out[key] = (_change(cur[key], base[key]) if comparable
                    else {"current": cur[key], "base": base[key], "change": None, "change_pct": None})
    return out


def compare(daily, as_of):
    """Day-, week- and month-over-period comparisons anchored at `as_of`.

    - day_vs_previous_day: as_of vs the day before
    - day_vs_same_weekday_last_week: as_of vs as_of - 7 days
    - week_vs_previous_week: trailing 7 days ending as_of vs the 7 days before
    - month_to_date_vs_previous_month: 1st..as_of vs the previous month's 1st..same
      day-of-month (clamped to the previous month's last day)
    """
    def block(cur_range, base_range):
        return _compare_block(cur_range, base_range,
                              _sum_range(daily, *cur_range), _sum_range(daily, *base_range))

    prev_day = as_of - timedelta(days=1)
    last_week = as_of - timedelta(days=7)
    first = as_of.replace(day=1)
    prev_last = first - timedelta(days=1)
    prev_first = prev_last.replace(day=1)
    prev_end = prev_first + timedelta(days=min(as_of.day, prev_last.day) - 1)
    return {
        "as_of": as_of.isoformat(),
        "day_vs_previous_day": block((as_of, as_of), (prev_day, prev_day)),
        "day_vs_same_weekday_last_week": block((as_of, as_of), (last_week, last_week)),
        "week_vs_previous_week": block((as_of - timedelta(days=6), as_of),
                                       (as_of - timedelta(days=13), as_of - timedelta(days=7))),
        "month_to_date_vs_previous_month": block((first, as_of), (prev_first, prev_end)),
    }


__all__ = ["average_ticket", "summarize", "rollup", "weekday_pattern", "hourly_pattern", "compare"]
