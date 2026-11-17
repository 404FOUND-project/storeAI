"""시연용 가짜 원가 데이터 생성: 재고 재료와 연결된 재료·단가·메뉴별 레시피·원가. 전부 가짜 값!

사용: python manage.py seed_dummy_costs [--store 2] [--reset]
(--reset: 이 매장의 레시피·원가를 지우고 다시 만듦. 로컬 DB 전용으로 쓸 것)
"""
from datetime import date
from decimal import Decimal as D

from django.core.management.base import BaseCommand
from django.db import connection

from inventory.models import (Ingredient, Inventory, IngredientPurchasePrice,
                              IngredientPurchaseSpec, Recipe, RecipeItem)
from inventory.services.costing import (calculate_menu_cost, save_purchase_price,
                                        save_purchase_spec, save_recipe, save_recipe_item)
from store.models import Menu, Store

AS_OF = date(2025, 1, 1)
# 재고 재료명: (포장수량, 포장단위, 포장 기본단위 환산량, 포장 가격) -- 가짜 단가
PRICES = {
    "원두": ("1", "kg", "1000", "28000"), "디카페인원두": ("1", "kg", "1000", "35000"),
    "우유": ("1", "L", "1000", "2600"), "귀리음료": ("1", "L", "1000", "4500"),
    "아몬드시럽": ("1", "L", "1000", "9000"), "바닐라시럽": ("1", "L", "1000", "9000"),
    "생크림": ("1", "L", "1000", "8000"), "초코소스": ("1", "kg", "1000", "12000"),
    "티베이스": ("1", "L", "1000", "7000"), "과일청": ("1", "L", "1000", "8000"),
    "탄산수": ("1", "L", "1000", "1000"), "오렌지주스원액": ("1", "L", "1000", "6000"),
    "케이크시트": ("10", "ea", "10", "12000"), "크림치즈": ("1", "kg", "1000", "14000"),
    "푸딩믹스": ("1", "kg", "1000", "10000"), "고구마페이스트": ("1", "kg", "1000", "9000"),
}
# 메뉴명: [(재료, 1잔/1개당 사용량)] -- 가짜 레시피
RECIPES = {
    "아몬드크리미라떼": [("원두", 18), ("우유", 120), ("아몬드시럽", 15), ("생크림", 30)],
    "아메리카노": [("원두", 18)],
    "아메리카노 디카페인": [("디카페인원두", 18)],
    "카페 라떼": [("원두", 18), ("우유", 150)],
    "플랫 화이트": [("원두", 20), ("우유", 120)],
    "바닐라 라떼": [("원두", 18), ("우유", 140), ("바닐라시럽", 15)],
    "귀리 라떼": [("원두", 18), ("귀리음료", 150)],
    "아인슈페너": [("원두", 18), ("우유", 80), ("생크림", 40)],
    "아이스티 샷 추가": [("티베이스", 120), ("원두", 18), ("과일청", 15)],
    "황매실 에이드/아이스티": [("과일청", 40), ("탄산수", 150)],
    "복숭아 살구 아이스티": [("티베이스", 120), ("과일청", 30)],
    "패션후르츠 에이드": [("과일청", 45), ("탄산수", 150)],
    "그린티 자몽": [("티베이스", 100), ("과일청", 40)],
    "아쿠아로사": [("과일청", 40), ("탄산수", 150)],
    "발로나 초코라떼": [("우유", 180), ("초코소스", 35)],
    "레몬 에이드": [("과일청", 40), ("탄산수", 150)],
    "블랙티 밀크티": [("티베이스", 100), ("우유", 120)],
    "오렌지 감귤 착즙 주스": [("오렌지주스원액", 180), ("과일청", 20)],
    "마스카포네 티라미수": [("케이크시트", 1), ("크림치즈", 60), ("생크림", 40)],
    "밀크티 바스크": [("크림치즈", 120), ("티베이스", 30), ("생크림", 40)],
    "레몬 생크림 케이크": [("케이크시트", 1), ("생크림", 60), ("과일청", 20)],
    "바스크 치즈 케이크": [("크림치즈", 130), ("생크림", 40)],
    "초코 바나나 케이크": [("케이크시트", 1), ("초코소스", 30), ("생크림", 40)],
    "찐고구마 케이크": [("케이크시트", 1), ("고구마페이스트", 80), ("생크림", 40)],
    "커스터드 푸딩": [("푸딩믹스", 70), ("우유", 100)],
    "빅토리아 케이크": [("케이크시트", 1), ("생크림", 50), ("과일청", 25)],
    "블루베리 판나코타": [("푸딩믹스", 40), ("생크림", 100), ("과일청", 30)],
}


class Command(BaseCommand):
    help = "가짜 원가 데이터 생성 (재고 재료와 연결)"

    def add_arguments(self, p):
        p.add_argument("--store", type=int, default=None)
        p.add_argument("--reset", action="store_true")

    def handle(self, *a, **o):
        store = Store.objects.get(pk=o["store"]) if o["store"] else Store.objects.first()
        if o["reset"]:
            with connection.cursor() as c:
                mids = [m.id for m in Menu.objects.filter(store=store)]
                ph = ",".join(["%s"] * len(mids))
                c.execute(f"DELETE FROM inventory_recipecostline WHERE snapshot_id IN (SELECT id FROM inventory_recipecostsnapshot WHERE menu_id IN ({ph}))", mids)
                c.execute(f"DELETE FROM inventory_recipecostsnapshot WHERE menu_id IN ({ph})", mids)
                c.execute(f"DELETE FROM inventory_recipeitem WHERE recipe_id IN (SELECT id FROM inventory_recipe WHERE menu_id IN ({ph}))", mids)
                c.execute(f"DELETE FROM inventory_recipe WHERE menu_id IN ({ph})", mids)
        ing = {}
        for inv in Inventory.objects.filter(store=store):
            if inv.ingredient_name not in PRICES:
                continue
            pq, pu, bq, amount = PRICES[inv.ingredient_name]
            base = {"g": "g", "ml": "ml"}.get(inv.unit, "ea")
            i, _ = Ingredient.objects.get_or_create(name=inv.ingredient_name, defaults={"base_unit": base})
            ing[inv.ingredient_name] = i
            if inv.ingredient_id != i.id:  # 재고 ↔ 재료 연결 (발주 추천이 사용)
                Inventory.objects.filter(pk=inv.pk).update(ingredient=i)
            spec = IngredientPurchaseSpec.objects.filter(store=store, ingredient=i).first()
            if not spec:
                spec = save_purchase_spec(IngredientPurchaseSpec(
                    store=store, ingredient=i, package_quantity=D(pq), purchase_unit=pu,
                    base_quantity=D(bq), conversion_evidence="시연용 가짜 값"))
            if not spec.prices.exists():
                save_purchase_price(IngredientPurchasePrice(
                    purchase_spec=spec, price_type="ESTIMATED", amount=D(amount),
                    valid_from=AS_OF, source="시연용 가짜 단가", rationale="시연용 가짜 단가"))
        done = 0
        for m in Menu.objects.filter(store=store):
            items = RECIPES.get(m.name)
            if not items or m.recipes.exists():
                continue
            r = save_recipe(Recipe(menu=m, variant="STANDARD", version=1, valid_from=AS_OF))
            for n, q in items:
                save_recipe_item(RecipeItem(recipe=r, ingredient=ing[n], quantity_base=D(q)))
            calculate_menu_cost(m, price_type="ESTIMATED", as_of=AS_OF)
            done += 1
        self.stdout.write(f"{done} menus done (all values are FAKE)")
