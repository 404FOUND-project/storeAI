"""Training / inference dataset assembly from the database and the CSV calendars.

Weather used for TRAINING (per date):
  1. scenario temperature (source_type=scenario) when one exists for the date, because
     the synthetic Nov-2026 sales were generated from exactly that scenario;
  2. otherwise the observed ASOS value.
`temp_source` records which one was used. Observed and forecast layers are never mixed:
forecast rows are only read by `weather_for_targets` for dates after `as_of`.
"""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
from django.db.models import Count, Sum
from django.db.models.functions import ExtractHour, TruncDate

from sales.models import Sales, SalesItem
from weatherdata.models import WeatherDatum
from .calendar_features import calendar_frame, load_events, load_holidays

KST = ZoneInfo("Asia/Seoul")
ROOT = __import__("pathlib").Path(__file__).resolve().parents[3]
HOLIDAY_FILES = [
    ROOT / "data/holidays/404dabang_holidays.csv",
    ROOT / "data/holidays/404dabang_holidays_2026-11_2027-12.csv",
]
EVENTS_FILE = ROOT / "docs/source/school_academic_calendar.csv"
CALENDAR_END = "2027-02-28"
TEMP_VARS = {"avg_temperature": "temp_avg", "max_temperature": "temp_max", "min_temperature": "temp_min",
             "avg_humidity": "humidity", "avg_wind_speed": "wind"}


def _local_date(series):
    return pd.to_datetime(series).dt.tz_localize(None) if getattr(series.dt, "tz", None) is None \
        else pd.to_datetime(series).dt.tz_convert(KST).dt.tz_localize(None).dt.normalize()


def load_sales(store_id, as_of=None):
    """-> (daily, hourly, menu_day) DataFrames in KST dates, using rows up to and including as_of."""
    sales = Sales.objects.filter(store_id=store_id)
    items = SalesItem.objects.filter(sales__store_id=store_id)
    if as_of is not None:
        hi = datetime.combine(pd.Timestamp(as_of).date() + timedelta(days=1), datetime.min.time(), tzinfo=KST)
        sales = sales.filter(sold_at__lt=hi)
        items = items.filter(sales__sold_at__lt=hi)
    daily = pd.DataFrame(sales.annotate(d=TruncDate("sold_at", tzinfo=KST)).values("d")
                         .annotate(sales=Sum("total_amount"), orders=Count("id")).order_by("d"))
    hourly = pd.DataFrame(sales.annotate(d=TruncDate("sold_at", tzinfo=KST), h=ExtractHour("sold_at", tzinfo=KST))
                          .values("d", "h").annotate(sales=Sum("total_amount"), orders=Count("id")).order_by("d", "h"))
    menu = pd.DataFrame(items.annotate(d=TruncDate("sales__sold_at", tzinfo=KST))
                        .values("d", "menu_id", "serving_temperature").annotate(qty=Sum("quantity")))
    for df in (daily, hourly, menu):
        df["d"] = pd.to_datetime(df["d"])
    daily = daily.rename(columns={"d": "date"}).set_index("date")
    hourly = hourly.rename(columns={"d": "date", "h": "hour"})
    menu = menu.rename(columns={"d": "date"})
    menu["qty"] = menu["qty"].astype(int)
    qty = menu.groupby("date").qty.sum()
    hot = menu[menu.serving_temperature == "HOT"].groupby("date").qty.sum()
    ice = menu[menu.serving_temperature == "ICE"].groupby("date").qty.sum()
    daily["quantity"] = qty.reindex(daily.index).fillna(0).astype(int)
    daily["hot_qty"] = hot.reindex(daily.index).fillna(0).astype(int)
    daily["ice_qty"] = ice.reindex(daily.index).fillna(0).astype(int)
    daily["sales"] = daily["sales"].astype(int)
    return daily, hourly, menu


def _weather_rows(qs):
    df = pd.DataFrame(qs.values("valid_at", "variable", "value_numeric"))
    if df.empty:
        return pd.DataFrame()
    df["date"] = pd.to_datetime(df.valid_at).dt.tz_convert(KST).dt.tz_localize(None).dt.normalize()
    df["value_numeric"] = df.value_numeric.astype(float)
    return df.pivot_table(index="date", columns="variable", values="value_numeric", aggfunc="last")


def load_training_weather(as_of=None):
    """Observed ASOS (+ scenario temp override) as one daily frame with temp_source."""
    obs = _weather_rows(WeatherDatum.objects.filter(
        collection_run__source_type="observed", collection_run__status="succeeded", period="daily",
        quality_status="valid", variable__in=list(TEMP_VARS) + ["precipitation"]))
    scen = _weather_rows(WeatherDatum.objects.filter(
        collection_run__source_type="scenario", collection_run__status="succeeded", variable="avg_temperature"))
    w = obs.rename(columns={**TEMP_VARS, "precipitation": "precip_mm"}) if not obs.empty else pd.DataFrame()
    w["temp_source"] = "observed_asos"
    if not scen.empty:
        override = scen["avg_temperature"].dropna()
        w = w.reindex(w.index.union(override.index))
        w.loc[override.index, "temp_avg"] = override
        w.loc[override.index, "temp_source"] = "scenario_synthetic"
    if as_of is not None:
        w = w[w.index <= pd.Timestamp(as_of)]
    w.index.name = "date"
    return w.sort_index()


def build_calendar(start="2025-01-01", end=CALENDAR_END):
    return calendar_frame(start, end, load_holidays(HOLIDAY_FILES), load_events(EVENTS_FILE))


def build_daily_frame(store_id, as_of=None):
    """Daily training frame: sales + weather + calendar for days that have sales."""
    daily, hourly, menu = load_sales(store_id, as_of)
    cal = build_calendar(daily.index.min(), CALENDAR_END)
    weather = load_training_weather(as_of)
    df = daily.join(cal, how="left").join(weather, how="left")
    df["avg_ticket"] = df.sales / df.orders
    return df, hourly, menu, cal


def climatology(weather: pd.DataFrame, target: pd.Timestamp, window_days=7):
    """Mean observed avg temp within +-window days of the same calendar day in past years."""
    obs = weather[weather.temp_source == "observed_asos"]["temp_avg"].dropna()
    if obs.empty:
        return None
    vals = []
    for year in sorted(set(obs.index.year)):
        try:
            center = target.replace(year=year)
        except ValueError:
            continue
        vals.extend(obs[(obs.index >= center - timedelta(days=window_days)) &
                        (obs.index <= center + timedelta(days=window_days)) & (obs.index < target)].tolist())
    return float(np.mean(vals)) if vals else None


def weather_for_targets(location, targets, as_of, issued_at, weather_obs):
    """Temperature input for each future target date, strictly from data published before issued_at.

    Priority: latest short-term forecast (daily mean of hourly TMP, >= 8 hourly values) ->
    latest mid-term forecast ((min+max)/2) -> climatology -> None.
    -> {date: {"temp_avg": float|None, "basis": str}}
    """
    from weatherdata.models import WeatherForecastPublication

    out = {}
    pubs = {}
    for dtype in ("short_forecast", "mid_temperature"):
        pubs[dtype] = (WeatherForecastPublication.objects
                       .filter(location=location, dataset_type=dtype, issued_at__lte=issued_at,
                               collection_runs__status="succeeded")
                       .order_by("-issued_at").distinct().first())
    short = mid = None
    if pubs["short_forecast"]:
        rows = pd.DataFrame(WeatherDatum.objects.filter(
            forecast_publication=pubs["short_forecast"], variable="temperature", quality_status="valid")
            .values("valid_at", "value_numeric"))
        if not rows.empty:
            rows["date"] = pd.to_datetime(rows.valid_at).dt.tz_convert(KST).dt.tz_localize(None).dt.normalize()
            rows["v"] = rows.value_numeric.astype(float)
            g = rows.groupby("date").v.agg(["mean", "count"])
            short = g[g["count"] >= 8]["mean"]
    if pubs["mid_temperature"]:
        rows = pd.DataFrame(WeatherDatum.objects.filter(
            forecast_publication=pubs["mid_temperature"], quality_status="valid",
            variable__in=["min_temperature", "max_temperature"]).values("valid_at", "variable", "value_numeric"))
        if not rows.empty:
            rows["date"] = pd.to_datetime(rows.valid_at).dt.tz_convert(KST).dt.tz_localize(None).dt.normalize()
            rows["v"] = rows.value_numeric.astype(float)
            p = rows.pivot_table(index="date", columns="variable", values="v", aggfunc="last")
            if {"min_temperature", "max_temperature"} <= set(p.columns):
                mid = ((p.min_temperature + p.max_temperature) / 2).dropna()
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
