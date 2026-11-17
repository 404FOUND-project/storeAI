import argparse
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "analysis.config.settings")

STORE_ID = 1
VALID_FROM = date(2025, 1, 1)
PRICE_TYPE = "ESTIMATED"
SOURCE = "404다방 프로젝트 시연용 가상 구매단가"

# These are explicitly project assumptions, not verified commercial package sizes/prices.
ROWS = [
    # ingredient_id, exact_name, estimated_price_krw
    (39, "황매실청", "12000"),
    (40, "복숭아·살구청", "15000"),
    (41, "패션후르츠청", "18000"),
    (42, "자몽청", "14000"),
    (43, "아쿠아로사 과일 베이스", "20000"),
    (46, "오렌지주스원액", "10000"),
]


class RegistrationError(Exception):
    pass


def setup_django():
    import django
    django.setup()


def build_objects(using):
    from store.models import Store
    from inventory.models import Ingredient, IngredientPurchaseSpec, IngredientPurchasePrice

    store = Store.objects.using(using).get(pk=STORE_ID)
    specs = []
    prices = []

    for ingredient_id, expected_name, amount in ROWS:
        ingredient = Ingredient.objects.using(using).get(
            pk=ingredient_id,
            name=expected_name,
        )
        if ingredient.base_unit != "ml":
            raise RegistrationError(
                f"{expected_name}: 기준 단위가 ml가 아닙니다 ({ingredient.base_unit})."
            )

        spec = IngredientPurchaseSpec(
            store=store,
            ingredient=ingredient,
            package_quantity=Decimal("1"),
            purchase_unit="L",
            base_quantity=Decimal("1000"),
            conversion_evidence=(
                "프로젝트 시연용 가상 구매규격. 1L=1,000ml로 가정한 값이며 "
                "실제 제품 포장 또는 제조사 규격을 확인한 값이 아님."
            ),
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
                "404다방 시연 및 메뉴 원가 계산을 위한 프로젝트 가상 추정 단가. "
                "실제 구매 영수증이나 공급업체 견적에 근거한 가격이 아님."
            ),
        )
        price.full_clean(exclude=["purchase_spec"])
        specs.append(spec)
        prices.append(price)

    return store, specs, prices


def execute(apply):
    setup_django()
    from django.db import DEFAULT_DB_ALIAS, transaction
    from inventory.models import IngredientPurchaseSpec, IngredientPurchasePrice
    from inventory.services.costing import save_purchase_spec, save_purchase_price

    using = DEFAULT_DB_ALIAS
    store, specs, prices = build_objects(using)
    target_ids = [row[0] for row in ROWS]

    existing_specs = IngredientPurchaseSpec.objects.using(using).filter(
        store_id=store.pk,
        ingredient_id__in=target_ids,
    )
    existing_prices = IngredientPurchasePrice.objects.using(using).filter(
        purchase_spec__store_id=store.pk,
        purchase_spec__ingredient_id__in=target_ids,
    )
    if existing_specs.exists() or existing_prices.exists():
        raise RegistrationError(
            "대상 6개 재료에 기존 구매규격 또는 가격 이력이 있습니다. "
            "중복 등록을 막기 위해 중단합니다."
        )

    print(f"대상 매장: {store.name} (store_id={store.pk})")
    print("추가 등록 대상: 구매규격 6개, 추정 단가 6개")
    print("가상 구매규격: 각 1L = 1,000ml")
    print(f"가격 유형: {PRICE_TYPE}")
    print(f"적용 시작일: {VALID_FROM.isoformat()} / 종료일: 없음")
    print("주의: 아래 규격과 가격은 실제 구매정보가 아닌 프로젝트 시연용 가정입니다.")
    for (ingredient_id, name, amount), spec in zip(ROWS, specs):
        print(f"- {name} (ID {ingredient_id}): 1L / {int(Decimal(amount)):,}원")

    if not apply:
        print("\n읽기 전용 사전 점검 통과. DB에는 아무것도 저장하지 않았습니다.")
        print("내용을 확인한 뒤 실제 등록하려면 --apply를 붙여 실행하세요.")
        return

    created_specs = 0
    created_prices = 0
    with transaction.atomic(using=using):
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

        if final_specs != 6 or final_prices != 6:
            raise RegistrationError(
                f"등록 후 검증 실패: specs={final_specs}, prices={final_prices}"
            )

    print(
        f"\n등록 완료: purchase_specs={created_specs}, "
        f"purchase_prices={created_prices}. 트랜잭션 검증을 통과했습니다."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Register the six remaining 404dabang demo purchase assumptions."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="실제 DB에 등록합니다. 기본 실행은 읽기 전용 사전 점검입니다.",
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
