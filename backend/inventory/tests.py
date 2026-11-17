from datetime import date
from decimal import Decimal
from threading import Event, Thread, current_thread
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import close_old_connections, connection
from django.test import TestCase, TransactionTestCase, skipUnlessDBFeature

from inventory.models import (
    Ingredient,
    IngredientPurchasePrice,
    IngredientPurchaseSpec,
    Inventory,
    MenuIngredient,
    Recipe,
    RecipeCostLine,
    RecipeCostSnapshot,
    RecipeItem,
)
from inventory.services.costing import (
    calculate_menu_cost,
    save_ingredient,
    save_purchase_price,
    save_purchase_spec,
    save_recipe,
    save_recipe_item,
)
from store.models import Menu, Store


class RecipeCostingTests(TestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="recipe-costing-owner")
        self.store = Store.objects.create(owner=owner, name="Test store")
        self.menu = Menu.objects.create(
            store=self.store,
            pos_code="M001",
            name="Americano",
            category="Coffee",
            price=5000,
            serving_temperature=Menu.ServingTemperature.BOTH,
        )
        self.ingredient = save_ingredient(Ingredient(
            name="Coffee beans",
            base_unit=Ingredient.BaseUnit.GRAM,
        ))
        self.recipe = save_recipe(Recipe(
            menu=self.menu,
            variant=Recipe.Variant.STANDARD,
            version=1,
            valid_from=date(2025, 1, 1),
            yield_quantity=Decimal("1"),
        ))
        self.recipe_item = save_recipe_item(RecipeItem(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity_base=Decimal("100"),
        ))
        self.spec = IngredientPurchaseSpec(
            store=self.store,
            ingredient=self.ingredient,
            package_quantity=Decimal("1"),
            purchase_unit=IngredientPurchaseSpec.PurchaseUnit.KILOGRAM,
            base_quantity=Decimal("1000"),
            conversion_evidence="Metric unit conversion: 1 kg = 1000 g.",
        )
        save_purchase_spec(self.spec)

    def add_price(self, price_type, amount, *, valid_from=date(2025, 1, 1), valid_to=None):
        return save_purchase_price(IngredientPurchasePrice(
            purchase_spec=self.spec,
            price_type=price_type,
            amount=Decimal(amount),
            valid_from=valid_from,
            valid_to=valid_to,
            source="Test fixture",
            rationale="Test-only price; not a project purchase value.",
        ))

    def test_purchase_unit_conversion_only_allows_same_dimension(self):
        self.assertEqual(self.spec.expected_base_quantity(), Decimal("1000"))
        ml_ingredient = Ingredient.objects.create(
            name="Milk",
            base_unit=Ingredient.BaseUnit.MILLILITER,
        )
        mass_to_volume = IngredientPurchaseSpec(
            store=self.store,
            ingredient=ml_ingredient,
            package_quantity=Decimal("1"),
            purchase_unit=IngredientPurchaseSpec.PurchaseUnit.KILOGRAM,
            base_quantity=Decimal("1000"),
            conversion_evidence="Must not permit density-free conversion.",
        )
        with self.assertRaises(ValidationError):
            mass_to_volume.full_clean()

        unverified = IngredientPurchaseSpec(
            store=self.store,
            ingredient=ml_ingredient,
            package_quantity=Decimal("1"),
            purchase_unit=IngredientPurchaseSpec.PurchaseUnit.KILOGRAM,
        )
        unverified.full_clean()
        self.assertIsNone(unverified.base_quantity)

    def test_conversion_requires_evidence_and_expected_quantity(self):
        no_evidence = IngredientPurchaseSpec(
            store=self.store,
            ingredient=self.ingredient,
            package_quantity=Decimal("1"),
            purchase_unit=IngredientPurchaseSpec.PurchaseUnit.KILOGRAM,
            base_quantity=Decimal("1000"),
        )
        with self.assertRaises(ValidationError):
            no_evidence.full_clean()

        wrong_quantity = IngredientPurchaseSpec(
            store=self.store,
            ingredient=self.ingredient,
            package_quantity=Decimal("1"),
            purchase_unit=IngredientPurchaseSpec.PurchaseUnit.KILOGRAM,
            base_quantity=Decimal("1"),
            conversion_evidence="Invalid assumed conversion.",
        )
        with self.assertRaises(ValidationError):
            wrong_quantity.full_clean()

    def test_used_ingredient_base_unit_and_priced_spec_are_immutable(self):
        self.ingredient.base_unit = Ingredient.BaseUnit.MILLILITER
        with self.assertRaises(ValidationError):
            save_ingredient(self.ingredient)

        self.add_price(IngredientPurchasePrice.PriceType.ACTUAL, "3000")
        self.spec.package_quantity = Decimal("2")
        with self.assertRaises(ValidationError):
            save_purchase_spec(self.spec)

    def test_same_type_purchase_price_periods_cannot_overlap(self):
        self.add_price(
            IngredientPurchasePrice.PriceType.ACTUAL,
            "3000",
            valid_from=date(2025, 1, 1),
            valid_to=date(2025, 2, 1),
        )
        with self.assertRaises(ValidationError):
            IngredientPurchasePrice(
                purchase_spec=self.spec,
                price_type=IngredientPurchasePrice.PriceType.ACTUAL,
                amount=Decimal("3200"),
                valid_from=date(2025, 2, 1),
                source="Test fixture",
            ).save()

        self.add_price(
            IngredientPurchasePrice.PriceType.ESTIMATED,
            "2500",
            valid_from=date(2025, 1, 1),
        )
        self.assertEqual(IngredientPurchasePrice.objects.count(), 2)

    def test_used_price_cannot_be_changed_or_deleted_through_orm(self):
        price = self.add_price(IngredientPurchasePrice.PriceType.ACTUAL, "3000")
        snapshot = calculate_menu_cost(
            self.menu,
            price_type=IngredientPurchasePrice.PriceType.ACTUAL,
            as_of=date(2025, 3, 1),
        )
        original = {
            "amount": price.amount,
            "valid_from": price.valid_from,
            "valid_to": price.valid_to,
            "price_type": price.price_type,
        }

        for field, value in (
            ("amount", Decimal("3500")),
            ("valid_from", date(2025, 1, 2)),
            ("valid_to", date(2025, 2, 1)),
            ("price_type", IngredientPurchasePrice.PriceType.ESTIMATED),
        ):
            setattr(price, field, value)
            with self.assertRaises(ValidationError):
                price.save()
            price.refresh_from_db()

        with self.assertRaises(ValidationError):
            price.delete()
        with self.assertRaises(ValidationError):
            IngredientPurchasePrice.objects.filter(pk=price.pk).delete()
        with self.assertRaises(ValidationError):
            IngredientPurchasePrice.objects.filter(pk=price.pk).update(
                amount=Decimal("3500")
            )

        price.refresh_from_db()
        self.assertEqual(price.amount, original["amount"])
        self.assertEqual(price.valid_from, original["valid_from"])
        self.assertEqual(price.valid_to, original["valid_to"])
        self.assertEqual(price.price_type, original["price_type"])
        line = snapshot.lines.get()
        self.assertEqual(line.purchase_price_id, price.pk)
        self.assertEqual(line.purchase_price.amount, Decimal("3000"))

        later_price = self.add_price(
            IngredientPurchasePrice.PriceType.ACTUAL,
            "3500",
            valid_from=date(2025, 4, 1),
            valid_to=date(2025, 6, 30),
        )
        future_snapshot = calculate_menu_cost(
            self.menu,
            price_type=IngredientPurchasePrice.PriceType.ACTUAL,
            as_of=date(2025, 5, 1),
        )
        self.assertEqual(future_snapshot.status, RecipeCostSnapshot.Status.COMPLETE)
        self.assertEqual(
            future_snapshot.lines.get().purchase_price_id,
            later_price.pk,
        )
        expired_snapshot = calculate_menu_cost(
            self.menu,
            price_type=IngredientPurchasePrice.PriceType.ACTUAL,
            as_of=date(2025, 7, 1),
        )
        self.assertEqual(expired_snapshot.status, RecipeCostSnapshot.Status.INCOMPLETE)
        self.assertEqual(
            expired_snapshot.error_details[0]["code"],
            "purchase_price_missing",
        )

    def test_regular_orm_save_validates_price_type_and_recipe_item_quantity(self):
        invalid_price = IngredientPurchasePrice(
            purchase_spec=self.spec,
            price_type="UNKNOWN",
            amount=Decimal("3000"),
            valid_from=date(2025, 1, 1),
            source="Test fixture",
        )
        with self.assertRaises(ValidationError):
            invalid_price.save()

        item = RecipeItem.objects.get(pk=self.recipe_item.pk)
        item.quantity_base = Decimal("0")
        with self.assertRaises(ValidationError):
            item.save()

        invalid_spec = IngredientPurchaseSpec(
            store=self.store,
            ingredient=self.ingredient,
            package_quantity=Decimal("1"),
            purchase_unit=IngredientPurchaseSpec.PurchaseUnit.KILOGRAM,
            base_quantity=Decimal("1"),
            conversion_evidence="Incorrect conversion.",
        )
        with self.assertRaises(ValidationError):
            invalid_spec.save()
        with self.assertRaises(ValidationError):
            IngredientPurchaseSpec.objects.filter(pk=self.spec.pk).update(
                base_quantity=Decimal("1")
            )

    def test_active_recipe_periods_cannot_overlap_for_same_variant(self):
        overlapping = Recipe(
            menu=self.menu,
            variant=Recipe.Variant.STANDARD,
            version=2,
            valid_from=date(2025, 6, 1),
            yield_quantity=Decimal("1"),
        )
        with self.assertRaises(ValidationError):
            overlapping.save()

    def test_temperature_specific_recipe_requires_rationale_and_allowed_menu(self):
        hot_recipe = Recipe(
            menu=self.menu,
            variant=Recipe.Variant.HOT,
            version=1,
            valid_from=date(2025, 1, 1),
        )
        with self.assertRaises(ValidationError):
            save_recipe(hot_recipe)

        hot_recipe.variant_rationale = "Verified hot preparation uses a different dose."
        save_recipe(hot_recipe)
        self.assertEqual(hot_recipe.variant, Recipe.Variant.HOT)

    def test_estimated_cost_is_applied_and_snapshot_keeps_price_type(self):
        actual = self.add_price(IngredientPurchasePrice.PriceType.ACTUAL, "3000")
        estimated = self.add_price(IngredientPurchasePrice.PriceType.ESTIMATED, "2500")

        snapshot = calculate_menu_cost(
            self.menu,
            price_type=IngredientPurchasePrice.PriceType.ESTIMATED,
            as_of=date(2025, 3, 1),
        )

        self.assertEqual(snapshot.status, RecipeCostSnapshot.Status.COMPLETE)
        self.assertEqual(snapshot.price_type, IngredientPurchasePrice.PriceType.ESTIMATED)
        self.assertEqual(snapshot.unrounded_cost, Decimal("250.000000"))
        self.assertEqual(snapshot.final_cost, 250)
        self.assertEqual(snapshot.lines.count(), 1)
        line = snapshot.lines.get()
        self.assertEqual(line.purchase_price_id, estimated.pk)
        self.assertNotEqual(line.purchase_price_id, actual.pk)
        self.assertEqual(line.purchase_base_quantity, Decimal("1000.0000"))
        self.assertEqual(line.unit_cost, Decimal("2.50000000"))
        self.assertEqual(line.line_subtotal, Decimal("250.000000"))

        self.menu.refresh_from_db()
        self.assertEqual(self.menu.cost, 250)
        self.assertEqual(self.menu.cost_status, Menu.CostStatus.ESTIMATED)
        self.assertIsNotNone(self.menu.cost_calculated_at)
        self.assertEqual(self.menu.price, 5000)
        self.assertEqual(self.menu.pos_code, "M001")

        actual_snapshot = calculate_menu_cost(
            self.menu,
            price_type=IngredientPurchasePrice.PriceType.ACTUAL,
            as_of=date(2025, 3, 1),
        )
        self.assertEqual(actual_snapshot.final_cost, 300)
        self.assertTrue(all(
            line.purchase_price.price_type == actual_snapshot.price_type
            for line in actual_snapshot.lines.select_related("purchase_price")
        ))
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.cost, 300)
        self.assertEqual(self.menu.cost_status, Menu.CostStatus.ACTUAL)

    def test_unverified_conversion_creates_incomplete_snapshot_without_overwriting_cost(self):
        legacy_inventory = Inventory.objects.create(
            store=self.store,
            ingredient_name="Legacy unlinked ingredient",
            quantity=Decimal("5"),
            unit="kg",
        )
        legacy_menu_ingredient = MenuIngredient.objects.create(
            menu=self.menu,
            inventory=legacy_inventory,
            required_quantity=Decimal("1"),
        )
        self.assertIsNone(legacy_menu_ingredient.inventory.ingredient_id)

        self.spec.base_quantity = None
        self.spec.save(update_fields=("base_quantity",))
        save_purchase_price(IngredientPurchasePrice(
            purchase_spec=self.spec,
            price_type=IngredientPurchasePrice.PriceType.ESTIMATED,
            amount=Decimal("2500"),
            valid_from=date(2025, 1, 1),
            source="Test fixture",
            rationale="Test-only price; not a project purchase value.",
        ))
        self.menu.cost = 123
        self.menu.cost_status = Menu.CostStatus.ACTUAL
        self.menu.save(update_fields=("cost", "cost_status"))

        snapshot = calculate_menu_cost(
            self.menu,
            price_type=IngredientPurchasePrice.PriceType.ESTIMATED,
            as_of=date(2025, 3, 1),
        )

        self.assertEqual(snapshot.status, RecipeCostSnapshot.Status.INCOMPLETE)
        self.assertIsNone(snapshot.final_cost)
        self.assertEqual(snapshot.error_details[0]["code"], "unit_conversion_unverified")
        self.assertEqual(snapshot.lines.count(), 0)
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.cost, 123)
        self.assertEqual(self.menu.cost_status, Menu.CostStatus.ACTUAL)

    def test_stale_conversion_is_revalidated_during_costing(self):
        self.add_price(IngredientPurchasePrice.PriceType.ESTIMATED, "2500")
        table_name = connection.ops.quote_name(Ingredient._meta.db_table)
        with connection.cursor() as cursor:
            cursor.execute(
                f"UPDATE {table_name} SET base_unit = %s WHERE id = %s",
                [Ingredient.BaseUnit.MILLILITER, self.ingredient.pk],
            )

        snapshot = calculate_menu_cost(
            self.menu,
            price_type=IngredientPurchasePrice.PriceType.ESTIMATED,
            as_of=date(2025, 3, 1),
        )

        self.assertEqual(snapshot.status, RecipeCostSnapshot.Status.INCOMPLETE)
        self.assertEqual(snapshot.error_details[0]["code"], "unit_conversion_invalid")
        self.assertIsNone(self.menu.cost)

    def test_missing_purchase_price_does_not_apply_cost(self):
        self.menu.cost = 321
        self.menu.cost_status = Menu.CostStatus.UNVERIFIED
        self.menu.save(update_fields=("cost", "cost_status"))

        snapshot = calculate_menu_cost(
            self.menu,
            price_type=IngredientPurchasePrice.PriceType.ACTUAL,
            as_of=date(2025, 3, 1),
        )

        self.assertEqual(snapshot.status, RecipeCostSnapshot.Status.INCOMPLETE)
        self.assertEqual(snapshot.error_details[0]["code"], "purchase_price_missing")
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.cost, 321)
        self.assertEqual(self.menu.cost_status, Menu.CostStatus.UNVERIFIED)

    def test_cost_rounds_half_up_to_existing_integer_menu_cost(self):
        item = RecipeItem.objects.get(pk=self.recipe_item.pk)
        item.quantity_base = Decimal("1")
        save_recipe_item(item)
        rounding_spec = save_purchase_spec(IngredientPurchaseSpec(
            store=self.store,
            ingredient=self.ingredient,
            package_quantity=Decimal("2"),
            purchase_unit=IngredientPurchaseSpec.PurchaseUnit.GRAM,
            base_quantity=Decimal("2"),
            conversion_evidence="The package label confirms 2 g.",
        ))
        save_purchase_price(IngredientPurchasePrice(
            purchase_spec=rounding_spec,
            price_type=IngredientPurchasePrice.PriceType.ACTUAL,
            amount=Decimal("1"),
            valid_from=date(2025, 1, 1),
            source="Test fixture",
            rationale="Test-only price; not a project purchase value.",
        ))

        snapshot = calculate_menu_cost(
            self.menu,
            price_type=IngredientPurchasePrice.PriceType.ACTUAL,
            as_of=date(2025, 3, 1),
        )

        self.assertEqual(snapshot.unrounded_cost, Decimal("0.500000"))
        self.assertEqual(snapshot.final_cost, 1)
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.cost, 1)


@skipUnlessDBFeature("has_select_for_update")
class RecipeCostingConcurrencyTests(TransactionTestCase):
    def setUp(self):
        owner = get_user_model().objects.create_user(username="recipe-costing-lock-owner")
        self.store = Store.objects.create(owner=owner, name="Lock test store")
        self.menu = Menu.objects.create(
            store=self.store,
            pos_code="M001",
            name="Lock test menu",
            category="Coffee",
            price=5000,
            serving_temperature=Menu.ServingTemperature.BOTH,
        )
        self.ingredient = Ingredient.objects.create(
            name="Lock test ingredient",
            base_unit=Ingredient.BaseUnit.GRAM,
        )
        self.recipe = Recipe(
            menu=self.menu,
            variant=Recipe.Variant.STANDARD,
            version=1,
            valid_from=date(2025, 1, 1),
        )
        save_recipe(self.recipe)
        self.item = RecipeItem(
            recipe=self.recipe,
            ingredient=self.ingredient,
            quantity_base=Decimal("100"),
        )
        save_recipe_item(self.item)
        spec = IngredientPurchaseSpec(
            store=self.store,
            ingredient=self.ingredient,
            package_quantity=Decimal("1"),
            purchase_unit=IngredientPurchaseSpec.PurchaseUnit.KILOGRAM,
            base_quantity=Decimal("1000"),
            conversion_evidence="Metric unit conversion: 1 kg = 1000 g.",
        )
        save_purchase_spec(spec)
        save_purchase_price(IngredientPurchasePrice(
            purchase_spec=spec,
            price_type=IngredientPurchasePrice.PriceType.ACTUAL,
            amount=Decimal("3000"),
            valid_from=date(2025, 1, 1),
            source="Test fixture",
        ))

    def test_cost_calculation_serializes_recipe_item_update(self):
        calculation_locked = Event()
        release_calculation = Event()
        writer_started = Event()
        writer_finished = Event()
        results = {}
        failures = []
        original_full_clean = RecipeItem.full_clean

        def pause_calculation_validation(item, *args, **kwargs):
            if current_thread().name == "cost-calculation":
                calculation_locked.set()
                if not release_calculation.wait(timeout=10):
                    raise TimeoutError("Timed out waiting to release the calculation.")
            return original_full_clean(item, *args, **kwargs)

        def calculate():
            close_old_connections()
            try:
                results["snapshot"] = calculate_menu_cost(
                    Menu.objects.get(pk=self.menu.pk),
                    price_type=IngredientPurchasePrice.PriceType.ACTUAL,
                    as_of=date(2025, 3, 1),
                )
            except Exception as error:
                failures.append(error)
            finally:
                close_old_connections()

        def update_item():
            close_old_connections()
            try:
                writer_started.set()
                item = RecipeItem.objects.get(pk=self.item.pk)
                item.quantity_base = Decimal("200")
                save_recipe_item(item)
                writer_finished.set()
            except Exception as error:
                failures.append(error)
            finally:
                close_old_connections()

        with patch.object(RecipeItem, "full_clean", pause_calculation_validation):
            calculation_thread = Thread(target=calculate, name="cost-calculation")
            calculation_thread.start()
            try:
                self.assertTrue(calculation_locked.wait(timeout=5))
                writer_thread = Thread(target=update_item, name="recipe-item-writer")
                writer_thread.start()
                self.assertTrue(writer_started.wait(timeout=5))
                self.assertFalse(writer_finished.wait(timeout=0.3))
            finally:
                release_calculation.set()
            calculation_thread.join(timeout=10)
            writer_thread.join(timeout=10)

        self.assertFalse(calculation_thread.is_alive())
        self.assertFalse(writer_thread.is_alive())
        if failures:
            raise failures[0]

        snapshot = results["snapshot"]
        self.assertEqual(snapshot.status, RecipeCostSnapshot.Status.COMPLETE)
        self.assertEqual(snapshot.lines.get().quantity_base, Decimal("100.0000"))
        self.item.refresh_from_db()
        self.assertEqual(self.item.quantity_base, Decimal("200.0000"))
