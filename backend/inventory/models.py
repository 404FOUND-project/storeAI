from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import models
from django.db import router, transaction
from django.db.models import Q
from django.core.validators import MinValueValidator
from store.models import Store, Menu


class Inventory(models.Model):
    store = models.ForeignKey(
        Store, 
        on_delete=models.CASCADE, 
        related_name='inventories'
    )

    # 제품명
    ingredient_name = models.CharField(
        max_length=100
    )
    ingredient = models.ForeignKey(
        "Ingredient",
        on_delete=models.SET_NULL,
        related_name="inventory_records",
        null=True,
        blank=True,
    )

    # 현재 재고량
    quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2,
    )

    # 재고 단위 (예: kg, g, L, ml 등)
    unit = models.CharField(max_length=20)

    # 유통기한
    expiration_date = models.DateField(
        null=True,
        blank=True
    )

    update_at = models.DateTimeField(auto_now=True)
    create_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.store.name} - {self.ingredient_name}"


class ValidatedWriteQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Use model save() so validation and locking run.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Bulk updates bypass validation; save records individually.")

    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Use model save() so validation and locking run.")


class MenuIngredient(models.Model):
    menu = models.ForeignKey(
        Menu, 
        on_delete=models.CASCADE, 
        related_name='ingredients'
    )

    inventory = models.ForeignKey(
        Inventory, 
        on_delete=models.CASCADE, 
        related_name='menu_ingredients'
    )

    # 메뉴에 필요한 재료의 양
    required_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=2
    )

    def __str__(self):
        return f"{self.menu.name} - {self.inventory.ingredient_name}"


class Ingredient(models.Model):
    class BaseUnit(models.TextChoices):
        GRAM = "g", "Gram"
        MILLILITER = "ml", "Milliliter"
        EACH = "ea", "Each"

    name = models.CharField(max_length=100, unique=True)
    base_unit = models.CharField(max_length=2, choices=BaseUnit.choices)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ValidatedWriteQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(base_unit__in=("g", "ml", "ea")),
                name="ingredient_base_unit_valid",
            ),
        ]
        ordering = ("name",)

    def clean(self):
        super().clean()
        if self.pk is None:
            return
        previous_unit = type(self).objects.filter(pk=self.pk).values_list(
            "base_unit",
            flat=True,
        ).first()
        if (
            previous_unit is not None
            and previous_unit != self.base_unit
            and (
                self.purchase_specs.exists()
                or self.recipe_items.exists()
                or self.inventory_records.exists()
            )
        ):
            raise ValidationError({
                "base_unit": (
                    "A referenced ingredient's base unit cannot change; "
                    "create a new ingredient and migrate its references."
                )
            })

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            if self.pk is not None:
                type(self).objects.using(using).select_for_update().get(pk=self.pk)
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.name} ({self.base_unit})"


class IngredientPurchaseSpec(models.Model):
    class PurchaseUnit(models.TextChoices):
        GRAM = "g", "Gram"
        KILOGRAM = "kg", "Kilogram"
        MILLILITER = "ml", "Milliliter"
        LITER = "L", "Liter"
        EACH = "ea", "Each"

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="ingredient_purchase_specs",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="purchase_specs",
    )
    package_quantity = models.DecimalField(
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    purchase_unit = models.CharField(max_length=2, choices=PurchaseUnit.choices)
    base_quantity = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    conversion_evidence = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ValidatedWriteQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(package_quantity__gt=0),
                name="purchase_spec_package_positive",
            ),
            models.CheckConstraint(
                condition=Q(base_quantity__isnull=True) | Q(base_quantity__gt=0),
                name="purchase_spec_base_positive",
            ),
        ]
        ordering = ("ingredient__name", "package_quantity")

    def expected_base_quantity(self):
        factors = {
            (Ingredient.BaseUnit.GRAM, self.PurchaseUnit.GRAM): Decimal("1"),
            (Ingredient.BaseUnit.GRAM, self.PurchaseUnit.KILOGRAM): Decimal("1000"),
            (Ingredient.BaseUnit.MILLILITER, self.PurchaseUnit.MILLILITER): Decimal("1"),
            (Ingredient.BaseUnit.MILLILITER, self.PurchaseUnit.LITER): Decimal("1000"),
            (Ingredient.BaseUnit.EACH, self.PurchaseUnit.EACH): Decimal("1"),
        }
        factor = factors.get((self.ingredient.base_unit, self.purchase_unit))
        if factor is None:
            return None
        return self.package_quantity * factor

    def clean(self):
        super().clean()
        if self.ingredient_id is None or self.package_quantity is None:
            return

        if self.pk is not None and self.prices.exists():
            previous = type(self).objects.filter(pk=self.pk).values(
                "ingredient_id",
                "package_quantity",
                "purchase_unit",
                "base_quantity",
            ).first()
            if previous and any(
                previous[field] != getattr(self, field)
                for field in (
                    "ingredient_id",
                    "package_quantity",
                    "purchase_unit",
                    "base_quantity",
                )
            ):
                raise ValidationError(
                    "A purchase specification with price history is immutable; "
                    "create a new specification for changed packaging or conversion."
                )

        expected = self.expected_base_quantity()
        if expected is None:
            if self.base_quantity is not None:
                raise ValidationError({
                    "base_quantity": (
                        "Purchase and recipe units have incompatible dimensions; "
                        "mass-to-volume conversion is not supported."
                    )
                })
            return

        if self.base_quantity is not None:
            if self.base_quantity != expected:
                raise ValidationError({
                    "base_quantity": (
                        f"Expected {expected} {self.ingredient.base_unit} "
                        "from the declared package size."
                    )
                })
            if not self.conversion_evidence.strip():
                raise ValidationError({
                    "conversion_evidence": (
                        "Record the basis for the purchase-to-base-unit conversion."
                    )
                })

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            old_ingredient_id = None
            if self.pk is not None:
                old_ingredient_id = type(self).objects.using(using).filter(
                    pk=self.pk
                ).values_list("ingredient_id", flat=True).first()
            if self.pk is not None:
                type(self).objects.using(using).select_for_update().get(pk=self.pk)
                current_ingredient_id = type(self).objects.using(using).filter(
                    pk=self.pk
                ).values_list("ingredient_id", flat=True).get()
                if current_ingredient_id != old_ingredient_id:
                    raise ValidationError(
                        "The purchase specification changed concurrently; reload it and retry."
                    )
            ingredient_ids = {self.ingredient_id}
            if old_ingredient_id is not None:
                ingredient_ids.add(old_ingredient_id)
            list(
                Ingredient.objects.using(using)
                .select_for_update()
                .filter(pk__in=ingredient_ids)
                .order_by("pk")
            )
            self.full_clean()
            return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ingredient.name} - {self.package_quantity} {self.purchase_unit}"


class GuardedHistoryQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError("Use model save() so history validation and locking run.")

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError("Bulk updates bypass history validation; save records individually.")


class IngredientPurchasePriceQuerySet(GuardedHistoryQuerySet):
    def bulk_create(self, objs, **kwargs):
        raise ValidationError("Use save_purchase_price() to validate each price period.")

    def delete(self):
        using = self.db
        with transaction.atomic(using=using):
            spec_ids = sorted(set(self.values_list("purchase_spec_id", flat=True)))
            list(
                IngredientPurchaseSpec.objects.using(using)
                .select_for_update()
                .filter(pk__in=spec_ids)
                .order_by("pk")
            )
            if self.filter(cost_lines__isnull=False).exists():
                raise ValidationError("A price referenced by a cost snapshot cannot be deleted.")
            return super().delete()


class IngredientPurchasePrice(models.Model):
    class PriceType(models.TextChoices):
        ACTUAL = "ACTUAL", "Actual"
        ESTIMATED = "ESTIMATED", "Estimated"

    purchase_spec = models.ForeignKey(
        IngredientPurchaseSpec,
        on_delete=models.PROTECT,
        related_name="prices",
    )
    price_type = models.CharField(max_length=9, choices=PriceType.choices)
    amount = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    source = models.CharField(max_length=255, blank=True)
    rationale = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = IngredientPurchasePriceQuerySet.as_manager()

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="purchase_price_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gte=models.F("valid_from")),
                name="purchase_price_dates_valid",
            ),
        ]
        ordering = ("-valid_from", "-pk")

    def clean(self):
        super().clean()
        if self.valid_from is None or self.purchase_spec_id is None:
            return
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValidationError({"valid_to": "End date cannot precede start date."})
        if not self.source.strip():
            raise ValidationError({"source": "Record the source of the purchase price."})
        if self.price_type == self.PriceType.ESTIMATED and not self.rationale.strip():
            raise ValidationError({
                "rationale": "Record the basis for an estimated purchase price."
            })

        if self.pk is not None:
            previous = type(self).objects.filter(pk=self.pk).values(
                "purchase_spec_id",
                "price_type",
                "amount",
                "valid_from",
                "valid_to",
                "source",
                "rationale",
            ).first()
            if previous:
                if previous["purchase_spec_id"] != self.purchase_spec_id:
                    raise ValidationError({
                        "purchase_spec": "A price history row cannot be moved to another specification."
                    })
                if self.cost_lines.exists() and any(
                    previous[field] != getattr(self, field)
                    for field in (
                        "price_type",
                        "amount",
                        "valid_from",
                        "valid_to",
                        "source",
                        "rationale",
                    )
                ):
                    raise ValidationError(
                        "A price referenced by a cost snapshot is immutable; "
                        "create a new price history row."
                    )

        overlapping = type(self).objects.filter(
            purchase_spec_id=self.purchase_spec_id,
            price_type=self.price_type,
        ).exclude(pk=self.pk).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=self.valid_from)
        )
        if self.valid_to is not None:
            overlapping = overlapping.filter(valid_from__lte=self.valid_to)
        for other in overlapping:
            earlier_price = self if self.valid_from < other.valid_from else other
            if (
                self.valid_from == other.valid_from
                or (
                    earlier_price.pk is None
                    or not earlier_price.cost_lines.exists()
                )
            ):
                raise ValidationError(
                    "Price validity periods cannot overlap unless a later price "
                    "supersedes a price already referenced by a cost snapshot."
                )

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            if self.purchase_spec_id is not None:
                IngredientPurchaseSpec.objects.using(using).select_for_update().get(
                    pk=self.purchase_spec_id
                )
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        return type(self).objects.using(using).filter(pk=self.pk).delete()

    def __str__(self):
        return f"{self.purchase_spec} - {self.price_type} {self.amount}"


class Recipe(models.Model):
    class Variant(models.TextChoices):
        STANDARD = "STANDARD", "Standard"
        HOT = "HOT", "Hot"
        ICE = "ICE", "Iced"

    menu = models.ForeignKey(
        Menu,
        on_delete=models.CASCADE,
        related_name="recipes",
    )
    variant = models.CharField(
        max_length=8,
        choices=Variant.choices,
        default=Variant.STANDARD,
    )
    version = models.PositiveIntegerField()
    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)
    yield_quantity = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal("1"),
        validators=[MinValueValidator(Decimal("0.001"))],
    )
    is_active = models.BooleanField(default=True)
    variant_rationale = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class QuerySet(GuardedHistoryQuerySet):
        def bulk_create(self, objs, **kwargs):
            raise ValidationError("Use model save() so recipe validation and locking run.")

        def delete(self):
            using = self.db
            with transaction.atomic(using=using):
                menu_ids = sorted(set(self.values_list("menu_id", flat=True)))
                list(
                    Menu.objects.using(using)
                    .select_for_update()
                    .filter(pk__in=menu_ids)
                    .order_by("pk")
                )
                if not set(self.values_list("menu_id", flat=True)).issubset(menu_ids):
                    raise ValidationError("A recipe changed concurrently; retry the deletion.")
                return super().delete()

    objects = QuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("menu", "variant", "version"),
                name="recipe_menu_var_ver_uniq",
            ),
            models.CheckConstraint(
                condition=Q(version__gt=0),
                name="recipe_version_positive",
            ),
            models.CheckConstraint(
                condition=Q(yield_quantity__gt=0),
                name="recipe_yield_positive",
            ),
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gte=models.F("valid_from")),
                name="recipe_dates_valid",
            ),
        ]
        ordering = ("menu_id", "variant", "-version")

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            menu_ids = {self.menu_id}
            if self.pk is not None:
                old_menu_id = type(self).objects.using(using).filter(
                    pk=self.pk
                ).values_list("menu_id", flat=True).first()
                if old_menu_id is not None:
                    menu_ids.add(old_menu_id)
            list(
                Menu.objects.using(using)
                .select_for_update()
                .filter(pk__in=menu_ids)
                .order_by("pk")
            )
            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        return type(self).objects.using(using).filter(pk=self.pk).delete()

    def clean(self):
        super().clean()
        if self.menu_id is None:
            return
        if self.valid_to is not None and self.valid_to < self.valid_from:
            raise ValidationError({"valid_to": "End date cannot precede start date."})

        menu = self.menu
        allowed_variants = {
            Menu.ServingTemperature.BOTH: {self.Variant.STANDARD, self.Variant.HOT, self.Variant.ICE},
            Menu.ServingTemperature.HOT: {self.Variant.STANDARD, self.Variant.HOT},
            Menu.ServingTemperature.ICE: {self.Variant.STANDARD, self.Variant.ICE},
            Menu.ServingTemperature.UNKNOWN: {self.Variant.STANDARD},
        }.get(menu.serving_temperature, {self.Variant.STANDARD})
        if self.variant not in allowed_variants:
            raise ValidationError({"variant": "Recipe variant is not allowed for this menu."})
        if self.variant != self.Variant.STANDARD and not self.variant_rationale.strip():
            raise ValidationError({
                "variant_rationale": "Explain the verified HOT/ICE recipe difference."
            })

        if not self.is_active:
            return
        overlapping = type(self).objects.filter(
            menu_id=self.menu_id,
            variant=self.variant,
            is_active=True,
        ).exclude(pk=self.pk).filter(
            Q(valid_to__isnull=True) | Q(valid_to__gte=self.valid_from)
        )
        if self.valid_to is not None:
            overlapping = overlapping.filter(valid_from__lte=self.valid_to)
        if overlapping.exists():
            raise ValidationError(
                "Active recipe validity periods for the same menu and variant "
                "cannot overlap."
            )

    def __str__(self):
        return f"{self.menu.name} - {self.variant} v{self.version}"


class RecipeItem(models.Model):
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.CASCADE,
        related_name="items",
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.PROTECT,
        related_name="recipe_items",
    )
    quantity_base = models.DecimalField(
        max_digits=14,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )

    class QuerySet(GuardedHistoryQuerySet):
        def bulk_create(self, objs, **kwargs):
            raise ValidationError("Use model save() so recipe item validation and locking run.")

        def delete(self):
            using = self.db
            with transaction.atomic(using=using):
                item_ids = list(self.values_list("pk", flat=True))
                recipe_ids = sorted(set(
                    self.values_list("recipe_id", flat=True)
                ))
                list(
                    Recipe.objects.using(using)
                    .select_for_update()
                    .filter(pk__in=recipe_ids)
                    .order_by("pk")
                )
                current_recipe_ids = set(
                    self.model.objects.using(using)
                    .filter(pk__in=item_ids)
                    .values_list("recipe_id", flat=True)
                )
                if not current_recipe_ids.issubset(recipe_ids):
                    raise ValidationError(
                        "A recipe item changed concurrently; reload and retry the deletion."
                    )
                return super().delete()

    objects = QuerySet.as_manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("recipe", "ingredient"),
                name="recipe_item_ingredient_uniq",
            ),
            models.CheckConstraint(
                condition=Q(quantity_base__gt=0),
                name="recipe_item_quantity_positive",
            ),
        ]
        ordering = ("recipe_id", "ingredient__name")

    def clean(self):
        super().clean()
        if self.ingredient_id is not None and self.ingredient.base_unit not in Ingredient.BaseUnit.values:
            raise ValidationError({"ingredient": "The ingredient must have a supported base unit."})

    def save(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        with transaction.atomic(using=using):
            recipe_ids = {self.recipe_id}
            previous_recipe_id = None
            ingredient_ids = {self.ingredient_id}
            previous_ingredient_id = None
            if self.pk is not None:
                previous = type(self).objects.using(using).filter(
                    pk=self.pk
                ).values("recipe_id", "ingredient_id").first()
                if previous is not None:
                    previous_recipe_id = previous["recipe_id"]
                    previous_ingredient_id = previous["ingredient_id"]
                    recipe_ids.add(previous_recipe_id)
                    ingredient_ids.add(previous_ingredient_id)

            list(
                Recipe.objects.using(using)
                .select_for_update()
                .filter(pk__in=recipe_ids)
                .order_by("pk")
            )
            list(
                Ingredient.objects.using(using)
                .select_for_update()
                .filter(pk__in=ingredient_ids)
                .order_by("pk")
            )
            if self.pk is not None:
                current = type(self).objects.using(using).select_for_update().filter(
                    pk=self.pk
                ).values("recipe_id", "ingredient_id").first()
                if current is None or (
                    current["recipe_id"] != previous_recipe_id
                    or current["ingredient_id"] != previous_ingredient_id
                ):
                    raise ValidationError(
                        "The recipe item changed concurrently; reload it and retry."
                    )

            self.full_clean()
            return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
        return type(self).objects.using(using).filter(pk=self.pk).delete()

    def __str__(self):
        return f"{self.recipe} - {self.ingredient.name}"


class RecipeCostSnapshot(models.Model):
    class Status(models.TextChoices):
        COMPLETE = "COMPLETE", "Complete"
        INCOMPLETE = "INCOMPLETE", "Incomplete"

    class PriceType(models.TextChoices):
        ACTUAL = "ACTUAL", "Actual"
        ESTIMATED = "ESTIMATED", "Estimated"

    menu = models.ForeignKey(
        Menu,
        on_delete=models.PROTECT,
        related_name="cost_snapshots",
    )
    recipe = models.ForeignKey(
        Recipe,
        on_delete=models.PROTECT,
        related_name="cost_snapshots",
        null=True,
        blank=True,
    )
    recipe_version = models.PositiveIntegerField(null=True, blank=True)
    price_type = models.CharField(max_length=9, choices=PriceType.choices)
    as_of = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices)
    unrounded_cost = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
    )
    final_cost = models.PositiveIntegerField(null=True, blank=True)
    error_details = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(price_type__in=("ACTUAL", "ESTIMATED")),
                name="cost_snapshot_price_type_valid",
            ),
            models.CheckConstraint(
                condition=(
                    Q(
                        status="COMPLETE",
                        recipe__isnull=False,
                        recipe_version__isnull=False,
                        unrounded_cost__isnull=False,
                        final_cost__isnull=False,
                    )
                    | Q(
                        status="INCOMPLETE",
                        unrounded_cost__isnull=True,
                        final_cost__isnull=True,
                    )
                ),
                name="cost_snapshot_complete_valid",
            ),
        ]
        ordering = ("-created_at", "-pk")

    def __str__(self):
        return f"{self.menu.name} - {self.price_type} - {self.status}"


class RecipeCostLine(models.Model):
    snapshot = models.ForeignKey(
        RecipeCostSnapshot,
        on_delete=models.CASCADE,
        related_name="lines",
    )
    recipe_item = models.ForeignKey(
        RecipeItem,
        on_delete=models.PROTECT,
        related_name="cost_lines",
    )
    purchase_price = models.ForeignKey(
        IngredientPurchasePrice,
        on_delete=models.PROTECT,
        related_name="cost_lines",
    )
    quantity_base = models.DecimalField(max_digits=14, decimal_places=4)
    purchase_base_quantity = models.DecimalField(max_digits=14, decimal_places=4)
    unit_cost = models.DecimalField(max_digits=16, decimal_places=8)
    line_subtotal = models.DecimalField(max_digits=18, decimal_places=6)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("snapshot", "recipe_item"),
                name="cost_line_snapshot_item_uniq",
            ),
            models.CheckConstraint(
                condition=Q(quantity_base__gt=0) & Q(purchase_base_quantity__gt=0),
                name="cost_line_quantities_positive",
            ),
            models.CheckConstraint(
                condition=Q(unit_cost__gte=0) & Q(line_subtotal__gte=0),
                name="cost_line_amounts_nonnegative",
            ),
        ]
        ordering = ("recipe_item_id",)

    def clean(self):
        super().clean()
        if self.snapshot_id and self.purchase_price_id:
            if self.snapshot.price_type != self.purchase_price.price_type:
                raise ValidationError(
                    "A cost snapshot cannot mix actual and estimated prices."
                )

    def __str__(self):
        return f"{self.snapshot} - {self.recipe_item.ingredient.name}"