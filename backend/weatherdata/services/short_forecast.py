"""KMA village short-term forecast collection service.

This module only performs network requests when ``collect_short_forecast`` is
explicitly called (for example through the management command). Tests inject a
mock transport and never contact the KMA API.
"""

from __future__ import annotations

import json
import http.client
import io
import logging
import os
import queue
import socket
import ssl
import time
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.request import Request
from zoneinfo import ZoneInfo

from django.core.exceptions import ValidationError
from django.db import connections, transaction
from django.db.models import Q
from django.utils import timezone

from weatherdata.models import (
    WeatherCollectionRun,
    WeatherDatum,
    WeatherForecastPublication,
    WeatherLocation,
)


KST = ZoneInfo("Asia/Seoul")
ENDPOINT = "https://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst"
ISSUE_HOURS = (2, 5, 8, 11, 14, 17, 20, 23)
AVAILABILITY_DELAY_MINUTES = 10
PAGE_SIZE = 1000
TOTAL_TIMEOUT_SECONDS = 60
CONNECT_TIMEOUT_SECONDS = 5
RESPONSE_TIMEOUT_SECONDS = 10
MAX_PAGES = 5
UPSERT_BATCH_SIZE = 100
RESPONSE_CHUNK_SIZE = 64 * 1024
logger = logging.getLogger(__name__)

# Raw KMA category -> stable internal variable, value representation, and unit.
CATEGORY_FIELDS = {
    "TMP": ("temperature", "numeric", "°C"),
    "POP": ("precipitation_probability", "numeric", "%"),
    "PCP": ("precipitation_amount", "text", "mm"),
    "SKY": ("sky_condition", "text", ""),
    "PTY": ("precipitation_type", "text", ""),
}


class ForecastCollectionError(Exception):
    """Safe, structured error suitable for storing in collection-run history."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        http_status: int | None = None,
        api_result_code: str = "",
    ) -> None:
        super().__init__(message)
        self.code = code
        self.safe_message = message
        self.http_status = http_status
        self.api_result_code = api_result_code


@dataclass(frozen=True)
class ParsedForecast:
    valid_at: datetime
    variable: str
    value_kind: str
    value_numeric: Decimal | None
    value_text: str
    unit: str
    source_field: str
    quality_status: str
    quality_note: str = ""


def latest_available_issue(now: datetime | None = None) -> datetime:
    """Return the most recent scheduled issue time after the 10-minute delay."""
    current = now or timezone.now()
    if timezone.is_naive(current):
        current = timezone.make_aware(current, KST)
    current = current.astimezone(KST) - timedelta(minutes=AVAILABILITY_DELAY_MINUTES)
    for hour in reversed(ISSUE_HOURS):
        candidate = current.replace(hour=hour, minute=0, second=0, microsecond=0)
        if candidate <= current:
            return candidate
    previous_day = current.date() - timedelta(days=1)
    return datetime.combine(previous_day, datetime.min.time(), tzinfo=KST).replace(hour=23)


def _as_kst_datetime(date_value: str, time_value: str) -> datetime:
    try:
        parsed = datetime.strptime(f"{date_value}{time_value}", "%Y%m%d%H%M")
    except (TypeError, ValueError) as exc:
        raise ForecastCollectionError("parse_error", "Invalid forecast date or time in API response.") from exc
    return parsed.replace(tzinfo=KST)


def _response_items(payload: Any, http_status: int) -> tuple[list[dict[str, Any]], int, str]:
    if not isinstance(payload, dict):
        raise ForecastCollectionError(
            "parse_error", "API response root must be a JSON object.", http_status=http_status,
        )
    response = payload.get("response")
    if not isinstance(response, dict):
        raise ForecastCollectionError(
            "parse_error", "API response envelope is missing.", http_status=http_status,
        )
    header = response.get("header")
    if not isinstance(header, dict):
        raise ForecastCollectionError(
            "parse_error", "API response header is missing.", http_status=http_status,
        )
    result_code = str(header.get("resultCode", ""))
    result_message = str(header.get("resultMsg", ""))[:200]
    if result_code != "00":
        raise ForecastCollectionError(
            "api_response_error",
            "KMA returned an API error response.",
            http_status=http_status,
            api_result_code=result_code,
        )
    body = response.get("body")
    if not isinstance(body, dict):
        raise ForecastCollectionError("parse_error", "API response body is missing.", http_status=http_status, api_result_code=result_code)
    raw_container = body.get("items", {})
    if raw_container is None:
        raw_container = {}
    if not isinstance(raw_container, dict):
        raise ForecastCollectionError("parse_error", "API response items container is invalid.", http_status=http_status, api_result_code=result_code)
    raw_items = raw_container.get("item", [])
    if raw_items is None or raw_items == "":
        items: list[dict[str, Any]] = []
    elif isinstance(raw_items, dict):
        items = [raw_items]
    elif isinstance(raw_items, list) and all(isinstance(item, dict) for item in raw_items):
        items = raw_items
    else:
        raise ForecastCollectionError("parse_error", "API response items have an invalid structure.", http_status=http_status, api_result_code=result_code)
    try:
        total_count = int(body.get("totalCount", len(items)))
    except (TypeError, ValueError) as exc:
        raise ForecastCollectionError("parse_error", "API response totalCount is invalid.", http_status=http_status, api_result_code=result_code) from exc
    return items, total_count, result_code


def _check_deadline(deadline: float) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ForecastCollectionError(
            "timeout_error", "Short forecast collection exceeded its total time limit.",
        )
    return remaining


def _remaining_until(deadline: float, message: str) -> float:
    remaining = deadline - time.monotonic()
    if remaining <= 0:
        raise ForecastCollectionError("timeout_error", message)
    return remaining


def _timestamp() -> str:
    return datetime.now(KST).isoformat(timespec="milliseconds")


def _resolve_host(host: str, port: int, *, deadline: float, resolver=None):
    """Resolve DNS in a daemon worker so a stalled system resolver cannot hold the command forever."""
    started_at = _timestamp()
    started = time.monotonic()
    logger.info("DNS lookup started (host=%s, started_at=%s)", host, started_at)
    result_queue: queue.Queue[tuple[bool, Any]] = queue.Queue(maxsize=1)
    resolve_addresses = resolver or socket.getaddrinfo

    def resolve():
        try:
            result_queue.put_nowait((True, resolve_addresses(host, port, type=socket.SOCK_STREAM)))
        except Exception as exc:
            try:
                result_queue.put_nowait((False, exc))
            except queue.Full:
                pass

    threading.Thread(target=resolve, name="weatherdata-kma-dns", daemon=True).start()
    wait_seconds = min(CONNECT_TIMEOUT_SECONDS, _check_deadline(deadline))
    try:
        succeeded, value = result_queue.get(timeout=wait_seconds)
    except queue.Empty:
        duration_ms = int((time.monotonic() - started) * 1000)
        logger.warning("DNS lookup timed out (host=%s, started_at=%s, duration_ms=%d)", host, started_at, duration_ms)
        raise ForecastCollectionError("timeout_error", "DNS lookup exceeded its time limit.") from None
    duration_ms = int((time.monotonic() - started) * 1000)
    if not succeeded:
        logger.warning(
            "DNS lookup failed (host=%s, started_at=%s, duration_ms=%d, error_type=%s)",
            host, started_at, duration_ms, type(value).__name__,
        )
        raise ForecastCollectionError("network_error", "Could not resolve the KMA API host.") from None
    if not value:
        logger.warning("DNS lookup returned no addresses (host=%s, started_at=%s, duration_ms=%d)", host, started_at, duration_ms)
        raise ForecastCollectionError("network_error", "DNS lookup returned no addresses.")
    logger.info(
        "DNS lookup completed (host=%s, started_at=%s, duration_ms=%d, address_count=%d)",
        host, started_at, duration_ms, len(value),
    )
    return value


class _ResolvedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPSConnection using addresses already resolved under the collection deadline."""

    def __init__(self, *args, addresses, connect_deadline: float, **kwargs):
        super().__init__(*args, **kwargs)
        self.addresses = addresses
        self.connect_deadline = connect_deadline

    def connect(self):
        last_error = None
        for family, socktype, proto, _canonname, sockaddr in self.addresses:
            remaining = _remaining_until(self.connect_deadline, "HTTPS connection exceeded its 5-second time limit.")
            raw_socket = socket.socket(family, socktype, proto)
            try:
                raw_socket.settimeout(min(self.timeout, remaining))
                raw_socket.connect(sockaddr)
                remaining = _remaining_until(self.connect_deadline, "HTTPS connection exceeded its 5-second time limit.")
                raw_socket.settimeout(min(self.timeout, remaining))
                self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
                _remaining_until(self.connect_deadline, "HTTPS connection exceeded its 5-second time limit.")
                return
            except OSError as exc:
                last_error = exc
                raw_socket.close()
            except BaseException:
                raw_socket.close()
                raise
        if last_error is not None:
            raise last_error
        raise OSError("No usable address for the KMA API host")


class _DeadlineSocketReader(io.RawIOBase):
    """File adapter that refreshes socket timeout and total deadline per read."""

    def __init__(self, sock, *, deadline: float, response_timeout: float):
        super().__init__()
        self.sock = sock
        self.file = sock.makefile("rb")
        self.deadline = deadline
        self.response_timeout = response_timeout

    def readable(self):
        return True

    def readinto(self, buffer):
        if not buffer:
            return 0
        remaining = _check_deadline(self.deadline)
        self.sock.settimeout(min(self.response_timeout, remaining))
        data = self.file.read1(len(buffer))
        if not data:
            return 0
        buffer[:len(data)] = data
        return len(data)

    def close(self):
        try:
            self.file.close()
        finally:
            super().close()


class _DeadlineSocketAdapter:
    def __init__(self, sock, *, deadline: float, response_timeout: float):
        self.sock = sock
        self.deadline = deadline
        self.response_timeout = response_timeout

    def makefile(self, mode="rb", buffering=None):
        if mode != "rb":
            raise ValueError("KMA HTTP response reader only supports binary read mode")
        raw = _DeadlineSocketReader(
            self.sock,
            deadline=self.deadline,
            response_timeout=self.response_timeout,
        )
        return io.BufferedReader(raw, buffer_size=io.DEFAULT_BUFFER_SIZE)


def _deadline_response_class(deadline: float, response_timeout: float):
    class DeadlineHTTPResponse(http.client.HTTPResponse):
        def __init__(self, sock, method=None):
            adapter = _DeadlineSocketAdapter(sock, deadline=deadline, response_timeout=response_timeout)
            super().__init__(adapter, method=method)

    return DeadlineHTTPResponse


def parse_forecast_items(items: list[dict[str, Any]]) -> list[ParsedForecast]:
    """Normalize only the weather categories used by storeAI; retain missingness."""
    normalized: dict[tuple[datetime, str], ParsedForecast] = {}
    try:
        for item in items:
            category = str(item["category"])
            if category not in CATEGORY_FIELDS:
                continue
            valid_at = _as_kst_datetime(str(item["fcstDate"]), str(item["fcstTime"]))
            variable, value_kind, unit = CATEGORY_FIELDS[category]
            raw_value = item.get("fcstValue")
            if raw_value is None or str(raw_value).strip() in {"", "-"}:
                parsed = ParsedForecast(
                    valid_at, variable, value_kind, None, "", unit, category,
                    WeatherDatum.QualityStatus.MISSING, "KMA forecast value was empty or missing.",
                )
            elif value_kind == "numeric":
                try:
                    numeric = Decimal(str(raw_value))
                except (InvalidOperation, ValueError) as exc:
                    raise ForecastCollectionError(
                        "parse_error", f"Invalid numeric value for KMA category {category}.",
                    ) from exc
                if not numeric.is_finite():
                    raise ForecastCollectionError(
                        "parse_error", f"Non-finite numeric value for KMA category {category}.",
                    )
                parsed = ParsedForecast(
                    valid_at, variable, value_kind, numeric, "", unit, category,
                    WeatherDatum.QualityStatus.VALID,
                )
            else:
                parsed = ParsedForecast(
                    valid_at, variable, value_kind, None, str(raw_value)[:120], unit, category,
                    WeatherDatum.QualityStatus.VALID,
                )
            key = (valid_at, variable)
            prior = normalized.get(key)
            if prior is not None and prior != parsed:
                raise ForecastCollectionError(
                    "parse_error", f"Conflicting duplicate values for KMA category {category}.",
                )
            normalized[key] = parsed
    except ForecastCollectionError:
        raise
    except (KeyError, TypeError) as exc:
        raise ForecastCollectionError("parse_error", "An API item is missing required fields.") from exc
    if not normalized:
        raise ForecastCollectionError("parse_error", "API response contained no supported forecast values.")
    return list(normalized.values())


def _request_page(
    parameters: dict[str, str | int],
    service_key: str,
    *,
    deadline: float,
    page: int,
    transport=None,
) -> tuple[dict[str, Any], int]:
    query = urlencode({**parameters, "serviceKey": service_key})
    request = Request(f"{ENDPOINT}?{query}", headers={"Accept": "application/json"})
    remaining = _check_deadline(deadline)
    connect_timeout = min(CONNECT_TIMEOUT_SECONDS, remaining)
    response_timeout = min(RESPONSE_TIMEOUT_SECONDS, remaining)
    request_started_at = _timestamp()
    logger.info(
        "KMA short forecast request started (page=%d, started_at=%s, base_date=%s, base_time=%s, nx=%s, ny=%s)",
        page, request_started_at, parameters["base_date"], parameters["base_time"], parameters["nx"], parameters["ny"],
    )
    request_started = time.monotonic()
    try:
        if transport is None:
            status, raw = _https_transport(
                request,
                connect_timeout=connect_timeout,
                response_timeout=response_timeout,
                deadline=deadline,
            )
        else:
            status, raw = transport(
                request,
                connect_timeout=connect_timeout,
                response_timeout=response_timeout,
                deadline=deadline,
            )
    except (TimeoutError, socket.timeout):
        logger.warning(
            "KMA short forecast request failed (page=%d, started_at=%s, duration_ms=%d, error_type=TimeoutError)",
            page, request_started_at, int((time.monotonic() - request_started) * 1000),
        )
        raise ForecastCollectionError("timeout_error", "KMA request exceeded a connection or response timeout.") from None
    except (OSError, http.client.HTTPException) as exc:
        logger.warning(
            "KMA short forecast request failed (page=%d, started_at=%s, duration_ms=%d, error_type=%s)",
            page, request_started_at, int((time.monotonic() - request_started) * 1000), type(exc).__name__,
        )
        raise ForecastCollectionError("network_error", "Could not reach the KMA forecast API.") from None
    _check_deadline(deadline)
    logger.info(
        "KMA short forecast response received (page=%d, started_at=%s, http_status=%d, duration_ms=%d)",
        page, request_started_at, int(status), int((time.monotonic() - request_started) * 1000),
    )
    if status < 200 or status >= 300:
        raise ForecastCollectionError("http_error", "KMA returned a non-success HTTP status.", http_status=status)
    try:
        payload = json.loads(raw.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ForecastCollectionError("parse_error", "KMA response was not valid JSON.", http_status=status) from None
    return payload, status


def _https_transport(
    request: Request,
    *,
    connect_timeout: float,
    response_timeout: float,
    deadline: float,
) -> tuple[int, bytes]:
    """HTTPS transport with separate connect/read timeouts and a total deadline."""
    parsed_url = urlsplit(request.full_url)
    if parsed_url.scheme != "https" or not parsed_url.hostname:
        raise OSError("KMA endpoint must use HTTPS")
    addresses = _resolve_host(parsed_url.hostname, parsed_url.port or 443, deadline=deadline)
    connect_started_at = _timestamp()
    connect_started = time.monotonic()
    connect_deadline = min(deadline, connect_started + connect_timeout)
    connection = _ResolvedHTTPSConnection(
        parsed_url.hostname,
        parsed_url.port or 443,
        timeout=connect_timeout,
        context=ssl.create_default_context(),
        addresses=addresses,
        connect_deadline=connect_deadline,
    )
    try:
        logger.info("HTTPS connection started (started_at=%s)", connect_started_at)
        try:
            connection.connect()
        except BaseException as exc:
            logger.warning(
                "HTTPS connection failed (started_at=%s, duration_ms=%d, error_type=%s)",
                connect_started_at, int((time.monotonic() - connect_started) * 1000), type(exc).__name__,
            )
            raise
        logger.info(
            "HTTPS connection completed (started_at=%s, duration_ms=%d)",
            connect_started_at, int((time.monotonic() - connect_started) * 1000),
        )
        remaining = _check_deadline(deadline)
        if connection.sock is None:
            raise OSError("HTTPS connection has no socket")
        connection.sock.settimeout(min(response_timeout, remaining))
        path = parsed_url.path or "/"
        if parsed_url.query:
            path = f"{path}?{parsed_url.query}"
        connection.request(request.get_method(), path, headers=dict(request.header_items()))
        remaining = _check_deadline(deadline)
        connection.sock.settimeout(min(response_timeout, remaining))
        connection.response_class = _deadline_response_class(deadline, response_timeout)
        response_started_at = _timestamp()
        response_started = time.monotonic()
        logger.info("HTTP response wait started (started_at=%s)", response_started_at)
        try:
            response = connection.getresponse()
        except BaseException as exc:
            logger.warning(
                "HTTP response wait failed (started_at=%s, duration_ms=%d, error_type=%s)",
                response_started_at, int((time.monotonic() - response_started) * 1000), type(exc).__name__,
            )
            raise
        logger.info(
            "HTTP response received (started_at=%s, duration_ms=%d, http_status=%d)",
            response_started_at, int((time.monotonic() - response_started) * 1000), response.status,
        )
        body_started_at = _timestamp()
        body_started = time.monotonic()
        logger.info("HTTP response body read started (started_at=%s)", body_started_at)
        chunks: list[bytes] = []
        try:
            while True:
                remaining = _check_deadline(deadline)
                chunk = response.read1(RESPONSE_CHUNK_SIZE)
                if not chunk:
                    break
                chunks.append(chunk)
            _check_deadline(deadline)
        except BaseException as exc:
            logger.warning(
                "HTTP response body read failed (started_at=%s, duration_ms=%d, error_type=%s)",
                body_started_at, int((time.monotonic() - body_started) * 1000), type(exc).__name__,
            )
            raise
        logger.info(
            "HTTP response body read completed (started_at=%s, duration_ms=%d, bytes=%d)",
            body_started_at, int((time.monotonic() - body_started) * 1000), sum(map(len, chunks)),
        )
        return int(response.status), b"".join(chunks)
    finally:
        connection.close()


def _fetch_all_items(
    base_at: datetime,
    nx: int,
    ny: int,
    service_key: str,
    *,
    deadline: float,
    transport=None,
):
    parameters: dict[str, str | int] = {
        "numOfRows": PAGE_SIZE,
        "pageNo": 1,
        "dataType": "JSON",
        "base_date": base_at.strftime("%Y%m%d"),
        "base_time": base_at.strftime("%H%M"),
        "nx": nx,
        "ny": ny,
    }
    all_items: list[dict[str, Any]] = []
    page = 1
    final_status = 200
    result_code = ""
    while True:
        if page > MAX_PAGES:
            raise ForecastCollectionError(
                "page_limit_exceeded", f"KMA response exceeded the maximum of {MAX_PAGES} pages.",
            )
        _check_deadline(deadline)
        parameters["pageNo"] = page
        payload, final_status = _request_page(
            parameters, service_key, deadline=deadline, page=page, transport=transport,
        )
        page_started_at = _timestamp()
        page_started = time.monotonic()
        logger.info("Forecast page processing started (page=%d, started_at=%s)", page, page_started_at)
        try:
            page_items, total_count, result_code = _response_items(payload, final_status)
        except ForecastCollectionError as error:
            logger.warning(
                "Forecast page processing failed (page=%d, started_at=%s, duration_ms=%d, error_code=%s)",
                page, page_started_at, int((time.monotonic() - page_started) * 1000), error.code,
            )
            raise
        all_items.extend(page_items)
        logger.info(
            "KMA short forecast page processed (page=%d, started_at=%s, duration_ms=%d, page_items=%d, collected_items=%d, total_count=%d)",
            page, page_started_at, int((time.monotonic() - page_started) * 1000), len(page_items), len(all_items), total_count,
        )
        if not page_items or len(all_items) >= total_count:
            break
        if page >= MAX_PAGES:
            raise ForecastCollectionError(
                "page_limit_exceeded", f"KMA response exceeded the maximum of {MAX_PAGES} pages.",
                http_status=final_status, api_result_code=result_code,
            )
        page += 1
    return all_items, final_status, result_code, {
        "base_date": parameters["base_date"],
        "base_time": parameters["base_time"],
        "nx": nx,
        "ny": ny,
        "dataType": "JSON",
        "numOfRows": PAGE_SIZE,
        "pages_fetched": page,
    }


def _mark_failed(run: WeatherCollectionRun, error: ForecastCollectionError) -> None:
    run.status = WeatherCollectionRun.Status.FAILED
    run.error_code = error.code
    run.error_message = error.safe_message
    if error.http_status is not None:
        run.http_status = error.http_status
    if error.api_result_code:
        run.api_result_code = error.api_result_code
    run.save(update_fields=("status", "error_code", "error_message", "http_status", "api_result_code"))
    logger.warning(
        "KMA short forecast collection failed (run_id=%s, error_code=%s, http_status=%s, api_result_code=%s)",
        run.pk, error.code, error.http_status, error.api_result_code,
    )


def _build_forecast_datum(
    value: ParsedForecast,
    run: WeatherCollectionRun,
    publication: WeatherForecastPublication,
) -> WeatherDatum:
    """Build and validate a datum without per-row database constraint queries."""
    datum = WeatherDatum(
        collection_run=run,
        forecast_publication=publication,
        data_layer=WeatherDatum.DataLayer.RAW,
        valid_at=value.valid_at,
        variable=value.variable,
        period="hourly",
        value_kind=value.value_kind,
        value_numeric=value.value_numeric,
        value_text=value.value_text,
        unit=value.unit,
        source_field=value.source_field,
        quality_status=value.quality_status,
        quality_note=value.quality_note,
    )

    has_numeric = datum.value_numeric is not None
    has_text = bool(datum.value_text)
    if datum.quality_status in {
        WeatherDatum.QualityStatus.MISSING,
        WeatherDatum.QualityStatus.NOT_APPLICABLE,
    }:
        values_valid = not has_numeric and not has_text
    elif datum.quality_status in {
        WeatherDatum.QualityStatus.VALID,
        WeatherDatum.QualityStatus.ESTIMATED,
        WeatherDatum.QualityStatus.SUSPECT,
    }:
        values_valid = (
            datum.value_kind == WeatherDatum.ValueKind.NUMERIC and has_numeric and not has_text
        ) or (
            datum.value_kind == WeatherDatum.ValueKind.TEXT and not has_numeric and has_text
        )
    else:
        values_valid = False
    if not values_valid:
        raise ForecastCollectionError(
            "persistence_validation_error",
            "Forecast value and quality status are inconsistent.",
        )

    try:
        # Field and model clean() checks remain active. Unique and CHECK
        # constraints are enforced by the database during the atomic upsert.
        datum.full_clean(validate_unique=False, validate_constraints=False)
    except ValidationError as exc:
        raise ForecastCollectionError(
            "persistence_validation_error",
            "Forecast data failed model validation.",
        ) from exc
    return datum


def _upsert_forecast_data(
    values: list[ParsedForecast],
    run: WeatherCollectionRun,
    publication: WeatherForecastPublication,
    *,
    deadline: float,
) -> None:
    """Preflight both unique keys, then atomically upsert bounded batches."""
    datums = [_build_forecast_datum(value, run, publication) for value in values]
    keys = [
        (datum.valid_at, datum.variable, datum.period, datum.data_layer)
        for datum in datums
    ]
    if len(set(keys)) != len(keys):
        raise ForecastCollectionError(
            "persistence_validation_error",
            "Forecast response contains duplicate normalized values.",
        )

    existing = WeatherDatum.objects.filter(
        Q(forecast_publication_id=publication.pk) | Q(collection_run_id=run.pk)
    ).select_related("collection_run").only(
        "pk",
        "forecast_publication_id",
        "collection_run_id",
        "collection_run__source_type",
        "collection_run__forecast_publication_id",
        "valid_at",
        "variable",
        "period",
        "data_layer",
    )
    publication_rows: dict[tuple, WeatherDatum] = {}
    run_rows: dict[tuple, WeatherDatum] = {}
    for row in existing:
        key = (row.valid_at, row.variable, row.period, row.data_layer)
        if (
            row.collection_run.source_type != WeatherCollectionRun.SourceType.FORECAST
            or row.collection_run.forecast_publication_id != row.forecast_publication_id
        ):
            raise ForecastCollectionError(
                "ambiguous_upsert",
                "Existing forecast data has inconsistent run and publication references.",
            )
        if row.forecast_publication_id == publication.pk:
            publication_rows[key] = row
        if row.collection_run_id == run.pk:
            run_rows[key] = row

    for key in keys:
        publication_row = publication_rows.get(key)
        run_row = run_rows.get(key)
        if run_row is not None and run_row.forecast_publication_id != publication.pk:
            raise ForecastCollectionError(
                "ambiguous_upsert",
                "The collection-run key conflicts with a different publication row.",
            )
        if publication_row is not None and run_row is not None and publication_row.pk != run_row.pk:
            raise ForecastCollectionError(
                "ambiguous_upsert",
                "Forecast unique keys point to different existing rows.",
            )

    db_connection = connections[run._state.db or "default"]
    if not db_connection.features.supports_update_conflicts:
        raise ForecastCollectionError(
            "persistence_configuration_error",
            "The configured database does not support conflict updates.",
        )

    upsert_options = {}
    if db_connection.features.supports_update_conflicts_with_target:
        upsert_options["unique_fields"] = [
            "forecast_publication",
            "valid_at",
            "variable",
            "period",
            "data_layer",
        ]
    for start in range(0, len(datums), UPSERT_BATCH_SIZE):
        _check_deadline(deadline)
        batch = datums[start : start + UPSERT_BATCH_SIZE]
        WeatherDatum.objects.bulk_create(
            batch,
            batch_size=UPSERT_BATCH_SIZE,
            update_conflicts=True,
            update_fields=[
                "collection_run",
                "value_kind",
                "value_numeric",
                "value_text",
                "unit",
                "source_field",
                "quality_status",
                "quality_note",
            ],
            **upsert_options,
        )
        _check_deadline(deadline)


def collect_short_forecast(
    location: WeatherLocation,
    *,
    base_at: datetime | None = None,
    service_key: str | None = None,
    transport=None,
) -> WeatherCollectionRun:
    """Create an attempt, fetch one publication, and idempotently persist its data."""
    started_at = time.monotonic()
    deadline = started_at + TOTAL_TIMEOUT_SECONDS
    issue_at = base_at or latest_available_issue()
    if timezone.is_naive(issue_at):
        issue_at = issue_at.replace(tzinfo=KST)
    issue_at = issue_at.astimezone(KST).replace(second=0, microsecond=0)
    run = None
    try:
        # Keep publication and attempt creation together so an interrupt during
        # setup cannot leave an orphan publication or a half-created attempt.
        with transaction.atomic():
            publication, _ = WeatherForecastPublication.objects.get_or_create(
                location=location,
                dataset_type=WeatherForecastPublication.DatasetType.SHORT_FORECAST,
                issued_at=issue_at,
            )
            run = WeatherCollectionRun.objects.create(
                source_type=WeatherCollectionRun.SourceType.FORECAST,
                forecast_publication=publication,
                status=WeatherCollectionRun.Status.RUNNING,
                request_parameters={
                    "base_date": issue_at.strftime("%Y%m%d"),
                    "base_time": issue_at.strftime("%H%M"),
                    "nx": location.forecast_nx,
                    "ny": location.forecast_ny,
                    "dataType": "JSON",
                    "numOfRows": PAGE_SIZE,
                },
            )
        return _collect_from_run(
            location,
            issue_at,
            publication,
            run,
            deadline=deadline,
            service_key=service_key,
            transport=transport,
        )
    except KeyboardInterrupt:
        if run is not None:
            try:
                run.refresh_from_db()
            except WeatherCollectionRun.DoesNotExist:
                # Setup was interrupted before its atomic transaction committed.
                pass
            except Exception as exc:
                logger.error(
                    "Could not inspect interrupted collection state (error_type=%s)",
                    type(exc).__name__,
                )
            else:
                if run.status == WeatherCollectionRun.Status.RUNNING:
                    try:
                        _mark_failed(run, ForecastCollectionError(
                            "interrupted", "Collection was interrupted by the operator.",
                        ))
                    except Exception as exc:
                        logger.error(
                            "Could not persist interrupted collection status (run_id=%s, error_type=%s)",
                            run.pk, type(exc).__name__,
                        )
        raise


def _collect_from_run(
    location: WeatherLocation,
    issue_at: datetime,
    publication: WeatherForecastPublication,
    run: WeatherCollectionRun,
    *,
    deadline: float,
    service_key: str | None,
    transport,
) -> WeatherCollectionRun:
    logger.info(
        "KMA short forecast collection started (run_id=%s, started_at=%s, issue_at=%s)",
        run.pk, _timestamp(), issue_at.isoformat(),
    )

    key = service_key if service_key is not None else os.environ.get("KMA_SERVICE_KEY", "")
    if not key:
        error = ForecastCollectionError("configuration_error", "KMA_SERVICE_KEY is not configured.")
        _mark_failed(run, error)
        return run
    if location.forecast_nx is None or location.forecast_ny is None:
        error = ForecastCollectionError("configuration_error", "Forecast grid coordinates are not configured.")
        _mark_failed(run, error)
        return run

    http_status: int | None = None
    result_code = ""
    try:
        items, http_status, result_code, safe_parameters = _fetch_all_items(
            issue_at,
            location.forecast_nx,
            location.forecast_ny,
            key,
            deadline=deadline,
            transport=transport,
        )
        for item in items:
            response_base_date = item.get("baseDate")
            response_base_time = item.get("baseTime")
            if response_base_date and response_base_time:
                response_issue = _as_kst_datetime(str(response_base_date), str(response_base_time))
                if response_issue != issue_at:
                    raise ForecastCollectionError(
                        "parse_error", "API response issue time differs from the requested publication.",
                        http_status=http_status, api_result_code=result_code,
                    )
        parsed = parse_forecast_items(items)
        _check_deadline(deadline)
    except ForecastCollectionError as error:
        if error.http_status is None and http_status is not None and error.code in {"parse_error", "api_response_error"}:
            error = ForecastCollectionError(
                error.code,
                error.safe_message,
                http_status=http_status,
                api_result_code=error.api_result_code or result_code,
            )
        _mark_failed(run, error)
        return run

    db_started_at = _timestamp()
    db_started = time.monotonic()
    logger.info("KMA short forecast database save started (run_id=%s, started_at=%s, records=%d)", run.pk, db_started_at, len(parsed))
    try:
        with transaction.atomic():
            _upsert_forecast_data(parsed, run, publication, deadline=deadline)
            _check_deadline(deadline)
            run.status = WeatherCollectionRun.Status.SUCCEEDED
            run.http_status = http_status
            run.api_result_code = result_code
            run.error_code = ""
            run.error_message = ""
            run.record_count = len(parsed)
            run.request_parameters = safe_parameters
            run.save(update_fields=(
                "status", "http_status", "api_result_code", "error_code", "error_message",
                "record_count", "request_parameters",
            ))
    except ForecastCollectionError as error:
        logger.warning(
            "KMA short forecast database save failed (run_id=%s, started_at=%s, duration_ms=%d, error_code=%s)",
            run.pk, db_started_at, int((time.monotonic() - db_started) * 1000), error.code,
        )
        run.refresh_from_db()
        _mark_failed(run, error)
    except Exception as exc:
        # A transaction rollback leaves no partial data; the attempt remains auditable.
        logger.error(
            "KMA short forecast database save failed (run_id=%s, started_at=%s, duration_ms=%d, error_type=%s)",
            run.pk, db_started_at, int((time.monotonic() - db_started) * 1000), type(exc).__name__,
        )
        run.refresh_from_db()
        _mark_failed(run, ForecastCollectionError("persistence_error", "Could not validate or save forecast data."))
    else:
        logger.info(
            "KMA short forecast database save completed (run_id=%s, started_at=%s, duration_ms=%d, records=%d)",
            run.pk, db_started_at, int((time.monotonic() - db_started) * 1000), len(parsed),
        )
    return run


def get_location_for_store(store_id: int) -> WeatherLocation:
    return WeatherLocation.objects.select_related("store").get(store_id=store_id)
