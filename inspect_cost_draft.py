
from pathlib import Path
import json
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parent

def show_file(relative_path):
    path = ROOT / relative_path
    print(f"\n{'=' * 80}\nFILE: {relative_path}\n{'=' * 80}")
    if not path.exists():
        print("NOT FOUND")
        return
    print(path.read_text(encoding="utf-8"))

def main():
    excel = ROOT / "data/inventory/404dabang_ingredient_purchase_cost_draft.xlsx"

    print("EXCEL EXISTS:", excel.exists())
    if excel.exists():
        wb = load_workbook(excel, data_only=True, read_only=True)
        print("\nWORKBOOK SHEETS:", wb.sheetnames)

        for ws in wb.worksheets:
            print(f"\n{'=' * 80}")
            print(f"SHEET: {ws.title} | ROWS: {ws.max_row} | COLS: {ws.max_column}")
            print("=" * 80)
            for row in ws.iter_rows(values_only=True):
                print(" | ".join("" if v is None else str(v) for v in row))

        wb.close()

    show_file("backend/inventory/models.py")
    show_file("backend/inventory/services/costing.py")

    seed_path = ROOT / "data/inventory/404dabang_ingredient_recipe_seed_v1.json"
    print(f"\n{'=' * 80}\nSEED JSON SUMMARY\n{'=' * 80}")

    if seed_path.exists():
        seed = json.loads(seed_path.read_text(encoding="utf-8"))
        print("TOP LEVEL KEYS:", list(seed.keys()))
        print("INGREDIENT COUNT:", len(seed.get("ingredients", [])))
        print("RECIPE COUNT:", len(seed.get("recipes", [])))
        print("RECIPE ITEM COUNT:", sum(
            len(recipe.get("items", []))
            for recipe in seed.get("recipes", [])
        ))
        print("INGREDIENTS:")
        for item in seed.get("ingredients", []):
            print(item)
        print("RECIPES:")
        for recipe in seed.get("recipes", []):
            print(recipe)
    else:
        print("SEED JSON NOT FOUND")

    show_file("backend/scripts/register_404dabang_seed.py")


if __name__ == "__main__":
    main()


print("\n" + "=" * 80)
print("AIVEN DB PURCHASE DATA CHECK")
print("=" * 80)

import os
import sys

BACKEND_DIR = Path(__file__).resolve().parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "analysis.config.settings")

import django
django.setup()

from inventory.models import (
    Ingredient,
    IngredientPurchaseSpec,
    IngredientPurchasePrice,
)

print("재료 수:", Ingredient.objects.count())
print("구매 규격 수:", IngredientPurchaseSpec.objects.count())
print("구매 가격 수:", IngredientPurchasePrice.objects.count())

print("\n[재료별 구매 데이터]")

for ingredient in Ingredient.objects.order_by("name"):
    specs = IngredientPurchaseSpec.objects.filter(
        ingredient=ingredient
    )

    print(f"\n재료: {ingredient.name} ({ingredient.base_unit})")

    if not specs.exists():
        print("  구매 규격: 없음")
        continue

    for spec in specs:
        print("  구매 규격:", spec.pk)
        print("  기준 수량:", spec.base_quantity)

        prices = IngredientPurchasePrice.objects.filter(
            purchase_spec=spec
        )

        if not prices.exists():
            print("  구매 가격: 없음")
        else:
            for price in prices:
                print(
                    "  구매 가격:",
                    price.amount,
                    "| 유형:",
                    price.price_type,
                    "| 시작일:",
                    price.valid_from,
                    "| 종료일:",
                    price.valid_to,
                )
