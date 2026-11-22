from django.core.management.base import BaseCommand

from weatherdata.services.asos_daily import import_scenario_temperatures
from weatherdata.services.short_forecast import get_location_for_store


class Command(BaseCommand):
    help = "Store the synthetic Nov-2026 temperature scenario (source_type=scenario, never 'observed')."

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, default=1)
        parser.add_argument("--csv", required=True)

    def handle(self, *a, **o):
        run, n = import_scenario_temperatures(
            get_location_for_store(o["store_id"]), o["csv"], "sales_dummy_nov2026_v1", "v1", 40420261112)
        self.stdout.write("already imported" if run is None else f"scenario run={run.pk} rows={n}")
