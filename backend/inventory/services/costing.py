from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from inventory.models import (
    Ingredient,
    IngredientPurchasePrice,
    IngredientPurchaseSpec,
    Recipe,
    RecipeCostLine,
    RecipeCostSnapshot,
)
from store.models import Menu


FINAL_COST_QUANTUM = Decimal("1")
LINE_COST_QUANTUM = Decimal("0.000001")
UNIT_COST_QUANTUM = Decimal("0.00000001")


def save_ingredient(ingredient):
    with transaction.atomic():
        if ingredient.pk is not None:
            Ingredient.objects.select_for_update().get(pk=ingredient.pk)
        ingredient.full_clean()
        ingredient.save()
    return ingredient


def save_purchase_spec(spec):
    if spec.ingredient_id is None:
        raise ValidationError({"ingredient": "An ingredient is required."})
    spec.save()
    return spec


def save_purchase_price(price):
    """Validate a price while serializing edits for the same purchase spec."""
    if price.purchase_spec_id is None:
        raise ValidationError({"purchase_spec": "A purchase specification is required."})
    with transaction.atomic():
        IngredientPurchaseSpec.objects.select_for_update().get(pk=price.purchase_spec_id)
        price.full_clean()
        price.save()
    return price


def save_recipe(recipe):
    """Validate active recipe periods while serializing changes for one menu."""
    if recipe.menu_id is None:
        raise ValidationError({"menu": "A menu is required."})
    recipe.save()
    return recipe


def save_recipe_item(item):
    if item.recipe_id is None:
        raise ValidationError({"recipe": "A recipe is required."})
    item.save()
    return item


def _incomplete_snapshot(menu, price_type, as_of, recipe, errors):
    return RecipeCostSnapshot.objects.create(
        menu=menu,
        recipe=recipe,
        recipe_version=recipe.version if recipe else None,
        price_type=price_type,
        as_of=as_of,
        status=RecipeCostSnapshot.Status.INCOMPLETE,
        error_details=errors,
    )


def calculate_menu_cost(menu, *, price_type, as_of, variant=Recipe.Variant.STANDARD):
    """Calculate and apply a complete material-only cost, preserving prior cost otherwise."""
    if menu.pk is None:
        raise ValueError("A saved menu is required.")
    if price_type not in IngredientPurchasePrice.PriceType.values:
        raise ValidationError({"price_type": "Select ACTUAL or ESTIMATED."})
    if variant not in Recipe.Variant.values:
        raise ValidationError({"variant": "Select STANDARD, HOT, or ICE."})

    with transaction.atomic():
        menu = Menu.objects.select_for_update().get(pk=menu.pk)
        supported_variants = {
            Menu.ServingTemperature.BOTH: {Recipe.Variant.STANDARD, Recipe.Variant.HOT, Recipe.Variant.ICE},
            Menu.ServingTemperature.HOT: {Recipe.Variant.STANDARD, Recipe.Variant.HOT},
            Menu.ServingTemperature.ICE: {Recipe.Variant.STANDARD, Recipe.Variant.ICE},
            Menu.ServingTemperature.UNKNOWN: {Recipe.Variant.STANDARD},
        }.get(menu.serving_temperature, {Recipe.Variant.STANDARD})
        if variant not in supported_variants:
            raise ValidationError({"variant": "Recipe variant is not allowed for this menu."})

        effective_recipes = Recipe.objects.filter(
            menu=menu,
            is_active=True,
            valid_from__lte=as_of,
        ).filter(Q(valid_to__isnull=True) | Q(valid_to__gte=as_of)).select_for_update()
        recipes = list(effective_recipes.filter(variant=variant).order_by("-version"))
        if not recipes and variant != Recipe.Variant.STANDARD:
            recipes = list(effective_recipes.filter(variant=Recipe.Variant.STANDARD).order_by("-version"))

        if not recipes:
            return _incomplete_snapshot(
                menu,
                price_type,
                as_of,
                None,
                [{"code": "recipe_missing", "message": "No active recipe covers the calculation date."}],
            )
        if len(recipes) != 1:
            return _incomplete_snapshot(
                menu,
                price_type,
                as_of,
                None,
                [{"code": "recipe_ambiguous", "message": "Multiple active recipes cover the calculation date."}],
            )

        recipe = recipes[0]
        try:
            recipe.full_clean()
        except ValidationError:
            return _incomplete_snapshot(
                menu,
                price_type,
                as_of,
                recipe,
                [{"code": "recipe_invalid", "message": "The active recipe failed validation."}],
            )

        items = list(recipe.items.select_related("ingredient").order_by("pk"))
        if not items:
            return _incomplete_snapshot(
                menu,
                price_type,
                as_of,
                recipe,
                [{"code": "recipe_items_missing", "message": "The active recipe has no ingredient items."}],
            )

        specs_by_ingredient = {}
        locked_specs = list(
            IngredientPurchaseSpec.objects.select_for_update()
            .filter(
                store_id=menu.store_id,
                ingredient_id__in={item.ingredient_id for item in items},
            )
            .order_by("pk")
        )
        for spec in locked_specs:
            specs_by_ingredient.setdefault(spec.ingredient_id, []).append(spec)

        errors = []
        calculated_lines = []
        for item in items:
            try:
                item.full_clean()
            except ValidationError:
                errors.append({
                    "code": "recipe_item_invalid",
                    "ingredient_id": item.ingredient_id,
                    "message": "A recipe item failed validation.",
                })
                continue

            specs = specs_by_ingredient.get(item.ingredient_id, [])
            if not specs:
                errors.append({
                    "code": "purchase_spec_missing",
                    "ingredient_id": item.ingredient_id,
                    "message": "No purchase specification exists for this store and ingredient.",
                })
                continue

            verified_specs = []
            invalid_spec = False
            for spec in specs:
                try:
                    spec.full_clean()
                except ValidationError:
                    invalid_spec = True
                    continue
                if spec.base_quantity is not None:
                    verified_specs.append(spec)

            convertible_specs = verified_specs
            if not convertible_specs:
                errors.append({
                    "code": (
                        "unit_conversion_invalid"
                        if invalid_spec
                        else "unit_conversion_unverified"
                    ),
                    "ingredient_id": item.ingredient_id,
                    "message": (
                        "Purchase specification conversion is invalid or unverified."
                    ),
                })
                continue

            spec_ids = [spec.pk for spec in convertible_specs]
            prices = list(
                IngredientPurchasePrice.objects.filter(
                    purchase_spec_id__in=spec_ids,
                    price_type=price_type,
                    valid_from__lte=as_of,
                )
                .select_related("purchase_spec")
                .order_by("pk")
            )
            latest_start_by_spec = {}
            for price in prices:
                latest_start_by_spec[price.purchase_spec_id] = max(
                    latest_start_by_spec.get(price.purchase_spec_id, price.valid_from),
                    price.valid_from,
                )
            # A referenced row cannot be closed; a later start date supersedes it.
            prices = [
                price for price in prices
                if (
                    price.valid_from == latest_start_by_spec[price.purchase_spec_id]
                    and (price.valid_to is None or price.valid_to >= as_of)
                )
            ]
            if not prices:
                errors.append({
                    "code": "purchase_price_missing",
                    "ingredient_id": item.ingredient_id,
                    "message": f"No {price_type.lower()} purchase price is valid on the calculation date.",
                })
                continue
            if len(prices) != 1:
                errors.append({
                    "code": "purchase_price_ambiguous",
                    "ingredient_id": item.ingredient_id,
                    "message": "Multiple applicable purchase prices exist; select one purchase specification.",
                })
                continue

            price = prices[0]
            try:
                price.full_clean()
            except ValidationError:
                errors.append({
                    "code": "purchase_price_invalid",
                    "ingredient_id": item.ingredient_id,
                    "message": "The applicable purchase price failed validation.",
                })
                continue

            package_base_quantity = price.purchase_spec.base_quantity
            unit_cost = price.amount / package_base_quantity
            line_subtotal = (item.quantity_base * unit_cost).quantize(
                LINE_COST_QUANTUM,
                rounding=ROUND_HALF_UP,
            )
            calculated_lines.append({
                "recipe_item": item,
                "purchase_price": price,
                "quantity_base": item.quantity_base,
                "purchase_base_quantity": package_base_quantity,
                "unit_cost": unit_cost.quantize(
                    UNIT_COST_QUANTUM,
                    rounding=ROUND_HALF_UP,
                ),
                "line_subtotal": line_subtotal,
            })

        if errors:
            return _incomplete_snapshot(menu, price_type, as_of, recipe, errors)

        unrounded_cost = (
            sum((line["line_subtotal"] for line in calculated_lines), Decimal("0"))
            / recipe.yield_quantity
        ).quantize(LINE_COST_QUANTUM, rounding=ROUND_HALF_UP)
        final_cost = int(unrounded_cost.quantize(FINAL_COST_QUANTUM, rounding=ROUND_HALF_UP))
        snapshot = RecipeCostSnapshot.objects.create(
            menu=menu,
            recipe=recipe,
            recipe_version=recipe.version,
            price_type=price_type,
            as_of=as_of,
            status=RecipeCostSnapshot.Status.COMPLETE,
            unrounded_cost=unrounded_cost,
            final_cost=final_cost,
        )
        RecipeCostLine.objects.bulk_create([
            RecipeCostLine(snapshot=snapshot, **line)
            for line in calculated_lines
        ])

        menu.cost = final_cost
        menu.cost_status = (
            Menu.CostStatus.ACTUAL
            if price_type == IngredientPurchasePrice.PriceType.ACTUAL
            else Menu.CostStatus.ESTIMATED
        )
        menu.cost_calculated_at = timezone.now()
        menu.save(update_fields=("cost", "cost_status", "cost_calculated_at"))
        return snapshot
