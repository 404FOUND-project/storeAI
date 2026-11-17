from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from sales.models import Sales, SalesItem
from store.models import Menu, Store


class SalesItemServingTemperatureTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        user_model = get_user_model()
        cls.owner = user_model.objects.create_user(username="temperature-test")
        cls.store = Store.objects.create(owner=cls.owner, name="temperature-test-store")
        cls.both_menu = Menu.objects.create(
            store=cls.store, name="both", category="drink", price=100,
            serving_temperature=Menu.ServingTemperature.BOTH,
        )
        cls.ice_menu = Menu.objects.create(
            store=cls.store, name="ice", category="drink", price=100,
            serving_temperature=Menu.ServingTemperature.ICE,
        )
        cls.hot_menu = Menu.objects.create(
            store=cls.store, name="hot", category="drink", price=100,
            serving_temperature=Menu.ServingTemperature.HOT,
        )
        cls.unknown_menu = Menu.objects.create(
            store=cls.store, name="unknown", category="dessert", price=100,
            serving_temperature=Menu.ServingTemperature.UNKNOWN,
        )
        cls.sale = Sales.objects.create(
            store=cls.store, sold_at=timezone.now(), total_amount=1000,
        )

    def item(self, menu, temperature):
        return SalesItem(
            sales=self.sale,
            menu=menu,
            quantity=1,
            unit_price=menu.price,
            serving_temperature=temperature,
        )

    def test_save_accepts_supported_temperatures(self):
        for menu, temperature in (
            (self.both_menu, SalesItem.ServingTemperature.HOT),
            (self.both_menu, SalesItem.ServingTemperature.ICE),
            (self.ice_menu, SalesItem.ServingTemperature.ICE),
            (self.hot_menu, SalesItem.ServingTemperature.HOT),
            (self.unknown_menu, None),
        ):
            with self.subTest(menu=menu.name, temperature=temperature):
                self.item(menu, temperature).save()
        self.assertEqual(SalesItem.objects.count(), 5)

    def test_save_rejects_unsupported_temperatures(self):
        for menu, temperature in (
            (self.ice_menu, SalesItem.ServingTemperature.HOT),
            (self.hot_menu, SalesItem.ServingTemperature.ICE),
            (self.unknown_menu, SalesItem.ServingTemperature.HOT),
            (self.unknown_menu, SalesItem.ServingTemperature.ICE),
        ):
            with self.subTest(menu=menu.name, temperature=temperature):
                with self.assertRaises(ValidationError):
                    self.item(menu, temperature).save()
        self.assertEqual(SalesItem.objects.count(), 0)

    def test_bulk_create_uses_same_rules(self):
        accepted = [
            self.item(self.both_menu, SalesItem.ServingTemperature.HOT),
            self.item(self.both_menu, SalesItem.ServingTemperature.ICE),
            self.item(self.ice_menu, SalesItem.ServingTemperature.ICE),
            self.item(self.unknown_menu, None),
        ]
        SalesItem.objects.bulk_create(accepted)
        self.assertEqual(SalesItem.objects.count(), 4)

        SalesItem.objects.all().delete()
        rejected = [
            self.item(self.both_menu, SalesItem.ServingTemperature.HOT),
            self.item(self.ice_menu, SalesItem.ServingTemperature.HOT),
        ]
        with self.assertRaises(ValidationError):
            SalesItem.objects.bulk_create(rejected)
        self.assertEqual(SalesItem.objects.count(), 0)

    def test_unknown_allows_only_null_for_save_and_bulk_create(self):
        self.item(self.unknown_menu, None).save()
        SalesItem.objects.all().delete()
        for method in ("save", "bulk_create"):
            with self.subTest(method=method):
                item = self.item(self.unknown_menu, SalesItem.ServingTemperature.ICE)
                with self.assertRaises(ValidationError):
                    if method == "save":
                        item.save()
                    else:
                        SalesItem.objects.bulk_create([item])
                self.assertEqual(SalesItem.objects.count(), 0)

    def test_missing_menu_is_rejected_without_partial_bulk_insert(self):
        valid = self.item(self.both_menu, SalesItem.ServingTemperature.HOT)
        missing = SalesItem(
            sales=self.sale,
            menu_id=999999,
            quantity=1,
            unit_price=100,
            serving_temperature=SalesItem.ServingTemperature.HOT,
        )
        with self.assertRaises(ValidationError):
            SalesItem.objects.bulk_create([valid, missing])
        self.assertEqual(SalesItem.objects.count(), 0)

    def test_database_error_rolls_back_all_bulk_batches(self):
        first = self.item(self.both_menu, SalesItem.ServingTemperature.HOT)
        second = self.item(self.both_menu, SalesItem.ServingTemperature.ICE)
        first.pk = 98765
        second.pk = 98765
        with self.assertRaises(IntegrityError):
            SalesItem.objects.bulk_create([first, second], batch_size=1)
        self.assertEqual(SalesItem.objects.count(), 0)

    def test_bulk_update_uses_same_rules(self):
        item = self.item(self.both_menu, SalesItem.ServingTemperature.HOT)
        item.save()
        item.menu = self.ice_menu
        item.serving_temperature = SalesItem.ServingTemperature.HOT
        with self.assertRaises(ValidationError):
            SalesItem.objects.bulk_update([item], ["menu", "serving_temperature"])
        item.refresh_from_db()
        self.assertEqual(item.menu_id, self.both_menu.pk)
        self.assertEqual(item.serving_temperature, SalesItem.ServingTemperature.HOT)

    def test_queryset_update_uses_same_rules(self):
        item = self.item(self.ice_menu, SalesItem.ServingTemperature.ICE)
        item.save()
        with self.assertRaises(ValidationError):
            SalesItem.objects.filter(pk=item.pk).update(serving_temperature="HOT")
        item.refresh_from_db()
        self.assertEqual(item.serving_temperature, SalesItem.ServingTemperature.ICE)
