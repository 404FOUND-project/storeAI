from django.contrib.auth import get_user_model
from django.core.management import CommandError, call_command
from django.db import connection
from django.test import TestCase, override_settings
from django.test.utils import CaptureQueriesContext
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
import queue
import socket
import ssl
from io import StringIO
import json
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request
from zoneinfo import ZoneInfo

from store.models import Store
from weatherdata.models import (
    WeatherCollectionRun,
    WeatherDatum,
    WeatherForecastPublication,
    WeatherLocation,
)
from weatherdata.services import short_forecast
from weatherdata.services.short_forecast import (
    ForecastCollectionError,
    ParsedForecast,
    collect_short_forecast,
)


class WeatherLocationMidRegionTests(TestCase):
    def test_mid_temperature_and_land_regions_are_stored_separately(self):
        owner = get_user_model().objects.create_user(username="weather-region-test")
        store = Store.objects.create(owner=owner, name="weather-region-test-store")

        location = WeatherLocation.objects.create(
            store=store,
            latitude="37.55893207501813",
            longitude="127.04045190481105",
            asos_station_id="108",
            forecast_nx=61,
            forecast_ny=127,
            mid_temp_region_id="11B10101",
            mid_land_region_id="11B00000",
        )

        stored = WeatherLocation.objects.get(pk=location.pk)
        self.assertEqual(stored.mid_temp_region_id, "11B10101")
        self.assertEqual(stored.mid_land_region_id, "11B00000")
        self.assertNotEqual(stored.mid_temp_region_id, stored.mid_land_region_id)

    def test_legacy_single_region_field_is_removed_from_model(self):
        field_names = {field.name for field in WeatherLocation._meta.fields}

        self.assertIn("mid_temp_region_id", field_names)
        self.assertIn("mid_land_region_id", field_names)
        self.assertNotIn("mid_forecast_region_id", field_names)


class ShortForecastCollectionTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="short-forecast-test")
        store = Store.objects.create(owner=owner, name="short-forecast-test-store")
        self.location = WeatherLocation.objects.create(
            store=store,
            latitude="37.55893207501813",
            longitude="127.04045190481105",
            asos_station_id="108",
            forecast_nx=61,
            forecast_ny=127,
        )
        self.issue_at = datetime(2026, 11, 10, 8, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        # Transient failures are now retried with a wait; never really sleep in tests.
        sleep_patcher = patch.object(short_forecast, "_sleep")
        self.sleep = sleep_patcher.start()
        self.addCleanup(sleep_patcher.stop)

    @staticmethod
    def response(items, *, code="00", total_count=None):
        return {
            "response": {
                "header": {"resultCode": code, "resultMsg": "NORMAL_SERVICE" if code == "00" else "ERROR"},
                "body": {
                    "totalCount": len(items) if total_count is None else total_count,
                    "items": {"item": items},
                },
            }
        }

    @staticmethod
    def transport_for(payload, status=200):
        return Mock(return_value=(status, json.dumps(payload).encode("utf-8")))

    def test_success_persists_target_times_and_source_issue_separately(self):
        payload = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
            {"category": "POP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "20"},
            {"category": "PCP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "강수없음"},
            {"category": "SKY", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "1"},
        ])
        transport = self.transport_for(payload)
        run = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="mock-secret",
            transport=transport,
        )
        self.assertEqual(run.status, WeatherCollectionRun.Status.SUCCEEDED)
        self.assertEqual(run.http_status, 200)
        self.assertEqual(run.issued_at, self.issue_at)
        temperature = run.data.get(variable="temperature")
        self.assertEqual(temperature.valid_at, datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")))
        self.assertEqual(temperature.value_numeric, Decimal("8.5"))
        self.assertEqual(run.data.get(variable="precipitation_amount").value_text, "강수없음")
        self.assertNotIn("mock-secret", str(run.request_parameters))
        self.assertEqual(run.record_count, 4)
        query = parse_qs(urlsplit(transport.call_args.args[0].full_url).query)
        self.assertEqual(query["nx"], ["61"])
        self.assertEqual(query["ny"], ["127"])
        self.assertEqual(query["base_date"], ["20261110"])
        self.assertEqual(query["base_time"], ["0800"])
        self.assertEqual(transport.call_args.kwargs["connect_timeout"], short_forecast.CONNECT_TIMEOUT_SECONDS)
        self.assertEqual(transport.call_args.kwargs["response_timeout"], short_forecast.RESPONSE_TIMEOUT_SECONDS)

    def test_same_publication_retry_keeps_attempts_and_deduplicates_data(self):
        first_payload = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
        ])
        second_payload = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "9.5"},
        ])
        first = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(first_payload),
        )
        original = first.data.get()
        original_pk = original.pk
        second = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(second_payload),
        )
        original.refresh_from_db()
        self.assertEqual(first.forecast_publication_id, second.forecast_publication_id)
        self.assertEqual(WeatherCollectionRun.objects.count(), 2)
        self.assertEqual(WeatherForecastPublication.objects.count(), 1)
        self.assertEqual(WeatherDatum.objects.count(), 1)
        self.assertEqual(original.pk, original_pk)
        self.assertEqual(original.value_numeric, Decimal("9.5"))
        self.assertEqual(original.collection_run_id, second.pk)

    def test_batch_upsert_detects_split_unique_key_collision(self):
        item = {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"}
        payload = self.response([item])
        first = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(payload),
        )
        original = first.data.get()
        original_value = (original.value_numeric, original.collection_run_id)

        def transport_with_conflicting_rows(_request, **_kwargs):
            current_run = WeatherCollectionRun.objects.order_by("-pk").first()
            other_publication = WeatherForecastPublication.objects.create(
                location=self.location,
                dataset_type=WeatherForecastPublication.DatasetType.SHORT_FORECAST,
                issued_at=self.issue_at + timedelta(hours=3),
            )
            # Deliberately create a cross-reference that passes each individual
            # unique key but makes the two upsert keys point at different rows.
            WeatherDatum.objects.create(
                collection_run=current_run,
                forecast_publication=other_publication,
                data_layer=WeatherDatum.DataLayer.RAW,
                valid_at=datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
                variable="temperature",
                period="hourly",
                value_kind=WeatherDatum.ValueKind.NUMERIC,
                value_numeric=Decimal("7.0"),
                value_text="",
                quality_status=WeatherDatum.QualityStatus.VALID,
            )
            return 200, json.dumps(payload).encode("utf-8")

        second = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=transport_with_conflicting_rows,
        )
        original.refresh_from_db()
        self.assertEqual(second.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(second.error_code, "ambiguous_upsert")
        self.assertEqual((original.value_numeric, original.collection_run_id), original_value)

    def test_batch_prevalidation_rejects_invalid_values_and_publication_mismatch(self):
        publication = WeatherForecastPublication.objects.create(
            location=self.location,
            dataset_type=WeatherForecastPublication.DatasetType.SHORT_FORECAST,
            issued_at=self.issue_at,
        )
        run = WeatherCollectionRun.objects.create(
            source_type=WeatherCollectionRun.SourceType.FORECAST,
            forecast_publication=publication,
            status=WeatherCollectionRun.Status.RUNNING,
        )
        invalid_missing_value = ParsedForecast(
            datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
            "temperature", "numeric", None, "", "째C", "TMP", WeatherDatum.QualityStatus.VALID,
        )
        with self.assertRaises(ForecastCollectionError) as invalid_context:
            short_forecast._build_forecast_datum(invalid_missing_value, run, publication)
        self.assertEqual(invalid_context.exception.code, "persistence_validation_error")

        other_publication = WeatherForecastPublication.objects.create(
            location=self.location,
            dataset_type=WeatherForecastPublication.DatasetType.SHORT_FORECAST,
            issued_at=self.issue_at + timedelta(hours=3),
        )
        valid_value = ParsedForecast(
            datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo("Asia/Seoul")),
            "temperature", "numeric", Decimal("8.5"), "", "째C", "TMP", WeatherDatum.QualityStatus.VALID,
        )
        with self.assertRaises(ForecastCollectionError) as mismatch_context:
            short_forecast._build_forecast_datum(valid_value, run, other_publication)
        self.assertEqual(mismatch_context.exception.code, "persistence_validation_error")

    def test_api_error_is_recorded_separately_from_http_error(self):
        run = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x",
            transport=self.transport_for(self.response([], code="03")),
        )
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "api_response_error")
        self.assertEqual(run.api_result_code, "03")
        self.assertEqual(run.http_status, 200)
        self.assertEqual(run.data.count(), 0)

    def test_parse_error_is_recorded_without_writing_partial_data(self):
        payload = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "not-a-number"},
        ])
        run = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(payload),
        )
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "parse_error")
        self.assertEqual(run.data.count(), 0)

    def test_malformed_json_envelope_preserves_http_status(self):
        run = collect_short_forecast(
            self.location,
            base_at=self.issue_at,
            service_key="x",
            transport=self.transport_for({"unexpected": "shape"}, status=200),
        )
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "parse_error")
        self.assertEqual(run.http_status, 200)
        self.assertEqual(run.data.count(), 0)

    def test_missing_numeric_value_remains_null_and_missing(self):
        payload = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "-"},
        ])
        run = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(payload),
        )
        datum = run.data.get()
        self.assertEqual(datum.quality_status, WeatherDatum.QualityStatus.MISSING)
        self.assertIsNone(datum.value_numeric)
        self.assertEqual(datum.value_text, "")

    def test_request_timeout_marks_run_failed_and_keeps_existing_data(self):
        original = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
        ])
        successful_run = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(original),
        )
        existing = successful_run.data.get(variable="temperature")
        before = (existing.value_numeric, existing.collection_run_id)

        timed_out = collect_short_forecast(
            self.location,
            base_at=self.issue_at,
            service_key="x",
            transport=Mock(side_effect=TimeoutError()),
        )
        existing.refresh_from_db()
        self.assertEqual(timed_out.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(timed_out.error_code, "timeout_error")
        self.assertEqual((existing.value_numeric, existing.collection_run_id), before)

    def test_total_deadline_expires_before_another_page_request(self):
        transport = self.transport_for(self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
        ]))
        with patch.object(short_forecast.time, "monotonic", side_effect=[100.0, 100.0 + short_forecast.TOTAL_TIMEOUT_SECONDS + 1]):
            run = collect_short_forecast(
                self.location, base_at=self.issue_at, service_key="x", transport=transport,
            )
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "timeout_error")
        transport.assert_not_called()

    def test_page_limit_is_enforced_without_partial_saves(self):
        initial = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
        ])
        prior_run = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(initial),
        )
        prior_datum = prior_run.data.get(variable="temperature")
        prior_value = (prior_datum.value_numeric, prior_datum.collection_run_id)

        page_item = {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"}
        raw_page = json.dumps(self.response([page_item], total_count=10)).encode("utf-8")
        transport = Mock(return_value=(200, raw_page))
        run = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=transport,
        )
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "page_limit_exceeded")
        self.assertEqual(transport.call_count, short_forecast.MAX_PAGES)
        self.assertEqual(run.data.count(), 0)
        prior_datum.refresh_from_db()
        self.assertEqual((prior_datum.value_numeric, prior_datum.collection_run_id), prior_value)

    def test_keyboard_interrupt_marks_attempt_failed_and_preserves_existing_datum(self):
        initial = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
        ])
        successful_run = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(initial),
        )
        datum = successful_run.data.get(variable="temperature")
        original_value = datum.value_numeric

        with self.assertRaises(KeyboardInterrupt):
            collect_short_forecast(
                self.location,
                base_at=self.issue_at,
                service_key="x",
                transport=Mock(side_effect=KeyboardInterrupt),
            )
        interrupted_run = WeatherCollectionRun.objects.order_by("-pk").first()
        datum.refresh_from_db()
        self.assertEqual(interrupted_run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(interrupted_run.error_code, "interrupted")
        self.assertEqual(datum.value_numeric, original_value)

    def test_keyboard_interrupt_during_publication_creation_leaves_no_running_attempt(self):
        with patch.object(WeatherForecastPublication.objects, "get_or_create", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                collect_short_forecast(self.location, base_at=self.issue_at, service_key="x")
        self.assertEqual(WeatherForecastPublication.objects.count(), 0)
        self.assertEqual(WeatherCollectionRun.objects.count(), 0)

    def test_keyboard_interrupt_during_run_creation_rolls_back_publication(self):
        with patch.object(WeatherCollectionRun.objects, "create", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                collect_short_forecast(self.location, base_at=self.issue_at, service_key="x")
        self.assertEqual(WeatherForecastPublication.objects.count(), 0)
        self.assertEqual(WeatherCollectionRun.objects.count(), 0)

    def test_keyboard_interrupt_during_page_processing_marks_attempt_failed(self):
        with patch.object(short_forecast, "_response_items", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                collect_short_forecast(
                    self.location,
                    base_at=self.issue_at,
                    service_key="x",
                    transport=self.transport_for(self.response([
                        {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
                    ])),
                )
        run = WeatherCollectionRun.objects.get()
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "interrupted")
        self.assertEqual(run.data.count(), 0)

    def test_keyboard_interrupt_during_dns_connect_headers_or_body_marks_failed(self):
        class FakeSocket:
            def settimeout(self, _timeout):
                pass

        class FakeResponse:
            status = 200

            def __init__(self, stage):
                self.stage = stage

            def read1(self, _size):
                if self.stage == "body":
                    raise KeyboardInterrupt
                return b""

        stage_state = {"value": None}

        class FakeConnection:
            def __init__(self, *args, **kwargs):
                self.sock = FakeSocket()

            def connect(self):
                if stage_state["value"] == "https":
                    raise KeyboardInterrupt

            def request(self, *args, **kwargs):
                pass

            def getresponse(self):
                if stage_state["value"] == "headers":
                    raise KeyboardInterrupt
                return FakeResponse(stage_state["value"])

            def close(self):
                pass

        addresses = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))]
        for stage in ("dns", "https", "headers", "body"):
            with self.subTest(stage=stage):
                stage_state["value"] = stage
                resolver_patch = patch.object(
                    short_forecast, "_resolve_host",
                    side_effect=KeyboardInterrupt if stage == "dns" else None,
                    return_value=addresses,
                )
                with (
                    resolver_patch,
                    patch.object(short_forecast, "_ResolvedHTTPSConnection", FakeConnection),
                    self.assertRaises(KeyboardInterrupt),
                ):
                    collect_short_forecast(
                        self.location,
                        base_at=self.issue_at,
                        service_key="x",
                    )
                run = WeatherCollectionRun.objects.order_by("-pk").first()
                self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
                self.assertEqual(run.error_code, "interrupted")
                self.assertEqual(run.data.count(), 0)

    def test_keyboard_interrupt_during_database_batch_rolls_back_all_rows(self):
        payload = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
            {"category": "POP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "20"},
        ])
        with patch.object(WeatherDatum.objects, "bulk_create", side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                collect_short_forecast(
                    self.location,
                    base_at=self.issue_at,
                    service_key="x",
                    transport=self.transport_for(payload),
                )
        run = WeatherCollectionRun.objects.get()
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "interrupted")
        self.assertEqual(WeatherDatum.objects.count(), 0)

    def test_second_upsert_batch_failure_rolls_back_all_batches_and_preserves_prior_data(self):
        prior_payload = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
        ])
        prior_run = collect_short_forecast(
            self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(prior_payload),
        )
        prior_datum = prior_run.data.get()
        prior_value = (prior_datum.value_numeric, prior_datum.collection_run_id)

        items = [
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "9.5"},
        ]
        for offset in range(1, 101):
            valid_date = datetime(2026, 11, 10) + timedelta(days=offset)
            items.append({
                "category": "TMP",
                "fcstDate": valid_date.strftime("%Y%m%d"),
                "fcstTime": "0900",
                "fcstValue": str(8 + offset / 10),
            })
        payload = self.response(items)
        original_bulk_create = WeatherDatum.objects.bulk_create
        batch_sizes = []

        def fail_second_batch(objs, *args, **kwargs):
            batch_sizes.append(len(objs))
            if len(batch_sizes) == 2:
                raise RuntimeError("simulated second batch failure")
            return original_bulk_create(objs, *args, **kwargs)

        with patch.object(WeatherDatum.objects, "bulk_create", side_effect=fail_second_batch):
            failed = collect_short_forecast(
                self.location, base_at=self.issue_at, service_key="x", transport=self.transport_for(payload),
            )
        prior_datum.refresh_from_db()
        self.assertEqual(batch_sizes, [100, 1])
        self.assertEqual(failed.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(failed.error_code, "persistence_error")
        self.assertEqual(WeatherDatum.objects.count(), 1)
        self.assertEqual((prior_datum.value_numeric, prior_datum.collection_run_id), prior_value)

    def test_keyboard_interrupt_after_commit_does_not_leave_running_record(self):
        payload = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
        ])
        original_info = short_forecast.logger.info

        def interrupt_after_commit(message, *args, **kwargs):
            if "database save completed" in message:
                raise KeyboardInterrupt
            return original_info(message, *args, **kwargs)

        with patch.object(short_forecast.logger, "info", side_effect=interrupt_after_commit):
            with self.assertRaises(KeyboardInterrupt):
                collect_short_forecast(
                    self.location,
                    base_at=self.issue_at,
                    service_key="x",
                    transport=self.transport_for(payload),
                )
        run = WeatherCollectionRun.objects.get()
        self.assertEqual(run.status, WeatherCollectionRun.Status.SUCCEEDED)
        self.assertEqual(WeatherDatum.objects.count(), 1)

    def test_management_command_prints_info_diagnostics_to_stdout(self):
        payload = self.response([
            {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
        ])
        stdout = StringIO()
        stderr = StringIO()
        real_collector = collect_short_forecast

        def collect_with_mock(location, *, base_at=None):
            return real_collector(
                location,
                base_at=base_at,
                service_key="mock-secret",
                transport=self.transport_for(payload),
            )

        with patch(
            "weatherdata.management.commands.collect_short_forecast.collect_short_forecast",
            side_effect=collect_with_mock,
        ):
            call_command(
                "collect_short_forecast",
                store_id=self.location.store_id,
                base_date="20261110",
                base_time="0800",
                stdout=stdout,
                stderr=stderr,
            )

        output = stdout.getvalue()
        for marker in (
            "KMA short forecast collection started",
            "KMA short forecast request started",
            "KMA short forecast response received",
            "Forecast page processing started",
            "KMA short forecast page processed",
            "database save started",
            "database save completed",
        ):
            self.assertIn(marker, output)
        self.assertNotIn("mock-secret", output)
        self.assertEqual(stderr.getvalue(), "")

    def test_dns_https_and_response_wait_stages_are_logged_without_url(self):
        class FakeSocket:
            def settimeout(self, _timeout):
                pass

        class FakeResponse:
            status = 200

            def read1(self, _size):
                return b""

        class FakeConnection:
            def __init__(self, *args, **kwargs):
                self.sock = FakeSocket()

            def connect(self):
                return None

            def request(self, *args, **kwargs):
                return None

            def getresponse(self):
                return FakeResponse()

            def close(self):
                return None

        fake_addresses = [(short_forecast.socket.AF_INET, short_forecast.socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        request = Request(short_forecast.ENDPOINT + "?serviceKey=do-not-log-this")
        with (
            patch.object(short_forecast.socket, "getaddrinfo", return_value=fake_addresses),
            patch.object(short_forecast, "_ResolvedHTTPSConnection", FakeConnection),
            self.assertLogs("weatherdata.services.short_forecast", level="INFO") as captured,
        ):
            short_forecast._https_transport(
                request,
                connect_timeout=short_forecast.CONNECT_TIMEOUT_SECONDS,
                response_timeout=short_forecast.RESPONSE_TIMEOUT_SECONDS,
                deadline=short_forecast.time.monotonic() + short_forecast.TOTAL_TIMEOUT_SECONDS,
            )

        output = "\n".join(captured.output)
        for marker in (
            "DNS lookup started", "DNS lookup completed", "HTTPS connection started",
            "HTTPS connection completed", "HTTP response wait started", "HTTP response received",
            "HTTP response body read completed",
        ):
            self.assertIn(marker, output)
        self.assertNotIn("do-not-log-this", output)
        self.assertIn("started_at=", output)
        self.assertIn("duration_ms=", output)

    def test_dns_lookup_wait_is_bounded_by_connect_timeout(self):
        address = [(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("127.0.0.1", 443))]
        with (
            patch.object(short_forecast.queue.Queue, "get", side_effect=queue.Empty) as wait_for_dns,
            self.assertRaises(short_forecast.ForecastCollectionError) as caught,
        ):
            short_forecast._resolve_host(
                "api.example.invalid",
                443,
                deadline=short_forecast.time.monotonic() + short_forecast.TOTAL_TIMEOUT_SECONDS,
                resolver=Mock(return_value=address),
            )
        self.assertEqual(caught.exception.code, "timeout_error")
        self.assertEqual(wait_for_dns.call_args.kwargs["timeout"], short_forecast.CONNECT_TIMEOUT_SECONDS)

    def test_https_connect_budget_is_shared_across_multiple_addresses(self):
        clock = [0.0]

        class FakeSocket:
            def __init__(self, connect_result):
                self.connect_result = connect_result
                self.timeouts = []

            def settimeout(self, value):
                self.timeouts.append(value)

            def connect(self, _address):
                if self.connect_result == "refused":
                    clock[0] = 4.5
                    raise ConnectionRefusedError("mock refusal")
                clock[0] = 5.0
                raise TimeoutError("mock connect timeout")

            def close(self):
                pass

        sockets = [FakeSocket("refused"), FakeSocket("timeout")]
        addresses = [
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("192.0.2.1", 443)),
            (socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", ("192.0.2.2", 443)),
        ]
        connection = short_forecast._ResolvedHTTPSConnection(
            "api.example.invalid",
            443,
            timeout=short_forecast.CONNECT_TIMEOUT_SECONDS,
            context=ssl.create_default_context(),
            addresses=addresses,
            connect_deadline=short_forecast.CONNECT_TIMEOUT_SECONDS,
        )
        with (
            patch.object(short_forecast.time, "monotonic", side_effect=lambda: clock[0]),
            patch.object(short_forecast.socket, "socket", side_effect=sockets),
            self.assertRaises(TimeoutError),
        ):
            connection.connect()
        self.assertEqual(sockets[0].timeouts, [5.0])
        self.assertEqual(sockets[1].timeouts, [0.5])

    def test_http_header_reads_use_remaining_total_deadline(self):
        clock = [0.0]

        class SlowHeaderSocket:
            def __init__(self):
                self.payload = bytearray(b"HTTP/1.1 200 OK\r\nContent-Length: 1\r\n\r\nx")
                self.timeouts = []

            def settimeout(self, value):
                self.timeouts.append(value)

            def makefile(self, _mode):
                return self

            def read1(self, size):
                buffer = bytearray(size)
                count = self.recv_into(buffer)
                return bytes(buffer[:count])

            def close(self):
                pass

            def recv_into(self, buffer):
                if not self.payload:
                    return 0
                count = min(len(buffer), len(self.payload), 8)
                buffer[:count] = self.payload[:count]
                del self.payload[:count]
                clock[0] += 0.3
                return count

        sock = SlowHeaderSocket()
        response_class = short_forecast._deadline_response_class(deadline=1.0, response_timeout=10.0)
        response = response_class(sock, method="GET")
        with patch.object(short_forecast.time, "monotonic", side_effect=lambda: clock[0]):
            with self.assertRaises(short_forecast.ForecastCollectionError) as caught:
                response.begin()
        self.assertEqual(caught.exception.code, "timeout_error")
        self.assertTrue(sock.timeouts)
        self.assertGreater(sock.timeouts[0], sock.timeouts[-1])

    def test_http_body_reads_refresh_timeout_and_stop_at_total_deadline(self):
        clock = [0.0]

        class BodySocket:
            def __init__(self):
                self.headers = bytearray(b"HTTP/1.1 200 OK\r\nContent-Length: 8\r\n\r\n")
                self.body = bytearray(b"dataMORE")
                self.timeouts = []

            def settimeout(self, value):
                self.timeouts.append(value)

            def makefile(self, _mode):
                return self

            def read1(self, size):
                buffer = bytearray(size)
                count = self.recv_into(buffer)
                return bytes(buffer[:count])

            def close(self):
                pass

            def recv_into(self, buffer):
                source = self.headers if self.headers else self.body
                if not source:
                    return 0
                count = min(len(buffer), len(source))
                buffer[:count] = source[:count]
                del source[:count]
                if source is self.body:
                    clock[0] += 0.25
                return count

        sock = BodySocket()
        response_class = short_forecast._deadline_response_class(deadline=2.0, response_timeout=10.0)
        response = response_class(sock, method="GET")
        with patch.object(short_forecast.time, "monotonic", side_effect=lambda: clock[0]):
            response.begin()
            self.assertEqual(response.read1(2), b"da")
            self.assertEqual(response.read1(2), b"ta")
            clock[0] = 2.0
            with self.assertRaises(short_forecast.ForecastCollectionError) as caught:
                response.read1(1)
        self.assertEqual(caught.exception.code, "timeout_error")
        self.assertEqual(sock.timeouts[-2:], [2.0, 1.75])
        response.close()


class ShortForecastStabilityTests(TestCase):
    """Diagnostics, bounded retries, separate budgets, redaction and dry-run.

    Everything here uses injected fake transports and the SQLite test database;
    any attempt to reach the real network transport or DNS fails the test.
    """

    SECRET = "SECRET-KEY+/=value123"
    ITEMS = [
        {"category": "TMP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "8.5"},
        {"category": "POP", "fcstDate": "20261110", "fcstTime": "0900", "fcstValue": "20"},
    ]

    def setUp(self):
        owner = get_user_model().objects.create_user(username="stability-test")
        store = Store.objects.create(owner=owner, name="stability-test-store")
        self.location = WeatherLocation.objects.create(
            store=store, latitude="37.55893207501813", longitude="127.04045190481105",
            asos_station_id="108", forecast_nx=61, forecast_ny=127,
        )
        self.issue_at = datetime(2026, 11, 10, 8, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        for target, name in (
            (short_forecast, "_https_transport"),
            (short_forecast.socket, "getaddrinfo"),
        ):
            patcher = patch.object(target, name, side_effect=AssertionError("real network access blocked in tests"))
            patcher.start()
            self.addCleanup(patcher.stop)
        sleeper = patch.object(short_forecast, "_sleep")
        self.sleep = sleeper.start()
        self.addCleanup(sleeper.stop)

    def ok(self, items=None):
        payload = ShortForecastCollectionTests.response(self.ITEMS if items is None else items)
        return 200, json.dumps(payload).encode("utf-8")

    def collect(self, transport, key="mock-secret"):
        return collect_short_forecast(self.location, base_at=self.issue_at, service_key=key, transport=transport)

    # -- defaults -------------------------------------------------------
    def test_defaults_keep_previous_limits_and_cap_retries_at_three(self):
        self.assertEqual(short_forecast.NETWORK_BUDGET_SECONDS, 60)
        self.assertEqual(short_forecast.DB_BUDGET_SECONDS, 60)
        self.assertEqual(short_forecast.TOTAL_TIMEOUT_SECONDS, 60)
        self.assertEqual(short_forecast.CONNECT_TIMEOUT_SECONDS, 5)
        self.assertEqual(short_forecast.RESPONSE_TIMEOUT_SECONDS, 10)
        self.assertEqual(short_forecast.MAX_ATTEMPTS, 3)
        self.assertEqual(short_forecast.RETRY_BACKOFF_SECONDS, (2.0, 5.0))

    # -- retries --------------------------------------------------------
    def test_timeout_then_success_is_retried_and_recorded(self):
        transport = Mock(side_effect=[TimeoutError(), self.ok()])
        run = self.collect(transport)
        self.assertEqual(run.status, WeatherCollectionRun.Status.SUCCEEDED)
        self.assertEqual(transport.call_count, 2)
        self.sleep.assert_called_once_with(2.0)
        run.refresh_from_db()
        diagnostics = run.request_parameters["diagnostics"]
        self.assertEqual(diagnostics["requests"], 2)
        self.assertEqual(diagnostics["retries"][0]["error_code"], "timeout_error")
        self.assertEqual(run.record_count, 2)

    def test_http_5xx_then_success_is_retried(self):
        transport = Mock(side_effect=[(503, b""), self.ok()])
        run = self.collect(transport)
        self.assertEqual(run.status, WeatherCollectionRun.Status.SUCCEEDED)
        self.assertEqual(transport.call_count, 2)

    def test_network_error_then_success_is_retried(self):
        transport = Mock(side_effect=[ConnectionResetError(), self.ok()])
        run = self.collect(transport)
        self.assertEqual(run.status, WeatherCollectionRun.Status.SUCCEEDED)
        self.assertEqual(transport.call_count, 2)

    def test_retries_stop_after_three_attempts_with_backoff_and_diagnostics(self):
        transport = Mock(side_effect=TimeoutError())
        run = self.collect(transport)
        run.refresh_from_db()
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "timeout_error")
        self.assertEqual(transport.call_count, 3)
        self.assertEqual([c.args[0] for c in self.sleep.call_args_list], [2.0, 5.0])
        self.assertIn("stage=request", run.error_message)
        self.assertIn("requests=3", run.error_message)
        diagnostics = run.request_parameters["diagnostics"]
        self.assertEqual(diagnostics["failed_stage"], "request")
        self.assertEqual(len(diagnostics["retries"]), 2)

    def test_persistent_5xx_records_http_status(self):
        transport = Mock(return_value=(500, b""))
        run = self.collect(transport)
        self.assertEqual(run.error_code, "http_error")
        self.assertEqual(run.http_status, 500)
        self.assertEqual(transport.call_count, 3)

    def test_non_transient_failures_are_not_retried(self):
        cases = {
            "http 404": (404, b""),
            "invalid json": (200, b"not json"),
            "auth result code": (200, json.dumps(ShortForecastCollectionTests.response([], code="30")).encode()),
            "parameter result code": (200, json.dumps(ShortForecastCollectionTests.response([], code="10")).encode()),
        }
        for name, response in cases.items():
            with self.subTest(name):
                self.sleep.reset_mock()
                transport = Mock(return_value=response)
                run = self.collect(transport)
                self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
                self.assertEqual(transport.call_count, 1)
                self.sleep.assert_not_called()

    def test_total_deadline_error_is_not_retryable(self):
        with patch.object(short_forecast.time, "monotonic", return_value=10.0):
            with self.assertRaises(ForecastCollectionError) as caught:
                short_forecast._check_deadline(5.0)
        self.assertFalse(caught.exception.retryable)
        transport = Mock(side_effect=ForecastCollectionError("timeout_error", "total", retryable=False))
        self.collect(transport)
        self.assertEqual(transport.call_count, 1)

    @override_settings(WEATHERDATA_NETWORK_BUDGET_SECONDS=1, WEATHERDATA_RETRY_BACKOFF_SECONDS=(5.0, 5.0))
    def test_retry_is_skipped_when_backoff_exceeds_remaining_network_budget(self):
        transport = Mock(side_effect=TimeoutError())
        run = self.collect(transport)
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(transport.call_count, 1)
        self.sleep.assert_not_called()

    @override_settings(WEATHERDATA_MAX_ATTEMPTS=2)
    def test_max_attempts_is_configurable(self):
        transport = Mock(side_effect=TimeoutError())
        self.collect(transport)
        self.assertEqual(transport.call_count, 2)

    # -- budgets --------------------------------------------------------
    @override_settings(WEATHERDATA_DB_BUDGET_SECONDS=0)
    def test_db_budget_is_independent_of_network_budget_and_rolls_back(self):
        run = self.collect(Mock(return_value=self.ok()))
        run.refresh_from_db()
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "timeout_error")
        self.assertIn("stage=db_save", run.error_message)
        self.assertEqual(run.request_parameters["diagnostics"]["failed_stage"], "db_save")
        self.assertEqual(WeatherDatum.objects.count(), 0)

    def test_budgets_are_reported_in_diagnostics(self):
        run = self.collect(Mock(return_value=self.ok()))
        self.assertEqual(run.status, WeatherCollectionRun.Status.SUCCEEDED)
        diagnostics = WeatherCollectionRun.objects.get(pk=run.pk).request_parameters["diagnostics"]
        self.assertEqual(diagnostics["network_budget_seconds"], 60)
        self.assertEqual(diagnostics["db_budget_seconds"], 60)

    # -- diagnostics ----------------------------------------------------
    def test_success_keeps_existing_request_parameters_and_adds_diagnostics(self):
        run = self.collect(Mock(return_value=self.ok()))
        run.refresh_from_db()
        parameters = run.request_parameters
        expected = {
            "base_date": "20261110", "base_time": "0800", "nx": 61, "ny": 127,
            "dataType": "JSON", "numOfRows": 1000, "pages_fetched": 1,
        }
        for key, value in expected.items():
            self.assertEqual(parameters[key], value)
        stages = parameters["diagnostics"]["stage_ms"]
        for name in ("request", "parse", "db_save"):
            self.assertIn(name, stages)
        json.dumps(parameters)  # must stay JSON serializable

    def test_failure_keeps_original_request_parameters(self):
        run = self.collect(Mock(side_effect=TimeoutError()))
        run.refresh_from_db()
        self.assertEqual(run.request_parameters["base_time"], "0800")
        self.assertEqual(run.request_parameters["nx"], 61)
        self.assertIn("diagnostics", run.request_parameters)

    def test_stage_context_keeps_failing_stage_and_timing(self):
        diagnostics = short_forecast._Diagnostics()
        token = short_forecast._diagnostics_var.set(diagnostics)
        try:
            with self.assertRaises(RuntimeError):
                with short_forecast._stage("body_read"):
                    raise RuntimeError("boom")
        finally:
            short_forecast._diagnostics_var.reset(token)
        self.assertEqual(diagnostics.stage, "body_read")
        self.assertIn("body_read", diagnostics.stage_ms)

    def test_dns_timeout_is_labelled_dns_and_retryable(self):
        fake_addresses = [(short_forecast.socket.AF_INET, short_forecast.socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with (
            patch.object(short_forecast.socket, "getaddrinfo", return_value=fake_addresses),
            patch.object(short_forecast.queue.Queue, "get", side_effect=queue.Empty),
            self.assertRaises(ForecastCollectionError) as caught,
        ):
            short_forecast._resolve_host(
                "api.example.invalid", 443, deadline=short_forecast.time.monotonic() + 60,
            )
        self.assertEqual(caught.exception.stage, "dns")
        self.assertTrue(caught.exception.retryable)

    # -- unexpected errors ---------------------------------------------
    def test_unexpected_exception_is_recorded_as_failed_without_leaking_details(self):
        transport = Mock(side_effect=ValueError(f"boom serviceKey={self.SECRET}"))
        run = self.collect(transport, key=self.SECRET)
        run.refresh_from_db()
        self.assertEqual(run.status, WeatherCollectionRun.Status.FAILED)
        self.assertEqual(run.error_code, "unexpected_error")
        self.assertIn("ValueError", run.error_message)
        self.assertNotIn(self.SECRET, run.error_message)
        self.assertFalse(WeatherCollectionRun.objects.filter(status=WeatherCollectionRun.Status.RUNNING).exists())

    # -- secrets --------------------------------------------------------
    def test_service_key_never_appears_in_logs_messages_or_stored_parameters(self):
        from urllib.parse import quote, quote_plus

        def leaky_transport(request, **kwargs):
            short_forecast.logger.warning("leak raw %s", self.SECRET)
            short_forecast.logger.warning("leak encoded %s %s", quote(self.SECRET, safe=""), quote_plus(self.SECRET))
            raise ForecastCollectionError("api_response_error", f"echoed {self.SECRET}")

        with self.assertLogs(short_forecast.logger, level=logging.DEBUG) as logs:
            run = self.collect(leaky_transport, key=self.SECRET)
        run.refresh_from_db()
        captured = "\n".join(logs.output)
        self.assertIn("***", captured)
        for variant in (self.SECRET, quote(self.SECRET, safe=""), quote_plus(self.SECRET)):
            self.assertNotIn(variant, captured)
            self.assertNotIn(variant, run.error_message)
            self.assertNotIn(variant, json.dumps(run.request_parameters))

    # -- dry run --------------------------------------------------------
    def test_dry_run_returns_summary_and_writes_nothing(self):
        result = short_forecast.dry_run_short_forecast(
            self.location, base_at=self.issue_at, service_key="mock-secret", transport=Mock(return_value=self.ok()),
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual((result["items"], result["parsed"], result["pages_fetched"]), (2, 2, 1))
        self.assertIn("request", result["diagnostics"]["stage_ms"])
        self.assertEqual(WeatherCollectionRun.objects.count(), 0)
        self.assertEqual(WeatherForecastPublication.objects.count(), 0)
        self.assertEqual(WeatherDatum.objects.count(), 0)

    def test_dry_run_failure_reports_stage_and_retries_without_writing(self):
        transport = Mock(side_effect=TimeoutError())
        result = short_forecast.dry_run_short_forecast(
            self.location, base_at=self.issue_at, service_key="mock-secret", transport=transport,
        )
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "timeout_error")
        self.assertEqual(result["failed_stage"], "request")
        self.assertEqual(transport.call_count, 3)
        self.assertEqual(WeatherCollectionRun.objects.count(), 0)

    def test_dry_run_requires_a_service_key(self):
        with patch.dict(short_forecast.os.environ, {"KMA_SERVICE_KEY": ""}):
            result = short_forecast.dry_run_short_forecast(
                self.location, base_at=self.issue_at, transport=Mock(),
            )
        self.assertEqual(result["error_code"], "configuration_error")

    def test_command_dry_run_does_not_collect_or_save(self):
        real_dry_run = short_forecast.dry_run_short_forecast

        def dry_run_with_mock(location, *, base_at=None):
            return real_dry_run(
                location, base_at=base_at, service_key=self.SECRET, transport=Mock(return_value=self.ok()),
            )

        stdout, stderr = StringIO(), StringIO()
        with (
            patch("weatherdata.management.commands.collect_short_forecast.dry_run_short_forecast",
                  side_effect=dry_run_with_mock),
            patch("weatherdata.management.commands.collect_short_forecast.collect_short_forecast") as collector,
        ):
            call_command(
                "collect_short_forecast", store_id=self.location.store_id, base_date="20261110",
                base_time="0800", dry_run=True, stdout=stdout, stderr=stderr,
            )
        collector.assert_not_called()
        self.assertIn("Dry run succeeded (nothing saved)", stdout.getvalue())
        self.assertNotIn(self.SECRET, stdout.getvalue())
        self.assertEqual(WeatherCollectionRun.objects.count(), 0)
        self.assertEqual(WeatherDatum.objects.count(), 0)

    def test_command_dry_run_failure_exits_with_error_and_stage(self):
        real_dry_run = short_forecast.dry_run_short_forecast

        def dry_run_with_mock(location, *, base_at=None):
            return real_dry_run(
                location, base_at=base_at, service_key="mock-secret", transport=Mock(return_value=(500, b"")),
            )

        stdout, stderr = StringIO(), StringIO()
        with patch("weatherdata.management.commands.collect_short_forecast.dry_run_short_forecast",
                   side_effect=dry_run_with_mock):
            with self.assertRaises(CommandError):
                call_command(
                    "collect_short_forecast", store_id=self.location.store_id, base_date="20261110",
                    base_time="0800", dry_run=True, stdout=stdout, stderr=stderr,
                )
        self.assertIn("stage=response_wait", stderr.getvalue())
        self.assertEqual(WeatherCollectionRun.objects.count(), 0)


class ShortForecastPersistenceQueryTests(TestCase):
    """Guard the DB-save phase against per-row round trips (remote DB latency)."""

    def setUp(self):
        owner = get_user_model().objects.create_user(username="short-forecast-query-test")
        store = Store.objects.create(owner=owner, name="short-forecast-query-test-store")
        self.location = WeatherLocation.objects.create(
            store=store,
            latitude="37.55893207501813",
            longitude="127.04045190481105",
            forecast_nx=61,
            forecast_ny=127,
        )
        self.issue_at = datetime(2026, 11, 10, 8, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        self.publication = WeatherForecastPublication.objects.create(
            location=self.location,
            dataset_type=WeatherForecastPublication.DatasetType.SHORT_FORECAST,
            issued_at=self.issue_at,
        )
        self.run = WeatherCollectionRun.objects.create(
            source_type=WeatherCollectionRun.SourceType.FORECAST,
            forecast_publication=self.publication,
        )

    def parsed(self, hours):
        start = datetime(2026, 11, 10, 9, 0, tzinfo=ZoneInfo("Asia/Seoul"))
        return [
            ParsedForecast(
                start + timedelta(hours=hour), "temperature", "numeric",
                Decimal("1.5"), "", "°C", "TMP", WeatherDatum.QualityStatus.VALID,
            )
            for hour in range(hours)
        ]

    def test_building_datums_issues_no_queries(self):
        values = self.parsed(50)
        with self.assertNumQueries(0):
            datums = [short_forecast._build_forecast_datum(v, self.run, self.publication) for v in values]
        self.assertEqual(len(datums), 50)

    def test_upsert_query_count_does_not_grow_with_row_count(self):
        def count_queries(hours):
            run = WeatherCollectionRun.objects.create(
                source_type=WeatherCollectionRun.SourceType.FORECAST,
                forecast_publication=WeatherForecastPublication.objects.create(
                    location=self.location,
                    dataset_type=WeatherForecastPublication.DatasetType.SHORT_FORECAST,
                    issued_at=self.issue_at + timedelta(days=hours),
                ),
            )
            with CaptureQueriesContext(connection) as queries:
                short_forecast._upsert_forecast_data(
                    self.parsed(hours), run, run.forecast_publication,
                    deadline=time.monotonic() + 60,
                )
            self.assertEqual(WeatherDatum.objects.filter(collection_run=run).count(), hours)
            return len(queries)

        # 100 rows is exactly one upsert batch; 250 rows is three. Only
        # per-batch statements (INSERT, savepoint) may add queries. Per-row
        # existence checks would add ~300 more (2 per extra row).
        small = count_queries(100)
        large = count_queries(250)
        self.assertLessEqual(large - small, 6)
        self.assertLess(large, 30)

    def test_model_clean_still_rejects_run_publication_mismatch(self):
        other_publication = WeatherForecastPublication.objects.create(
            location=self.location,
            dataset_type=WeatherForecastPublication.DatasetType.SHORT_FORECAST,
            issued_at=self.issue_at + timedelta(hours=3),
        )
        with self.assertRaises(ForecastCollectionError) as raised:
            short_forecast._build_forecast_datum(self.parsed(1)[0], self.run, other_publication)
        self.assertEqual(raised.exception.code, "persistence_validation_error")

    def test_field_validation_still_rejects_invalid_values(self):
        bad = self.parsed(1)[0]
        bad = ParsedForecast(
            bad.valid_at, "x" * 60, bad.value_kind, bad.value_numeric, "", bad.unit,
            bad.source_field, bad.quality_status,
        )
        with self.assertRaises(ForecastCollectionError) as raised:
            short_forecast._build_forecast_datum(bad, self.run, self.publication)
        self.assertEqual(raised.exception.code, "persistence_validation_error")

    def test_unsaved_run_or_publication_is_rejected_without_queries(self):
        unsaved_run = WeatherCollectionRun(source_type=WeatherCollectionRun.SourceType.FORECAST)
        with self.assertNumQueries(0):
            with self.assertRaises(ForecastCollectionError) as raised:
                short_forecast._build_forecast_datum(self.parsed(1)[0], unsaved_run, self.publication)
        self.assertEqual(raised.exception.code, "persistence_validation_error")
