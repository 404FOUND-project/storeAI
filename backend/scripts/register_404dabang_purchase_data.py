import argparse
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "analysis.config.settings")

STORE_ID = 1
VALID_FROM = date(2025, 1, 1)
PRICE_TYPE = "ESTIMATED"
SOURCE = "404다방 시연용 구매단가 정리표"

# The six mass-to-volume items are intentionally excluded.
# Do not add a base_quantity for them without verified density/yield data.
ROWS = [
    # ingredient, package_quantity, purchase_unit, base_quantity, evidence, price_krw
    ("원두", "1", "kg", "1000", "상품 표시 규격 1kg = 1,000g", "23800"),
    ("디카페인원두", "1", "kg", "1000", "상품 표시 규격 1kg = 1,000g", "35400"),
    ("우유", "1", "L", "1000", "상품 표시 규격 1L = 1,000ml", "2850"),
    ("귀리음료", "1", "L", "1000", "상품 표시 규격 1L = 1,000ml", "4490"),
    ("아몬드시럽", "1", "L", "1000", "상품 표시 규격 1L = 1,000ml", "16000"),
    ("바닐라시럽", "1", "L", "1000", "상품 표시 규격 1L = 1,000ml", "14900"),
    ("생크림", "1", "L", "1000", "상품 표시 규격 1L = 1,000ml", "8800"),
    ("초코소스", "2.47", "kg", "2470", "상품 표시 규격 2.47kg = 2,470g", "33000"),
    ("아이스티용 티베이스", "1", "L", "1000", "상품 표시 규격 1L = 1,000ml", "18000"),
    ("녹차 베이스", "1", "L", "1000", "상품 표시 규격 1L = 1,000ml", "18000"),
    ("홍차 베이스", "1", "L", "1000", "상품 표시 규격 1L = 1,000ml", "18000"),
    ("레몬청", "1", "L", "1000", "상품 표시 규격 1L = 1,000ml", "16000"),
    ("탄산수", "18", "L", "18000", "상품 표시 규격 1.5L × 12개 = 총 18L = 18,000ml", "14900"),
    ("케이크시트", "1", "ea", "1", "상품 표시 규격 1개 = 1ea", "4780"),
    ("크림치즈", "1", "kg", "1000", "상품 표시 규격 1kg = 1,000g", "14300"),
    ("푸딩믹스", "1", "kg", "1000", "상품 표시 규격 1kg = 1,000g", "12000"),
    ("고구마페이스트", "1", "kg", "1000", "상품 표시 규격 1kg = 1,000g", "10100"),
    ("마스카포네 치즈", "0.5", "kg", "500", "상품 표시 규격 500g = 0.5kg = 500g", "8400"),
    ("레몬 커드", "1", "kg", "1000", "상품 표시 규격 1kg = 1,000g", "18000"),
    ("바나나", "1", "kg", "1000", "상품 표시 규격 1kg = 1,000g", "4000"),
    ("블루베리 퓨레", "0.5", "kg", "500", "상품 표시 규격 500g = 0.5kg = 500g", "13240"),
]

EXCLUDED = {
    "황매실청",
    "복숭아·살구청",
    "패션후르츠청",
    "자몽청",
    "아쿠아로사 과일 베이스",
    "오렌지주스원액",
}


class RegistrationError(Exception):
    pass


def setup_django():
    import django
    django.setup()


def build_objects(using):
    from inventory.models import Ingredient, IngredientPurchaseSpec, IngredientPurchasePrice
    from store.models import Store
    from inventory.services.costing import save_purchase_price

    try:
        store = Store.objects.using(using).get(pk=STORE_ID)
    except Store.DoesNotExist as exc:
        raise RegistrationError(f"store_id={STORE_ID} 매장을 찾을 수 없습니다.") from exc

    ingredients = {
        item.name: item
        for item in Ingredient.objects.using(using).filter(
            name__in=[row[0] for row in ROWS] + list(EXCLUDED)
        )
    }
    expected_names = {row[0] for row in ROWS} | EXCLUDED
    if set(ingredients) != expected_names:
        missing = sorted(expected_names - set(ingredients))
        raise RegistrationError(f"재료 누락 또는 이름 불일치: {missing}")

    if len(ROWS) != 21:
        raise RegistrationError("등록 대상은 정확히 21개여야 합니다.")

    specs = []
    prices = []
    for name, package_qty, purchase_unit, base_qty, evidence, amount in ROWS:
        ingredient = ingredients[name]
        spec = IngredientPurchaseSpec(
            store=store,
            ingredient=ingredient,
            package_quantity=Decimal(package_qty),
            purchase_unit=purchase_unit,
            base_quantity=Decimal(base_qty),
            conversion_evidence=evidence,
        )
        spec.full_clean()
        price = IngredientPurchasePrice(
            purchase_spec=spec,
            price_type=PRICE_TYPE,
            amount=Decimal(amount),
            valid_from=VALID_FROM,
            valid_to=None,
            source=SOURCE,
            rationale=(
                "404다방 시연 및 원가 계산을 위한 프로젝트용 추정 단가입니다. "
                "실제 404다방 매입 영수증이나 확정 공급업체 견적을 의미하지 않습니다. "
                "실제 매입 데이터가 확보되면 별도의 ACTUAL 가격 이력으로 관리해야 합니다."
            ),
        )
        # Validate scalar fields now; the FK and price-period checks run again
        # through save_purchase_price() after the purchase spec has a DB ID.
        price.full_clean(exclude=["purchase_spec"])
        specs.append(spec)
        prices.append(price)

    return store, ingredients, specs, prices


def execute(apply):
    setup_django()
    from django.db import DEFAULT_DB_ALIAS, transaction
    from inventory.models import IngredientPurchaseSpec, IngredientPurchasePrice
    from inventory.services.costing import save_purchase_spec, save_purchase_price

    using = DEFAULT_DB_ALIAS
    store, ingredients, specs, prices = build_objects(using)

    # Fail closed if any target ingredient already has purchase data.
    target_ids = [ingredients[row[0]].pk for row in ROWS]
    existing_specs = IngredientPurchaseSpec.objects.using(using).filter(
        store_id=store.pk, ingredient_id__in=target_ids
    )
    existing_prices = IngredientPurchasePrice.objects.using(using).filter(
        purchase_spec__store_id=store.pk,
        purchase_spec__ingredient_id__in=target_ids,
    )
    if existing_specs.exists() or existing_prices.exists():
        raise RegistrationError(
            "대상 21개 재료에 기존 구매규격 또는 가격 이력이 있습니다. "
            "중복 등록을 막기 위해 중단했습니다."
        )

    print(f"대상 매장: {store.name} (store_id={store.pk})")
    print(f"구매규격 및 추정 단가 등록 대상: {len(specs)}개")
    print(f"가격 유형: {PRICE_TYPE}")
    print(f"적용 시작일: {VALID_FROM.isoformat()} / 종료일: 없음")
    print(f"제외 재료 6개: {', '.join(sorted(EXCLUDED))}")
    print("")
    for row in ROWS:
        print(f"- {row[0]}: {row[1]} {row[2]} / {int(Decimal(row[5])):,}원")

    if not apply:
        print("\n읽기 전용 사전 점검 통과. DB에는 아무것도 저장하지 않았습니다.")
        print("내용을 확인한 뒤 실제 등록하려면 --apply를 붙여 실행하세요.")
        return

    created_specs = 0
    created_prices = 0
    with transaction.atomic(using=using):
        # Recheck inside the transaction before writing.
        if IngredientPurchaseSpec.objects.using(using).filter(
            store_id=store.pk, ingredient_id__in=target_ids
        ).exists():
            raise RegistrationError("등록 직전 기존 구매규격이 발견되어 중단했습니다.")
        if IngredientPurchasePrice.objects.using(using).filter(
            purchase_spec__store_id=store.pk,
            purchase_spec__ingredient_id__in=target_ids,
        ).exists():
            raise RegistrationError("등록 직전 기존 가격 이력이 발견되어 중단했습니다.")

        for spec, price in zip(specs, prices):
            save_purchase_spec(spec)
            created_specs += 1
            price.purchase_spec = spec
            save_purchase_price(price)
            created_prices += 1

        final_specs = IngredientPurchaseSpec.objects.using(using).filter(
            store_id=store.pk, ingredient_id__in=target_ids
        ).count()
        final_prices = IngredientPurchasePrice.objects.using(using).filter(
            purchase_spec__store_id=store.pk,
            purchase_spec__ingredient_id__in=target_ids,
        ).count()
        if final_specs != 21 or final_prices != 21:
            raise RegistrationError(
                f"등록 후 검증 실패: specs={final_specs}, prices={final_prices}"
            )

    print(
        f"\n등록 완료: purchase_specs={created_specs}, "
        f"purchase_prices={created_prices}. "
        "트랜잭션 검증을 통과했습니다."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Register 404dabang estimated ingredient purchase data."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제 DB에 등록합니다. 기본 실행은 읽기 전용입니다.",
    )
    args = parser.parse_args()
    try:
        execute(args.apply)
    except Exception as exc:
        print(f"등록 중단: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
