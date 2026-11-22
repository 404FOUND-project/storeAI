from datetime import datetime
import logging

from django.core.management.base import BaseCommand, CommandError
from zoneinfo import ZoneInfo

from weatherdata.models import WeatherCollectionRun, WeatherLocation
from weatherdata.services.short_forecast import (
    collect_short_forecast,
    dry_run_short_forecast,
    get_location_for_store,
    latest_available_issue,
)


class Command(BaseCommand):
    help = "Collect KMA village short-term forecast for a store's configured weather location."

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, default=1)
        parser.add_argument("--base-date", help="Issue date in YYYYMMDD; defaults to latest available issue.")
        parser.add_argument("--base-time", help="Issue time in HHMM; defaults to latest available issue.")
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and parse the forecast and print stage timings, without saving anything to the database.",
        )

    def handle(self, *args, **options):
        service_logger = logging.getLogger("weatherdata.services.short_forecast")
        handler = logging.StreamHandler(self.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
        previous_handlers = service_logger.handlers[:]
        previous_level = service_logger.level
        previous_propagate = service_logger.propagate
        service_logger.handlers = [handler]
        service_logger.setLevel(logging.INFO)
        service_logger.propagate = False
        try:
            return self._collect(*args, **options)
        finally:
            service_logger.handlers = previous_handlers
            service_logger.setLevel(previous_level)
            service_logger.propagate = previous_propagate
            handler.close()

    def _collect(self, *args, **options):
        try:
            location = get_location_for_store(options["store_id"])
        except WeatherLocation.DoesNotExist as exc:
            raise CommandError("WeatherLocation was not found for the requested store.") from exc

        if bool(options["base_date"]) != bool(options["base_time"]):
            raise CommandError("Provide both --base-date and --base-time, or neither.")
        if options["base_date"]:
            try:
                issue_at = datetime.strptime(
                    options["base_date"] + options["base_time"], "%Y%m%d%H%M",
                ).replace(tzinfo=ZoneInfo("Asia/Seoul"))
            except ValueError as exc:
                raise CommandError("Invalid issue date/time; use YYYYMMDD and HHMM.") from exc
        else:
            issue_at = latest_available_issue()

        if options.get("dry_run"):
            return self._dry_run(location, issue_at)

        try:
            run = collect_short_forecast(location, base_at=issue_at)
        except KeyboardInterrupt:
            raise CommandError("Collection interrupted; inspect the collection-run record for its final state.") from None
        if run.status == WeatherCollectionRun.Status.SUCCEEDED:
            self.stdout.write(self.style.SUCCESS(
                f"Forecast collection succeeded: run={run.pk}, issued_at={run.issued_at.isoformat()}, "
                f"records={run.record_count}."
            ))
            return
        self.stderr.write(self.style.ERROR(
            f"Forecast collection failed: run={run.pk}, code={run.error_code}, "
            f"http_status={run.http_status or '-'}, api_result_code={run.api_result_code or '-'}, "
            f"message={run.error_message}"
        ))
        raise CommandError("Forecast collection failed; inspect the collection-run record.")

    def _dry_run(self, location, issue_at):
        try:
            result = dry_run_short_forecast(location, base_at=issue_at)
        except KeyboardInterrupt:
            raise CommandError("Dry run interrupted; nothing was saved.") from None
        diagnostics = result.get("diagnostics", {})
        timing = (
            f"elapsed_ms={diagnostics.get('elapsed_ms')}, requests={diagnostics.get('requests')}, "
            f"retries={len(diagnostics.get('retries', []))}, stage_ms={diagnostics.get('stage_ms')}"
        )
        if result["status"] == "ok":
            self.stdout.write(self.style.SUCCESS(
                f"Dry run succeeded (nothing saved): issued_at={result['issued_at']}, "
                f"http_status={result['http_status']}, pages={result['pages_fetched']}, "
                f"items={result['items']}, parsed={result['parsed']}, {timing}"
            ))
            return
        self.stderr.write(self.style.ERROR(
            f"Dry run failed (nothing saved): code={result['error_code']}, stage={result.get('failed_stage')}, "
            f"http_status={result.get('http_status') or '-'}, api_result_code={result.get('api_result_code') or '-'}, "
            f"message={result['error_message']}, {timing}"
        ))
        raise CommandError("Dry run failed; nothing was saved.")
