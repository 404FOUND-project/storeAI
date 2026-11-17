import argparse
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_DIR.parent
SEED_PATH = PROJECT_ROOT / "data" / "inventory" / "404dabang_ingredient_recipe_seed_v1.json"
REQUIRED_MIGRATIONS = {
    ("store", "0006_menu_cost_status"),
    ("inventory", "0003_recipe_costing"),
}
EXPECTED_MENU_CODES = {f"M{number:03d}" for number in range(1, 28)}
EXPECTED_INGREDIENTS = 27
EXPECTED_RECIPES = 27
EXPECTED_RECIPE_ITEMS = 59
EXPECTED_ITEMS_PER_MENU = [
    4, 1, 1, 2, 2, 3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 1, 4, 2, 3, 1, 4, 2, 2, 2, 3
]


class RegistrationError(Exception):
    pass


def load_seed():
    try:
        seed = json.loads(SEED_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RegistrationError(f"Could not read seed JSON: {type(exc).__name__}") from exc

    ingredients = seed.get("ingredients", [])
    recipes = seed.get("recipes", [])
    ingredient_by_name = {item["name"]: item for item in ingredients}

    if len(ingredients) != EXPECTED_INGREDIENTS or len(ingredient_by_name) != EXPECTED_INGREDIENTS:
        raise RegistrationError("Seed must contain 27 uniquely named ingredients.")
    if {item["base_unit"] for item in ingredients} - {"g", "ml", "ea"}:
        raise RegistrationError("Seed contains an unsupported ingredient base unit.")
    if len(recipes) != EXPECTED_RECIPES:
        raise RegistrationError("Seed must contain 27 recipes.")
    if {item["menu_code"] for item in recipes} != EXPECTED_MENU_CODES:
        raise RegistrationError("Seed must cover M001-M027 exactly once.")
    purchase_data = seed.get("purchase_data", {})
    if purchase_data.get("purchase_specs") or purchase_data.get("purchase_prices"):
        raise RegistrationError("Purchase specs and prices must remain unregistered.")

    total_items = 0
    used_ingredients = set()
    for recipe in recipes:
        if recipe["variant"] != "STANDARD":
            raise RegistrationError(f"{recipe['menu_code']} must use STANDARD variant.")
        if recipe["valid_from"] != "2025-01-01" or recipe.get("valid_to") is not None:
            raise RegistrationError(f"{recipe['menu_code']} has an unexpected validity range.")
        if int(recipe["version"]) <= 0 or Decimal(str(recipe["yield_quantity"])) <= 0:
            raise RegistrationError(f"{recipe['menu_code']} has an invalid version or yield.")

        seen_items = set()
        for item in recipe["items"]:
            ingredient = ingredient_by_name.get(item["ingredient"])
            if ingredient is None:
                raise RegistrationError(
                    f"{recipe['menu_code']} references an unknown ingredient."
                )
            if item["ingredient"] in seen_items:
                raise RegistrationError(
                    f"{recipe['menu_code']} repeats an ingredient."
                )
            seen_items.add(item["ingredient"])
            used_ingredients.add(item["ingredient"])
            if item["unit"] != ingredient["base_unit"]:
                raise RegistrationError(
                    f"{recipe['menu_code']} has a unit/base-unit mismatch."
                )
            if Decimal(str(item["quantity_base"])) <= 0:
                raise RegistrationError(f"{recipe['menu_code']} has a non-positive quantity.")
            total_items += 1

    if total_items != EXPECTED_RECIPE_ITEMS:
        raise RegistrationError("Seed must contain exactly 59 recipe items.")
    if [len(recipe["items"]) for recipe in recipes] != EXPECTED_ITEMS_PER_MENU:
        raise RegistrationError("Seed recipe-item counts do not match M001-M027.")
    if used_ingredients != set(ingredient_by_name):
        raise RegistrationError("Every seed ingredient must be used by at least one recipe.")
    return seed, ingredient_by_name


def check_migrations(using):
    from django.db import connections
    from django.db.migrations.recorder import MigrationRecorder

    recorder = MigrationRecorder(connections[using])
    if not recorder.has_table():
        raise RegistrationError("django_migrations is unavailable; apply prerequisites first.")
    missing = REQUIRED_MIGRATIONS - set(recorder.applied_migrations())
    if missing:
        pending = ", ".join(f"{app}.{name}" for app, name in sorted(missing))
        raise RegistrationError(f"Required migrations are not applied: {pending}")


def prepare_plan(seed, ingredient_by_name, using, lock_rows):
    from django.db.models import Prefetch
    from inventory.models import Ingredient, Recipe, RecipeItem
    from store.models import Menu, Store

    stores = list(Store.objects.using(using).filter(name=seed["store_label"]))
    if len(stores) != 1:
        raise RegistrationError("Expected exactly one target Store.")
    store = stores[0]
    if lock_rows:
        store = Store.objects.using(using).select_for_update().get(pk=store.pk)

    codes = [recipe["menu_code"] for recipe in seed["recipes"]]
    menus_query = Menu.objects.using(using).filter(
        store_id=store.pk,
        pos_code__in=codes,
    )
    if lock_rows:
        menus_query = menus_query.select_for_update()
    menus = list(menus_query.order_by("pos_code"))
    menu_by_code = {menu.pos_code: menu for menu in menus}
    if set(menu_by_code) != EXPECTED_MENU_CODES or len(menus) != EXPECTED_RECIPES:
        raise RegistrationError("Target Store must have exactly one Menu for every seed code.")

    for recipe_data in seed["recipes"]:
        menu = menu_by_code[recipe_data["menu_code"]]
        if menu.name != recipe_data["menu_name"]:
            raise RegistrationError(
                f"Menu name does not match the seed for {recipe_data['menu_code']}."
            )

    ingredient_names = list(ingredient_by_name)
    ingredients_query = Ingredient.objects.using(using).filter(name__in=ingredient_names)
    if lock_rows:
        ingredients_query = ingredients_query.select_for_update()
    existing_ingredients = list(ingredients_query)
    ingredient_rows = {item.name: item for item in existing_ingredients}
    if len(ingredient_rows) != len(existing_ingredients):
        raise RegistrationError("Duplicate ingredient names exist in the database.")

    for name, row in ingredient_rows.items():
        if row.base_unit != ingredient_by_name[name]["base_unit"]:
            raise RegistrationError(f"Existing ingredient has a different base unit: {name}.")

    recipes_query = Recipe.objects.using(using).filter(
        menu_id__in=[menu.pk for menu in menus],
    ).prefetch_related(
        Prefetch("items", queryset=RecipeItem.objects.using(using).select_related("ingredient"))
    )
    if lock_rows:
        recipes_query = recipes_query.select_for_update()
    existing_recipes = list(recipes_query)
    recipe_plans = []

    for recipe_data in seed["recipes"]:
        menu = menu_by_code[recipe_data["menu_code"]]
        version = int(recipe_data["version"])
        start = date.fromisoformat(recipe_data["valid_from"])
        matching_key = [
            row for row in existing_recipes
            if row.menu_id == menu.pk
            and row.variant == recipe_data["variant"]
            and row.version == version
        ]
        if len(matching_key) > 1:
            raise RegistrationError(f"Duplicate recipe version exists for {recipe_data['menu_code']}.")

        expected_items = {
            item["ingredient"]: Decimal(str(item["quantity_base"]))
            for item in recipe_data["items"]
        }
        if matching_key:
            row = matching_key[0]
            row_items = {
                item.ingredient.name: Decimal(item.quantity_base)
                for item in row.items.all()
            }
            exact = (
                row.valid_from == start
                and row.valid_to is None
                and row.is_active
                and Decimal(row.yield_quantity) == Decimal(str(recipe_data["yield_quantity"]))
                and row_items == expected_items
            )
            if not exact:
                raise RegistrationError(
                    f"Existing recipe conflicts with the seed for {recipe_data['menu_code']}."
                )
            other_overlaps = [
                other for other in existing_recipes
                if other.pk != row.pk
                and other.menu_id == menu.pk
                and other.variant == recipe_data["variant"]
                and other.is_active
                and (other.valid_to is None or other.valid_to >= start)
            ]
            if other_overlaps:
                raise RegistrationError(
                    f"Active STANDARD recipe validity overlaps for {recipe_data['menu_code']}."
                )
            recipe_plans.append((recipe_data, menu, row))
            continue

        overlapping = [
            row for row in existing_recipes
            if row.menu_id == menu.pk
            and row.variant == recipe_data["variant"]
            and row.is_active
            and (row.valid_to is None or row.valid_to >= start)
        ]
        if overlapping:
            raise RegistrationError(
                f"Active STANDARD recipe validity overlaps for {recipe_data['menu_code']}."
            )
        recipe_plans.append((recipe_data, menu, None))

    return store, menu_by_code, ingredient_rows, recipe_plans


def execute(apply):
    import django

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "analysis.config.settings")
    if str(BACKEND_DIR) not in sys.path:
        sys.path.insert(0, str(BACKEND_DIR))
    django.setup()

    from django.db import DEFAULT_DB_ALIAS, transaction
    from inventory.models import Ingredient, Recipe, RecipeItem
    from store.models import Menu

    using = DEFAULT_DB_ALIAS
    seed, ingredient_by_name = load_seed()
    check_migrations(using)

    if apply:
        with transaction.atomic(using=using):
            store, menu_by_code, ingredient_rows, recipe_plans = prepare_plan(
                seed, ingredient_by_name, using, lock_rows=True
            )
            for name, data in ingredient_by_name.items():
                if name in ingredient_rows:
                    continue
                ingredient = Ingredient(name=name, base_unit=data["base_unit"])
                ingredient.save(using=using)
                ingredient_rows[name] = ingredient

            created_recipes = 0
            created_items = 0
            recipe_ids = []
            for recipe_data, menu, existing in recipe_plans:
                if existing is not None:
                    recipe_ids.append(existing.pk)
                    continue
                recipe = Recipe(
                    menu=menu,
                    variant=recipe_data["variant"],
                    version=int(recipe_data["version"]),
                    valid_from=date.fromisoformat(recipe_data["valid_from"]),
                    valid_to=None,
                    yield_quantity=Decimal(str(recipe_data["yield_quantity"])),
                    is_active=True,
                )
                recipe.save(using=using)
                created_recipes += 1
                recipe_ids.append(recipe.pk)
                for item_data in recipe_data["items"]:
                    item = RecipeItem(
                        recipe=recipe,
                        ingredient=ingredient_rows[item_data["ingredient"]],
                        quantity_base=Decimal(str(item_data["quantity_base"])),
                    )
                    item.save(using=using)
                    created_items += 1

            expected_codes = set(menu_by_code)
            unchanged_temperatures = set(
                Menu.objects.using(using)
                .filter(store_id=store.pk, pos_code__in=expected_codes)
                .values_list("pos_code", "serving_temperature")
            ) == {
                (code, menu.serving_temperature)
                for code, menu in menu_by_code.items()
            }
            if not unchanged_temperatures:
                raise RegistrationError("Menu serving_temperature changed during registration.")

            final_recipes = list(
                Recipe.objects.using(using)
                .filter(pk__in=recipe_ids)
                .prefetch_related("items__ingredient")
            )
            final_item_count = sum(recipe.items.count() for recipe in final_recipes)
            if len(final_recipes) != EXPECTED_RECIPES or final_item_count != EXPECTED_RECIPE_ITEMS:
                raise RegistrationError("Post-write count verification failed; transaction rolled back.")

        print(
            f"Committed: ingredients={len(ingredient_rows)}, "
            f"recipes={len(final_recipes)}, recipe_items={final_item_count}; "
            f"created_recipes={created_recipes}, created_items={created_items}."
        )
        return

    _, _, ingredient_rows, recipe_plans = prepare_plan(
        seed, ingredient_by_name, using, lock_rows=False
    )
    existing_recipe_count = sum(plan[2] is not None for plan in recipe_plans)
    print(
        "Read-only preflight passed. "
        f"ingredients_existing={len(ingredient_rows)}, "
        f"ingredients_to_create={EXPECTED_INGREDIENTS - len(ingredient_rows)}, "
        f"recipes_exact_existing={existing_recipe_count}, "
        f"recipes_to_create={EXPECTED_RECIPES - existing_recipe_count}, "
        f"recipe_items_expected={EXPECTED_RECIPE_ITEMS}. "
        "No rows were written; pass --apply to register."
    )


def main():
    parser = argparse.ArgumentParser(
        description="Register the 404dabang development ingredient and recipe seed."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Create missing rows in one atomic transaction. Default is read-only preflight.",
    )
    args = parser.parse_args()
    try:
        execute(apply=args.apply)
    except RegistrationError as exc:
        print(f"Registration stopped: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
