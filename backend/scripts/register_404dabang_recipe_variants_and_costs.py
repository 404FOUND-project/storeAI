
"""
404다방 HOT/ICE 레시피 추가 및 원가 계산

프로젝트 루트(C:\\dev\\storeAI)에서 실행한다.

1. 읽기 전용 사전 점검
python backend\\manage.py shell -c "exec(open('backend/scripts/register_404dabang_recipe_variants_and_costs.py', encoding='utf-8').read())"

2. 사전 점검 결과 확인 후 실제 반영
python backend\\manage.py shell -c "import sys; sys.argv.append('--apply'); exec(open('backend/scripts/register_404dabang_recipe_variants_and_costs.py', encoding='utf-8').read())"
"""

import sys
from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q

from inventory.models import (
    IngredientPurchasePrice,
    Recipe,
    RecipeCostSnapshot,
    RecipeItem,
)
from inventory.services.costing import (
    calculate_menu_cost,
    save_recipe,
    save_recipe_item,
)
from store.models import Menu


STORE_ID = 1
AS_OF = date(2025, 1, 1)
PRICE_TYPE = IngredientPurchasePrice.PriceType.ESTIMATED

# 프로젝트 시연용 가정값. 실제 매장 레시피로 검증된 수량이 아니다.
# 기존 STANDARD 레시피에서 지정한 우유/귀리음료 양만 변경한다.
ICE_MILK_QUANTITIES = {
    "M001": ("우유", Decimal("155")),
    "M004": ("우유", Decimal("170")),
    "M005": ("우유", Decimal("130")),
    "M006": ("우유", Decimal("155")),
    "M007": ("귀리음료", Decimal("170")),
    "M015": ("우유", Decimal("170")),
}

RATIONALE = (
    "프로젝트 시연용 HOT/ICE 구분 가정. "
    "HOT는 기존 STANDARD 재료량을 유지하고, "
    "ICE는 얼음 및 차가운 음료 제조를 고려해 우유/귀리음료 양을 조정함. "
    "실제 404다방의 검증된 제조 레시피가 아님."
)


def get_active_recipe(menu, variant):
    recipes = list(
        Recipe.objects.filter(
            menu=menu,
            variant=variant,
            is_active=True,
            valid_from__lte=AS_OF,
        )
        .filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=AS_OF)
        )
        .order_by("-version")
    )

    if len(recipes) != 1:
        raise RuntimeError(
            f"{menu.pos_code} {menu.name}: {variant} 레시피가 "
            f"{AS_OF} 기준 정확히 1개여야 합니다. 현재 {len(recipes)}개"
        )

    return recipes[0]


def preflight():
    menus = list(
        Menu.objects.filter(store_id=STORE_ID).order_by("pos_code")
    )

    if len(menus) != 27:
        raise RuntimeError(
            f"메뉴 수가 예상과 다릅니다. 예상 27개 / 실제 {len(menus)}개"
        )

    recipe_count = Recipe.objects.filter(
        menu__store_id=STORE_ID
    ).count()

    item_count = RecipeItem.objects.filter(
        recipe__menu__store_id=STORE_ID
    ).count()

    if recipe_count != 27 or item_count != 59:
        raise RuntimeError(
            "기존 레시피 데이터 수가 예상과 다릅니다. "
            f"레시피 {recipe_count}개 / 재료 연결 {item_count}개"
        )

    menu_by_code = {
        menu.pos_code: menu
        for menu in menus
    }

    missing_codes = sorted(
        set(ICE_MILK_QUANTITIES) - set(menu_by_code)
    )

    if missing_codes:
        raise RuntimeError(
            f"분리 대상 메뉴가 없습니다: {missing_codes}"
        )

    standard_by_code = {}

    for menu in menus:
        standard_by_code[menu.pos_code] = get_active_recipe(
            menu,
            Recipe.Variant.STANDARD,
        )

    # 분리 대상은 모두 BOTH 메뉴여야 한다.
    for code in ICE_MILK_QUANTITIES:
        menu = menu_by_code[code]

        if menu.serving_temperature != Menu.ServingTemperature.BOTH:
            raise RuntimeError(
                f"{code} {menu.name}: BOTH 메뉴가 아닙니다."
            )

    # 중복 등록 방지
    existing_variants = Recipe.objects.filter(
        menu__store_id=STORE_ID,
        menu__pos_code__in=list(ICE_MILK_QUANTITIES),
        variant__in=[
            Recipe.Variant.HOT,
            Recipe.Variant.ICE,
        ],
    ).count()

    if existing_variants:
        raise RuntimeError(
            f"HOT/ICE 레시피가 이미 {existing_variants}개 있습니다. "
            "중복 등록 방지를 위해 중단합니다."
        )

    existing_snapshots = RecipeCostSnapshot.objects.filter(
        menu__store_id=STORE_ID,
        price_type=PRICE_TYPE,
        as_of=AS_OF,
    ).count()

    if existing_snapshots:
        raise RuntimeError(
            f"동일 기준일 원가 스냅샷이 이미 {existing_snapshots}개 있습니다. "
            "중복 계산 방지를 위해 중단합니다."
        )

    # 기존 레시피 항목 및 ICE 변경 대상 재료 검증
    for code, (ingredient_name, _) in ICE_MILK_QUANTITIES.items():
        recipe = standard_by_code[code]

        items = list(
            recipe.items.select_related("ingredient").order_by("pk")
        )

        if not items:
            raise RuntimeError(
                f"{code}: 기존 STANDARD 레시피에 재료가 없습니다."
            )

        for item in items:
            item.full_clean()

        matching = [
            item
            for item in items
            if item.ingredient.name == ingredient_name
            and item.ingredient.base_unit == "ml"
        ]

        if len(matching) != 1:
            raise RuntimeError(
                f"{code}: {ingredient_name}(ml) 재료가 "
                f"정확히 1개가 아닙니다. 현재 {len(matching)}개"
            )

    return menus, menu_by_code, standard_by_code


def print_plan(menus, menu_by_code, standard_by_code):
    normal_count = len(menus) - len(ICE_MILK_QUANTITIES)

    print("=" * 55)
    print("404다방 HOT/ICE 레시피 및 원가 등록 사전 점검")
    print("=" * 55)

    print("매장: 404다방 (store_id=1)")
    print("기존 메뉴: 27개")
    print("기존 STANDARD 레시피: 27개")
    print("기존 레시피 재료 연결: 59개")

    print("\n추가 예정:")
    print("- HOT 레시피 6개")
    print("- ICE 레시피 6개")
    print("- 레시피 재료 연결 30개")

    print("\n원가 계산 예정:")
    print(f"- HOT/ICE 분리 메뉴: 6개 × 2 = 12건")
    print(f"- 나머지 메뉴: {normal_count}건")
    print("- 총 33건")

    print(f"\n기준일: {AS_OF}")
    print(f"가격 유형: {PRICE_TYPE}")

    print("\nHOT/ICE 수량:")
    for code, (ingredient_name, ice_quantity) in ICE_MILK_QUANTITIES.items():
        menu = menu_by_code[code]
        standard = standard_by_code[code]

        hot_quantity = next(
            item.quantity_base
            for item in standard.items.select_related("ingredient").all()
            if item.ingredient.name == ingredient_name
        )

        print(
            f"- {code} {menu.name}: "
            f"HOT {hot_quantity}ml / ICE {ice_quantity}ml"
        )

    print("\n주의:")
    print("- ICE 수량은 프로젝트 시연용 가정입니다.")
    print("- 물과 얼음은 현재 재료원가 계산에서 제외됩니다.")
    print("- 분리 메뉴의 Menu.cost에는 HOT 원가를 대표값으로 저장합니다.")
    print("- ICE 원가는 별도 원가 스냅샷에 보존합니다.")


def apply_changes(menus, menu_by_code, standard_by_code):
    created_recipes = 0
    created_items = 0

    with transaction.atomic():

        # 트랜잭션 내부에서 중복 상태 재확인
        if Recipe.objects.filter(
            menu__store_id=STORE_ID,
            menu__pos_code__in=list(ICE_MILK_QUANTITIES),
            variant__in=[
                Recipe.Variant.HOT,
                Recipe.Variant.ICE,
            ],
        ).exists():
            raise RuntimeError(
                "적용 직전 HOT/ICE 레시피가 발견되어 중단했습니다."
            )

        if RecipeCostSnapshot.objects.filter(
            menu__store_id=STORE_ID,
            price_type=PRICE_TYPE,
            as_of=AS_OF,
        ).exists():
            raise RuntimeError(
                "적용 직전 기존 원가 스냅샷이 발견되어 중단했습니다."
            )

        # 1. HOT/ICE 레시피 추가
        for code, (ingredient_name, ice_quantity) in ICE_MILK_QUANTITIES.items():

            menu = menu_by_code[code]
            standard = standard_by_code[code]

            source_items = list(
                standard.items.select_related("ingredient").order_by("pk")
            )

            for variant in (
                Recipe.Variant.HOT,
                Recipe.Variant.ICE,
            ):

                new_recipe = Recipe(
                    menu=menu,
                    variant=variant,
                    version=1,
                    valid_from=standard.valid_from,
                    valid_to=standard.valid_to,
                    yield_quantity=standard.yield_quantity,
                    is_active=True,
                    variant_rationale=RATIONALE,
                )

                save_recipe(new_recipe)
                created_recipes += 1

                # 기존 STANDARD 재료 연결을 복사
                for source_item in source_items:

                    quantity = source_item.quantity_base

                    # ICE의 우유/귀리음료 양만 조정
                    if (
                        variant == Recipe.Variant.ICE
                        and source_item.ingredient.name == ingredient_name
                        and source_item.ingredient.base_unit == "ml"
                    ):
                        quantity = ice_quantity

                    new_item = RecipeItem(
                        recipe=new_recipe,
                        ingredient=source_item.ingredient,
                        quantity_base=quantity,
                    )

                    save_recipe_item(new_item)
                    created_items += 1

        # 2. 원가 계산
        for menu in menus:

            if menu.pos_code in ICE_MILK_QUANTITIES:

                # HOT 원가
                hot_snapshot = calculate_menu_cost(
                    menu,
                    price_type=PRICE_TYPE,
                    as_of=AS_OF,
                    variant=Recipe.Variant.HOT,
                )

                if hot_snapshot.status != RecipeCostSnapshot.Status.COMPLETE:
                    raise RuntimeError(
                        f"{menu.pos_code} HOT 원가 계산 실패: "
                        f"{hot_snapshot.error_details}"
                    )

                # HOT 계산 결과를 대표 원가로 보관
                menu.refresh_from_db()

                hot_cost = menu.cost
                hot_status = menu.cost_status
                hot_calculated_at = menu.cost_calculated_at

                # ICE 원가
                ice_snapshot = calculate_menu_cost(
                    menu,
                    price_type=PRICE_TYPE,
                    as_of=AS_OF,
                    variant=Recipe.Variant.ICE,
                )

                if ice_snapshot.status != RecipeCostSnapshot.Status.COMPLETE:
                    raise RuntimeError(
                        f"{menu.pos_code} ICE 원가 계산 실패: "
                        f"{ice_snapshot.error_details}"
                    )

                # ICE 계산으로 덮인 Menu.cost를 HOT 대표 원가로 복원
                menu.refresh_from_db()

                menu.cost = hot_cost
                menu.cost_status = hot_status
                menu.cost_calculated_at = hot_calculated_at

                menu.save(
                    update_fields=[
                        "cost",
                        "cost_status",
                        "cost_calculated_at",
                    ]
                )

            else:

                # 분리하지 않는 메뉴는 STANDARD로 계산
                snapshot = calculate_menu_cost(
                    menu,
                    price_type=PRICE_TYPE,
                    as_of=AS_OF,
                    variant=Recipe.Variant.STANDARD,
                )

                if snapshot.status != RecipeCostSnapshot.Status.COMPLETE:
                    raise RuntimeError(
                        f"{menu.pos_code} STANDARD 원가 계산 실패: "
                        f"{snapshot.error_details}"
                    )

        # 3. 최종 건수 검증
        total_recipes = Recipe.objects.filter(
            menu__store_id=STORE_ID
        ).count()

        total_items = RecipeItem.objects.filter(
            recipe__menu__store_id=STORE_ID
        ).count()

        complete_snapshots = RecipeCostSnapshot.objects.filter(
            menu__store_id=STORE_ID,
            price_type=PRICE_TYPE,
            as_of=AS_OF,
            status=RecipeCostSnapshot.Status.COMPLETE,
        ).count()

        incomplete_snapshots = RecipeCostSnapshot.objects.filter(
            menu__store_id=STORE_ID,
            price_type=PRICE_TYPE,
            as_of=AS_OF,
            status=RecipeCostSnapshot.Status.INCOMPLETE,
        ).count()

        expected = {
            "created_recipes": 12,
            "created_items": 30,
            "total_recipes": 39,
            "total_items": 89,
            "complete_snapshots": 33,
            "incomplete_snapshots": 0,
        }

        actual = {
            "created_recipes": created_recipes,
            "created_items": created_items,
            "total_recipes": total_recipes,
            "total_items": total_items,
            "complete_snapshots": complete_snapshots,
            "incomplete_snapshots": incomplete_snapshots,
        }

        if actual != expected:
            raise RuntimeError(
                f"최종 검증 실패. 예상={expected}, 실제={actual}"
            )

    print("\n등록 및 원가 계산 완료")
    print(f"신규 레시피: {created_recipes}개")
    print(f"신규 재료 연결: {created_items}개")
    print("완료 원가 스냅샷: 33개")
    print("전체 레시피: 39개")
    print("전체 레시피 재료 연결: 89개")
    print("6개 분리 메뉴의 Menu.cost: HOT 대표 원가")
    print("ICE 원가: 별도 스냅샷 보존")
    print("모든 검증 통과 및 트랜잭션 커밋 완료")


def main():
    apply_mode = "--apply" in sys.argv[1:]

    try:
        menus, menu_by_code, standard_by_code = preflight()

        print_plan(
            menus,
            menu_by_code,
            standard_by_code,
        )

        if not apply_mode:
            print("\n읽기 전용 사전 점검 통과.")
            print("DB에는 아무것도 저장하지 않았습니다.")
            print("--apply를 붙이면 실제 등록합니다.")
            return

        apply_changes(
            menus,
            menu_by_code,
            standard_by_code,
        )

    except (ValidationError, RuntimeError, ValueError) as exc:
        print(f"\n중단: {exc}")
        raise SystemExit(1)


main()
