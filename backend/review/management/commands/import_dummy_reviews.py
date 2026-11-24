"""data/dummy_reviews.csv의 더미(테스트) 리뷰를 DB에 넣기. 메뉴는 이름으로 매칭.
사용: python manage.py import_dummy_reviews --store-id 1 [--reset]"""
import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.dateparse import parse_datetime

from review.models import Review
from store.models import Menu, Store

CSV = Path(__file__).resolve().parents[4] / "data" / "dummy_reviews.csv"


class Command(BaseCommand):
    help = "CSV의 더미 리뷰(source=DUMMY)를 가져오기"

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, required=True)
        parser.add_argument("--reset", action="store_true")

    def handle(self, *a, **o):
        try:
            store = Store.objects.get(pk=o["store_id"])
        except Store.DoesNotExist:
            raise CommandError("해당 store-id 매장이 없습니다.")
        menus = {m.name: m for m in Menu.objects.filter(store=store)}
        if o["reset"]:
            Review.objects.filter(store=store, source="DUMMY").delete()
        rows, skipped = [], 0
        with open(CSV, encoding="utf-8-sig", newline="") as f:
            for r in csv.DictReader(f):
                m = menus.get(r["menu_name"])
                if not m:
                    skipped += 1
                    continue
                rows.append(Review(
                    store=store, menu=m, content=r["content"], rating=r["rating"] or None,
                    sentiment=r["sentiment"], category=r["category"], source="DUMMY",
                    keywords={"dummy": True, "note": "테스트용 더미 리뷰"},
                    reviewed_at=parse_datetime(r["reviewed_at"]) if r["reviewed_at"] else None,
                ))
        Review.objects.bulk_create(rows)
        self.stdout.write(self.style.SUCCESS(f"{len(rows)}건 가져옴 (메뉴 이름 불일치로 {skipped}건 건너뜀)"))
