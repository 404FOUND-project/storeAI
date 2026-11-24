"""기존 Menu를 기반으로 더미(테스트) 리뷰 생성. source=DUMMY, 실제 고객 리뷰 아님.
사용: python manage.py seed_dummy_reviews --store-id 1 [--per-menu 6] [--reset]
"""
import random
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from review.models import Review
from store.models import Menu, Store

# (감정, 카테고리, 점수, 문장 템플릿) — {m}=메뉴명
T = [
    ("positive", "TASTE", 5.0, "{m} 정말 맛있어요! 또 시킬 것 같아요."),
    ("positive", "TASTE", 4.5, "{m} 향이 좋고 깔끔해서 마음에 들었어요."),
    ("positive", "AMOUNT", 4.5, "{m} 양이 푸짐해서 배부르게 먹었어요."),
    ("positive", "PRICE", 4.5, "{m} 가격 대비 만족스러워요. 가성비 좋네요."),
    ("positive", "ATMOSPHERE", 5.0, "{m} 먹으면서 매장 분위기도 좋아서 재방문하고 싶어요."),
    ("positive", "SERVICE", 4.5, "{m} 주문했는데 직원분이 친절하고 빨리 나와서 좋았어요."),
    ("negative", "TASTE", 2.0, "{m} 너무 달아서(또는 짜서) 아쉬웠어요."),
    ("negative", "TASTE", 2.5, "{m} 맛이 싱겁고 밍밍해요. 기대 이하였어요."),
    ("negative", "AMOUNT", 2.0, "{m} 양이 너무 적어요. 한 입 거리예요."),
    ("negative", "PRICE", 2.0, "{m} 가격이 좀 비싼 편이에요. 이 가격이면 아쉬워요."),
    ("negative", "SERVICE", 2.0, "{m} 주문하고 한참 기다렸어요. 너무 늦게 나와요."),
    ("neutral", "TASTE", 3.0, "{m} 그냥 무난해요. 특별한 건 없어요."),
    ("neutral", "ETC", 3.0, "{m} 평범한 맛이에요. 나쁘지 않아요."),
    ("neutral", "TASTE", 3.5, "{m}은 괜찮은데 다른 메뉴는 조금 아쉬웠어요."),
]


class Command(BaseCommand):
    help = "기존 메뉴 기반 더미 리뷰 생성 (source=DUMMY)"

    def add_arguments(self, parser):
        parser.add_argument("--store-id", type=int, required=True)
        parser.add_argument("--per-menu", type=int, default=6)
        parser.add_argument("--reset", action="store_true", help="기존 DUMMY 리뷰 삭제 후 재생성")

    def handle(self, *args, **o):
        try:
            store = Store.objects.get(pk=o["store_id"])
        except Store.DoesNotExist:
            raise CommandError("해당 store-id 매장이 없습니다.")
        menus = list(Menu.objects.filter(store=store))
        if not menus:
            raise CommandError("매장에 메뉴가 없습니다. 메뉴를 먼저 등록하세요.")
        if o["reset"]:
            Review.objects.filter(store=store, source="DUMMY").delete()
        rnd, now, rows = random.Random(42), timezone.now(), []
        for m in menus:
            for _ in range(o["per_menu"]):
                s, c, r, t = rnd.choice(T)
                rows.append(Review(
                    store=store, menu=m, content=t.format(m=m.name), rating=r,
                    sentiment=s, category=c, source="DUMMY",
                    keywords={"dummy": True, "note": "테스트용 더미 리뷰"},
                    reviewed_at=now - timedelta(days=rnd.randint(0, 90)),
                ))
        Review.objects.bulk_create(rows)
        self.stdout.write(self.style.SUCCESS(f"더미 리뷰 {len(rows)}건 생성 (메뉴 {len(menus)}개, 가짜 데이터)"))
