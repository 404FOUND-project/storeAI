"""Training / inference dataset assembly from the database and the CSV calendars.

Time basis rules
- Sales are read only up to `as_of`, which is clamped to the last complete KST day
  (see boundary.py); future synthetic scenario sales are excluded unless the caller
  passes allow_future=True (scenario experiments only).
- Training weather = observed ASOS values. The synthetic Nov-2026 scenario temperature
  is used ONLY when use_scenario=True (scenario experiments). `temp_source` records the origin.
- Forecast weather is read only by `weather_for_targets`, only from publications issued
  at or before the forecast time, and is never mixed into the observed layer.
- Missing weather/calendar values stay NaN (precipitation is never filled with 0).
"""
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from django.db.models import Count, F, Sum
from django.db.models.functions import ExtractHour, TruncDate

from sales.models import Sales, SalesItem
from weatherdata.models import WeatherDatum
from .boundary import KST, clamp_as_of
from .calendar_features import calendar_frame, load_events, load_holidays

ROOT = Path(__file__).resolve().parents[3]
HOLIDAY_FILES = [
    ROOT / "data/holidays/404dabang_holidays.csv",
    ROOT / "data/holidays/404dabang_holidays_2026-11_2027-12.csv",
]
EVENTS_FILE = ROOT / "docs/source/school_academic_calendar.csv"
CALENDAR_END = "2027-02-28"
TEMP_VARS = {"avg_temperature": "temp_avg", "max_temperature": "temp_max", "min_temperature": "temp_min",
             "avg_humidity": "humidity", "avg_wind_speed": "wind"}
WEATHER_COLUMNS = ["temp_avg", "temp_max", "temp_min", "humidity", "wind", "precip_mm"]


class InsufficientData(Exception):
    """Not enough operating data to build or fit a forecast."""


def _empty_frames():
    daily = pd.DataFrame({"sales": [], "orders": [], "quantity": [], "hot_qty": [], "ice_qty": []},
                         index=pd.DatetimeIndex([], name="date"))
    hourly = pd.DataFrame({"date": pd.to_datetime([]), "hour": [], "sales": [], "orders": []})
    menu = pd.DataFrame({"date": pd.to_datetime([]), "menu_id": [], "serving_temperature": [],
                         "qty": [], "amt": []})
    return daily, hourly, menu


def load_sales(store_id, as_of=None, *, allow_future=False, now=None):
    """-> (daily, hourly, menu_day) with KST dates, only rows dated <= clamped as_of."""
    as_of = clamp_as_of(as_of, now, allow_future)
    hi = datetime.combine(as_of + timedelta(days=1), datetime.min.time(), tzinfo=KST)
    sales = Sales.objects.filter(store_id=store_id, sold_at__lt=hi)
    items = SalesItem.objects.filter(sales__store_id=store_id, sales__sold_at__lt=hi)
    daily = pd.DataFrame(sales.annotate(d=TruncDate("sold_at", tzinfo=KST)).values("d")
                         .annotate(sales=Sum("total_amount"), orders=Count("id")).order_by("d"))
    if daily.empty:
        return _empty_frames()
    hourly = pd.DataFrame(sales.annotate(d=TruncDate("sold_at", tzinfo=KST), h=ExtractHour("sold_at", tzinfo=KST))
                          .values("d", "h").annotate(sales=Sum("total_amount"), orders=Count("id")).order_by("d", "h"))
    menu = pd.DataFrame(items.annotate(d=TruncDate("sales__sold_at", tzinfo=KST))
                        .values("d", "menu_id", "serving_temperature")
                        .annotate(qty=Sum("quantity"), amt=Sum(F("quantity") * F("unit_price"))))
    daily["d"] = pd.to_datetime(daily["d"])
    hourly["d"] = pd.to_datetime(hourly["d"])
    daily = daily.rename(columns={"d": "date"}).set_index("date")
    hourly = hourly.rename(columns={"d": "date", "h": "hour"})
    full_hours = pd.MultiIndex.from_product([daily.index, range(8, 22)], names=["date", "hour"])
    hourly = hourly.set_index(["date", "hour"]).reindex(full_hours, fill_value=0).reset_index()
    if menu.empty:
        menu = _empty_frames()[2]
    else:
        menu["d"] = pd.to_datetime(menu["d"])
        menu = menu.rename(columns={"d": "date"})
        menu["qty"] = menu["qty"].astype(int)
        menu["amt"] = menu["amt"].astype(float)
        completed = []
        for (menu_id, temp), group in menu.groupby(["menu_id", "serving_temperature"], dropna=False):
            group = group.set_index("date").sort_index()
            dates = pd.date_range(group.index.min(), daily.index.max(), freq="D")
            group = group.reindex(dates)
            group["menu_id"] = menu_id
            group["serving_temperature"] = temp
            group[["qty", "amt"]] = group[["qty", "amt"]].fillna(0)
            group.index.name = "date"
            completed.append(group.reset_index())
        menu = pd.concat(completed, ignore_index=True)
        menu["qty"] = menu["qty"].astype(int)
        menu["amt"] = menu["amt"].astype(float)
    qty = menu.groupby("date").qty.sum()
    hot = menu[menu.serving_temperature == "HOT"].groupby("date").qty.sum()
    ice = menu[menu.serving_temperature == "ICE"].groupby("date").qty.sum()
    daily["sales"] = daily["sales"].astype(int)
    daily["orders"] = daily["orders"].astype(int)
    daily["quantity"] = qty.reindex(daily.index).fillna(0).astype(int)
    daily["hot_qty"] = hot.reindex(daily.index).fillna(0).astype(int)
    daily["ice_qty"] = ice.reindex(daily.index).fillna(0).astype(int)
    hourly["hour"] = hourly["hour"].astype(int)
    return daily, hourly, menu


def _weather_rows(qs):
    df = pd.DataFrame(list(qs.values("valid_at", "variable", "value_numeric")))
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df.valid_at, utc=True).dt.tz_convert(KST).dt.tz_localize(None).dt.normalize()
    df["value_numeric"] = df.value_numeric.astype(float)
    return df.pivot_table(index="date", columns="variable", values="value_numeric", aggfunc="last")


def load_training_weather(as_of=None, use_scenario=False, now=None, allow_future=False):
    """Daily weather frame for training; columns WEATHER_COLUMNS + temp_source. Missing stays NaN."""
    as_of = clamp_as_of(as_of, now, allow_future)
    obs = _weather_rows(WeatherDatum.objects.filter(
        collection_run__source_type="observed", collection_run__status="succeeded", period="daily",
        quality_status="valid", variable__in=list(TEMP_VARS) + ["precipitation"]))
    w = obs.rename(columns={**TEMP_VARS, "precipitation": "precip_mm"}) if not obs.empty else pd.DataFrame()
    w = w.reindex(columns=WEATHER_COLUMNS)
    w["temp_source"] = np.where(w["temp_avg"].notna(), "observed_asos", "missing")
    if use_scenario:
        scen = _weather_rows(WeatherDatum.objects.filter(
            collection_run__source_type="scenario", collection_run__status="succeeded",
            variable="avg_temperature"))
        if not scen.empty:
            override = scen["avg_temperature"].dropna()
            w = w.reindex(w.index.union(override.index))
            w.loc[override.index, "temp_avg"] = override
            w.loc[override.index, "temp_source"] = "scenario_synthetic"
    w = w[w.index <= pd.Timestamp(as_of)]
    w.index.name = "date"
    return w.sort_index()


def build_calendar(start="2025-01-01", end=CALENDAR_END):
    return calendar_frame(start, end, load_holidays(HOLIDAY_FILES), load_events(EVENTS_FILE))


def build_daily_frame(store_id, as_of=None, *, use_scenario=False, allow_future=False, now=None):
    """-> (daily, hourly, menu, calendar, weather). `daily` = sales + weather + calendar features."""
    as_of = clamp_as_of(as_of, now, allow_future)
    daily, hourly, menu = load_sales(store_id, as_of, allow_future=allow_future, now=now)
    if daily.empty:
        raise InsufficientData("매출 데이터가 없어 예측 데이터셋을 만들 수 없습니다.")
    cal = build_calendar(daily.index.min(), CALENDAR_END)
    weather = load_training_weather(as_of, use_scenario, now, allow_future)
    df = daily.join(cal, how="left").join(weather, how="left")
    df["temp_source"] = df["temp_source"].fillna("missing")
    df["avg_ticket"] = df.sales / df.orders.replace(0, np.nan)
    return df, hourly, menu, cal, weather


def climatology(weather: pd.DataFrame, target: pd.Timestamp, window_days=7):
    """Mean observed avg temp within +-window days of the same calendar day in earlier years."""
    if weather is None or weather.empty or "temp_avg" not in weather:
        return None
    obs = weather[weather.temp_source == "observed_asos"]["temp_avg"].dropna()
    vals = []
    for year in sorted(set(obs.index.year)):
        try:
            center = target.replace(year=year)
        except ValueError:
            continue
        sel = obs[(obs.index >= center - timedelta(days=window_days)) &
                  (obs.index <= center + timedelta(days=window_days)) & (obs.index < target)]
        vals.extend(sel.tolist())
    return float(np.mean(vals)) if vals else None


def observed_temperature_for_targets(targets, weather):
    """Backfill only: observed ASOS temperature on the target date (optimistic 'perfect forecast')."""
    out = {}
    for t in targets:
        t = pd.Timestamp(t)
        v = weather["temp_avg"].get(t) if weather is not None and not weather.empty else None
        if v is not None and not pd.isna(v):
            out[t] = {"temp_avg": float(v), "basis": "observed_backfill"}
        else:
            out[t] = {"temp_avg": None, "basis": "none"}
    return out


def weather_for_targets(location, targets, issued_at, weather_obs):
    """Temperature input per future target date from data published at or before `issued_at`.

    Priority: latest short-term forecast (daily mean of hourly TMP, >= 8 hourly values) ->
    latest mid-term forecast ((min+max)/2) -> climatology -> none.
    Any failure reading forecasts degrades to climatology/none; it never raises.
    -> {Timestamp: {"temp_avg": float|None, "basis": str}}
    """
    from weatherdata.models import WeatherForecastPublication

    short = mid = None
    try:
        def latest(dtype):
            return (WeatherForecastPublication.objects
                    .filter(location=location, dataset_type=dtype, issued_at__lte=issued_at,
                            collection_runs__status="succeeded")
                    .order_by("-issued_at").distinct().first())

        pub = latest("short_forecast") if location is not None else None
        if pub:
            rows = pd.DataFrame(list(WeatherDatum.objects.filter(
                forecast_publication=pub, variable="temperature", quality_status="valid")
                .values("valid_at", "value_numeric")))
            if not rows.empty:
                rows["date"] = pd.to_datetime(rows.valid_at, utc=True).dt.tz_convert(KST).dt.tz_localize(None).dt.normalize()
                rows["v"] = rows.value_numeric.astype(float)
                g = rows.groupby("date").v.agg(["mean", "count"])
                short = g[g["count"] >= 8]["mean"]
        pub = latest("mid_temperature") if location is not None else None
        if pub:
            rows = pd.DataFrame(list(WeatherDatum.objects.filter(
                forecast_publication=pub, quality_status="valid",
                variable__in=["min_temperature", "max_temperature"]).values("valid_at", "variable", "value_numeric")))
            if not rows.empty:
                rows["date"] = pd.to_datetime(rows.valid_at, utc=True).dt.tz_convert(KST).dt.tz_localize(None).dt.normalize()
                rows["v"] = rows.value_numeric.astype(float)
                p = rows.pivot_table(index="date", columns="variable", values="v", aggfunc="last")
                if {"min_temperature", "max_temperature"} <= set(p.columns):
                    mid = ((p.min_temperature + p.max_temperature) / 2).dropna()
    except Exception:  # forecast storage problems must never break prediction
        short = mid = None
    out = {}
    for t in targets:
        t = pd.Timestamp(t)
        if short is not None and t in short.index:
            out[t] = {"temp_avg": float(short[t]), "basis": "short_forecast"}
        elif mid is not None and t in mid.index:
            out[t] = {"temp_avg": float(mid[t]), "basis": "mid_forecast"}
        else:
            c = climatology(weather_obs, t)
            out[t] = {"temp_avg": c, "basis": "climatology" if c is not None else "none"}
    return out
