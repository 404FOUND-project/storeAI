"""팀이 정한 실제 메뉴(store/data/menus.csv)를 DB에 등록하는 명령어.

사용법 (backend 폴더에서):
    python manage.py load_menus                  # 로컬 SQLite: 첫 번째 매장에 등록
    python manage.py load_menus --store-id 3     # 특정 매장에 등록
    python manage.py load_menus --yes-shared-db  # 팀 공유 DB(MySQL)에 등록 (팀과 합의 후에만!)

- 같은 메뉴 ID(M001 등)가 이미 있으면 이름·분류·가격만 갱신하고, 원가(cost)는 건드리지 않습니다.
- 메뉴를 삭제하지는 않습니다.
- 음료 온도(temperature)는 Menu 모델에 필드가 없어 DB에 저장하지 않고, CSV에만 있습니다.
"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction

from store.models import Menu, Store

CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "menus.csv"


def read_menus():
    with open(CSV_PATH, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


class Command(BaseCommand):
    help = "store/data/menus.csv 의 메뉴를 DB에 등록합니다."

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, help="메뉴를 등록할 매장 ID")
        parser.add_argument(
            "--yes-shared-db", action="store_true",
            help="공유 DB(MySQL)에 쓰는 것을 허용합니다. 팀과 합의된 경우에만 사용하세요.",
        )

    def handle(self, *args, **opts):
        if connection.vendor != "sqlite" and not opts["yes_shared_db"]:
            raise CommandError(
                "공유 DB에는 쓸 수 없습니다. 팀과 합의했다면 --yes-shared-db 를 붙여 주세요."
            )

        stores = Store.objects.order_by("id")
        if opts["store_id"]:
            store = stores.filter(id=opts["store_id"]).first()
        elif stores.count() == 1:
            store = stores.first()
        elif stores.count() == 0:
            raise CommandError("등록된 매장이 없습니다.")
        else:
            raise CommandError("매장이 여러 개입니다. --store-id 로 지정해 주세요.")
        if store is None:
            raise CommandError("해당 ID의 매장이 없습니다.")

        rows = read_menus()
        created = updated = 0
        with transaction.atomic():
            for r in rows:
                _, is_new = Menu.objects.update_or_create(
                    store=store, source_menu_id=r["source_menu_id"],
                    defaults={
                        "name": r["name"],
                        "category": r["category"],
                        "price": int(r["price"]),
                        "data_type": "real_menu",
                    },
                )
                created += is_new
                updated += not is_new
        self.stdout.write(self.style.SUCCESS(
            f"[{store.name}] 메뉴 {len(rows)}개 처리: 새로 {created}개, 갱신 {updated}개"
        ))
