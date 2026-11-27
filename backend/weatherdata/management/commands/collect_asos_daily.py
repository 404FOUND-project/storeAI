from datetime import date, timedelta

from django.core.management.base import BaseCommand, CommandError

from weatherdata.services.asos_daily import collect_asos_daily
from weatherdata.services.kma_http import KmaRequestError
from weatherdata.services.short_forecast import get_location_for_store


class Command(BaseCommand):
    help = "Collect ASOS daily observations (temperature, precipitation, humidity, wind) into weatherdata."

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, default=1)
        parser.add_argument("--start", help="YYYY-MM-DD (default: 2025-01-01)")
        parser.add_argument("--end", help="YYYY-MM-DD (default: yesterday)")

    def handle(self, *args, **o):
        loc = get_location_for_store(o["store_id"])
        start = date.fromisoformat(o["start"]) if o["start"] else date(2025, 1, 1)
        end = date.fromisoformat(o["end"]) if o["end"] else date.today() - timedelta(days=1)
        try:
            run, inserted, skipped = collect_asos_daily(loc, start, end)
        except KmaRequestError as exc:
            raise CommandError(f"ASOS collection failed: {exc.code}: {exc}")
        self.stdout.write(f"ASOS run={run.pk} {start}..{end} inserted={inserted} already_stored={skipped}")
