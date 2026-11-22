from django.core.management.base import BaseCommand

from weatherdata.services.mid_forecast import collect_mid_forecast
from weatherdata.services.short_forecast import get_location_for_store


class Command(BaseCommand):
    help = "Collect KMA mid-term (day 4-10) temperature and land forecasts."

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, default=1)

    def handle(self, *args, **o):
        loc = get_location_for_store(o["store_id"])
        for dataset in ("mid_temperature", "mid_land"):
            try:
                run, _ = collect_mid_forecast(loc, dataset)
                self.stdout.write(
                    f"{dataset}: run={run.pk} status={run.status} records={run.record_count} "
                    f"issued_at={run.forecast_publication.issued_at:%Y-%m-%d %H:%M} {run.error_code}")
            except Exception as exc:  # keep the other dataset going
                self.stderr.write(f"{dataset}: failed ({type(exc).__name__}: {exc})")
