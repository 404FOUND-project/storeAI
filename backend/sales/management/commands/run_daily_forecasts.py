from django.core.management.base import BaseCommand, CommandError

from sales.ml.boundary import default_as_of
from sales.ml.forecast_engine import generate_forecasts
from sales.models import ForecastRun
from store.models import Store


class Command(BaseCommand):
    help = "Generate and persist daily 7-day forecasts for all stores."

    def add_arguments(self, parser):
        parser.add_argument(
            "--store-id",
            type=int,
            help="Process only the specified store.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show target stores and skip decisions without generating or saving forecasts.",
        )

    def handle(self, *args, **options):
        as_of = default_as_of()

        stores = Store.objects.order_by("pk")
        if options["store_id"] is not None:
            stores = stores.filter(pk=options["store_id"])

        stores = list(stores)
        if not stores:
            raise CommandError("No matching stores were found.")

        self.stdout.write(f"Forecast 기준일: {as_of}")
        self.stdout.write(f"대상 매장 수: {len(stores)}")

        succeeded = 0
        skipped = 0
        failed = 0

        for store in stores:
            already_completed = ForecastRun.objects.filter(
                store=store,
                as_of=as_of,
                status=ForecastRun.Status.COMPLETED,
            ).exists()

            if already_completed:
                skipped += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"[SKIP] 매장 {store.pk} ({store.name}): "
                        f"{as_of} 기준 완료된 예측 기록이 있음"
                    )
                )
                continue

            if options["dry_run"]:
                self.stdout.write(
                    f"[DRY-RUN] 매장 {store.pk} ({store.name}): 실행 대상"
                )
                continue

            try:
                result = generate_forecasts(
                    store.pk,
                    as_of=as_of,
                    persist=True,
                )
                succeeded += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[SUCCESS] 매장 {store.pk} ({store.name}): "
                        f"run_id={result['run_id']}, "
                        f"기준일={result['as_of']}"
                    )
                )
            except Exception as exc:
                failed += 1
                self.stderr.write(
                    self.style.ERROR(
                        f"[FAILED] 매장 {store.pk} ({store.name}): "
                        f"{type(exc).__name__}: {exc}"
                    )
                )

        if options["dry_run"]:
            self.stdout.write(
                f"Dry-run 완료: 실행 대상={len(stores) - skipped}, "
                f"건너뜀={skipped}, DB 저장 없음"
            )
            return

        self.stdout.write(
            f"자동 예측 완료: 성공={succeeded}, "
            f"건너뜀={skipped}, 실패={failed}"
        )

        if failed:
            raise CommandError(
                f"{failed}개 매장의 예측 실행에 실패했습니다."
            )
