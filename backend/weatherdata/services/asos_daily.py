"""ASOS daily observations -> weatherdata (observed layer) and scenario temperatures.

Observed values come from the KMA ASOS daily API and are stored as separate
WeatherCollectionRun(source_type=observed). Missing precipitation is stored as
quality_status=missing (never as 0). Rows already stored are never duplicated.
"""
import csv
import logging
import os
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from django.db import transaction

from weatherdata.models import WeatherCollectionRun, WeatherDatum
from .kma_http import get_json

KST = ZoneInfo("Asia/Seoul")
ENDPOINT = "https://apis.data.go.kr/1360000/AsosDalyInfoService/getWthrDataList"
logger = logging.getLogger(__name__)

# API field -> (variable, unit)
FIELDS = {
    "avgTa": ("avg_temperature", "°C"),
    "maxTa": ("max_temperature", "°C"),
    "minTa": ("min_temperature", "°C"),
    "sumRn": ("precipitation", "mm"),
    "avgRhm": ("avg_humidity", "%"),
    "avgWs": ("avg_wind_speed", "m/s"),
}


def _decimal(raw):
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return Decimal(str(raw).strip())
    except InvalidOperation:
        return None


def _midnight(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=KST)


def parse_asos_items(items):
    """-> {date: {variable: Decimal|None}}"""
    out = {}
    for item in items:
        day = date.fromisoformat(item["tm"])
        out[day] = {var: _decimal(item.get(field)) for field, (var, _) in FIELDS.items()}
    return out


def fetch_asos_range(station, start: date, end: date, key, *, getter=get_json):
    """Monthly windows (numOfRows=100) to stay within the API row limit."""
    rows = {}
    cursor = start.replace(day=1)
    while cursor <= end:
        nxt = (cursor.replace(day=28) + timedelta(days=4)).replace(day=1)
        lo, hi = max(start, cursor), min(end, nxt - timedelta(days=1))
        items, _ = getter(ENDPOINT, {
            "pageNo": 1, "numOfRows": 100, "dataType": "JSON", "dataCd": "ASOS", "dateCd": "DAY",
            "startDt": lo.strftime("%Y%m%d"), "endDt": hi.strftime("%Y%m%d"), "stnIds": station,
        }, key)
        rows.update(parse_asos_items(items))
        cursor = nxt
    return rows


def store_observations(location, rows, *, request_parameters):
    """Insert observed rows not already stored. Returns (run, inserted, skipped)."""
    existing = set(
        WeatherDatum.objects.filter(
            collection_run__source_type="observed", collection_run__dataset_type="asos_daily",
            collection_run__location=location, period="daily",
        ).values_list("valid_at", "variable")
    )
    units = {var: unit for var, unit in FIELDS.values()}
    with transaction.atomic():
        run = WeatherCollectionRun.objects.create(
            location=location, source_type="observed", dataset_type="asos_daily",
            status=WeatherCollectionRun.Status.RUNNING, request_parameters=request_parameters,
        )
        data, skipped = [], 0
        for day, values in sorted(rows.items()):
            for var, value in values.items():
                key = (_midnight(day), var)
                if key in existing:
                    skipped += 1
                    continue
                missing = value is None
                data.append(WeatherDatum(
                    collection_run=run, data_layer="raw", valid_at=key[0], variable=var, period="daily",
                    value_kind="numeric", value_numeric=value, unit=units[var],
                    quality_status="missing" if missing else "valid",
                    quality_note="provider returned no value; not assumed to be 0" if missing else "",
                ))
        WeatherDatum.objects.bulk_create(data, batch_size=1000)
        run.record_count = len(data)
        run.status = WeatherCollectionRun.Status.SUCCEEDED
        run.api_result_code = "00"
        run.save(update_fields=["record_count", "status", "api_result_code"])
    return run, len(data), skipped


def collect_asos_daily(location, start: date, end: date, *, key=None, getter=get_json):
    key = key if key is not None else os.environ.get("KMA_SERVICE_KEY", "")
    station = location.asos_station_id
    rows = fetch_asos_range(station, start, end, key, getter=getter)
    return store_observations(location, rows, request_parameters={
        "source": "KMA AsosDalyInfoService/getWthrDataList", "station": station,
        "start": start.isoformat(), "end": end.isoformat(),
    })


def import_scenario_temperatures(location, csv_path, scenario_name, scenario_version, seed):
    """Synthetic temperature scenario used to generate the Nov-2026 dummy sales."""
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = [r for r in csv.DictReader(fh) if r["weather_value_type"] == "synthetic_scenario"]
    if WeatherCollectionRun.objects.filter(source_type="scenario", scenario_name=scenario_name,
                                           scenario_version=scenario_version).exists():
        return None, 0
    with transaction.atomic():
        run = WeatherCollectionRun.objects.create(
            location=location, source_type="scenario", dataset_type="scenario",
            status=WeatherCollectionRun.Status.SUCCEEDED, scenario_name=scenario_name,
            scenario_version=scenario_version, random_seed=seed, record_count=len(rows),
            generation_rule="independent resample of 2025-11 ASOS 108 avg temperature; SYNTHETIC, not observed",
            request_parameters={"source_file": str(csv_path)},
        )
        WeatherDatum.objects.bulk_create([
            WeatherDatum(
                collection_run=run, data_layer="raw", valid_at=_midnight(date.fromisoformat(r["sales_date"])),
                variable="avg_temperature", period="daily", value_kind="numeric",
                value_numeric=Decimal(r["avg_temp_c_scenario"]), unit="°C", quality_status="estimated",
                quality_note="synthetic scenario temperature (not observed)",
            ) for r in rows
        ])
    return run, len(rows)
