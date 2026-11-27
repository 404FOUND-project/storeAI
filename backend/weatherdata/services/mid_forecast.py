"""KMA mid-term forecast (days 4-10): temperature (getMidTa) and land (getMidLandFcst)."""
import logging
import os
import re
from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db import transaction

from weatherdata.models import WeatherCollectionRun, WeatherDatum, WeatherForecastPublication
from .kma_http import KmaRequestError, get_json

KST = ZoneInfo("Asia/Seoul")
BASE = "https://apis.data.go.kr/1360000/MidFcstInfoService/"
logger = logging.getLogger(__name__)
PUBLICATION_HOURS = (6, 18)
AVAILABILITY_DELAY_MINUTES = 45


def latest_mid_issue(now=None):
    now = (now or datetime.now(KST)).astimezone(KST) - timedelta(minutes=AVAILABILITY_DELAY_MINUTES)
    for day_offset in (0, -1):
        day = (now + timedelta(days=day_offset)).replace(minute=0, second=0, microsecond=0)
        for hour in sorted(PUBLICATION_HOURS, reverse=True):
            cand = day.replace(hour=hour)
            if cand <= now:
                return cand
    raise AssertionError("unreachable")


def parse_mid_items(dataset_type, item, issued_at):
    """-> list of (valid_date, variable, period, kind, numeric, text, unit, source_field)."""
    out = []
    base_day = issued_at.date()
    for field, value in item.items():
        m = re.fullmatch(r"(taMin|taMax|rnSt|wf)(\d+)(Am|Pm)?", field)
        if not m or value in ("", None):
            continue
        kind, n, half = m.group(1), int(m.group(2)), (m.group(3) or "").lower()
        valid = base_day + timedelta(days=n)
        if dataset_type == "mid_temperature" and kind in ("taMin", "taMax"):
            out.append((valid, "min_temperature" if kind == "taMin" else "max_temperature",
                        "daily", "numeric", Decimal(str(value)), "", "°C", field))
        elif dataset_type == "mid_land" and kind == "rnSt":
            out.append((valid, "precipitation_probability", half or "daily", "numeric",
                        Decimal(str(value)), "", "%", field))
        elif dataset_type == "mid_land" and kind == "wf":
            out.append((valid, "weather_text", half or "daily", "text", None, str(value)[:120], "", field))
    return out


def collect_mid_forecast(location, dataset_type, issued_at=None, *, key=None, getter=get_json):
    """Fetch + store one mid-term publication. Idempotent per (location, dataset, issued_at)."""
    key = key if key is not None else os.environ.get("KMA_SERVICE_KEY", "")
    issued_at = issued_at or latest_mid_issue()
    endpoint, region = {
        "mid_temperature": ("getMidTa", location.mid_temp_region_id),
        "mid_land": ("getMidLandFcst", location.mid_land_region_id),
    }[dataset_type]
    if not region:
        raise KmaRequestError("configuration_error", f"{dataset_type} region id is not configured.")
    publication, _ = WeatherForecastPublication.objects.get_or_create(
        location=location, dataset_type=dataset_type, issued_at=issued_at)
    done = publication.collection_runs.filter(status="succeeded").first()
    if done:
        return done, 0
    run = WeatherCollectionRun.objects.create(
        source_type="forecast", forecast_publication=publication, status="running",
        request_parameters={"endpoint": endpoint, "regId": region, "tmFc": issued_at.strftime("%Y%m%d%H%M")},
    )
    try:
        items, code = getter(BASE + endpoint, {
            "pageNo": 1, "numOfRows": 10, "dataType": "JSON", "regId": region,
            "tmFc": issued_at.strftime("%Y%m%d%H%M")}, key)
        if not items:
            raise KmaRequestError("api_error", "empty response", code)
        rows = parse_mid_items(dataset_type, items[0], issued_at)
        with transaction.atomic():
            WeatherDatum.objects.bulk_create([
                WeatherDatum(
                    collection_run=run, forecast_publication=publication, data_layer="raw",
                    valid_at=datetime(v.year, v.month, v.day, tzinfo=KST), variable=var, period=period,
                    value_kind=kind, value_numeric=num, value_text=text, unit=unit, source_field=field,
                ) for v, var, period, kind, num, text, unit, field in rows
            ], batch_size=500)
            run.status, run.record_count, run.api_result_code = "succeeded", len(rows), code
            run.save(update_fields=["status", "record_count", "api_result_code"])
    except KmaRequestError as exc:
        run.status, run.error_code, run.error_message = "failed", exc.code, str(exc)[:500]
        run.api_result_code = exc.result_code
        run.save(update_fields=["status", "error_code", "error_message", "api_result_code"])
    return run, run.record_count
