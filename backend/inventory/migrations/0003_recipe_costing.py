import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0002_menuingredient"),
        ("store", "0006_menu_cost_status"),
    ]

    operations = [
        migrations.CreateModel(
            name="Ingredient",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100, unique=True)),
                ("base_unit", models.CharField(choices=[("g", "Gram"), ("ml", "Milliliter"), ("ea", "Each")], max_length=2)),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "ordering": ("name",),
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(base_unit__in=("g", "ml", "ea")),
                        name="ingredient_base_unit_valid",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="IngredientPurchaseSpec",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("package_quantity", models.DecimalField(decimal_places=3, max_digits=12, validators=[django.core.validators.MinValueValidator(Decimal("0.001"))])),
                ("purchase_unit", models.CharField(choices=[("g", "Gram"), ("kg", "Kilogram"), ("ml", "Milliliter"), ("L", "Liter"), ("ea", "Each")], max_length=2)),
                ("base_quantity", models.DecimalField(blank=True, decimal_places=4, max_digits=14, null=True, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("conversion_evidence", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("ingredient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="purchase_specs", to="inventory.ingredient")),
                ("store", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="ingredient_purchase_specs", to="store.store")),
            ],
            options={
                "ordering": ("ingredient__name", "package_quantity"),
                "constraints": [
                    models.CheckConstraint(condition=models.Q(package_quantity__gt=0), name="purchase_spec_package_positive"),
                    models.CheckConstraint(condition=models.Q(base_quantity__isnull=True) | models.Q(base_quantity__gt=0), name="purchase_spec_base_positive"),
                ],
            },
        ),
        migrations.CreateModel(
            name="Recipe",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("variant", models.CharField(choices=[("STANDARD", "Standard"), ("HOT", "Hot"), ("ICE", "Iced")], default="STANDARD", max_length=8)),
                ("version", models.PositiveIntegerField()),
                ("valid_from", models.DateField()),
                ("valid_to", models.DateField(blank=True, null=True)),
                ("yield_quantity", models.DecimalField(decimal_places=3, default=Decimal("1"), max_digits=10, validators=[django.core.validators.MinValueValidator(Decimal("0.001"))])),
                ("is_active", models.BooleanField(default=True)),
                ("variant_rationale", models.CharField(blank=True, max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("menu", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="recipes", to="store.menu")),
            ],
            options={
                "ordering": ("menu_id", "variant", "-version"),
                "constraints": [
                    models.UniqueConstraint(fields=("menu", "variant", "version"), name="recipe_menu_var_ver_uniq"),
                    models.CheckConstraint(condition=models.Q(version__gt=0), name="recipe_version_positive"),
                    models.CheckConstraint(condition=models.Q(yield_quantity__gt=0), name="recipe_yield_positive"),
                    models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")), name="recipe_dates_valid"),
                ],
            },
        ),
        migrations.CreateModel(
            name="IngredientPurchasePrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("price_type", models.CharField(choices=[("ACTUAL", "Actual"), ("ESTIMATED", "Estimated")], max_length=9)),
                ("amount", models.DecimalField(decimal_places=2, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0.01"))])),
                ("valid_from", models.DateField()),
                ("valid_to", models.DateField(blank=True, null=True)),
                ("source", models.CharField(blank=True, max_length=255)),
                ("rationale", models.TextField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("purchase_spec", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="prices", to="inventory.ingredientpurchasespec")),
            ],
            options={
                "ordering": ("-valid_from", "-pk"),
                "constraints": [
                    models.CheckConstraint(condition=models.Q(amount__gt=0), name="purchase_price_amount_positive"),
                    models.CheckConstraint(condition=models.Q(valid_to__isnull=True) | models.Q(valid_to__gte=models.F("valid_from")), name="purchase_price_dates_valid"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecipeItem",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity_base", models.DecimalField(decimal_places=4, max_digits=14, validators=[django.core.validators.MinValueValidator(Decimal("0.0001"))])),
                ("ingredient", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="recipe_items", to="inventory.ingredient")),
                ("recipe", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="items", to="inventory.recipe")),
            ],
            options={
                "ordering": ("recipe_id", "ingredient__name"),
                "constraints": [
                    models.UniqueConstraint(fields=("recipe", "ingredient"), name="recipe_item_ingredient_uniq"),
                    models.CheckConstraint(condition=models.Q(quantity_base__gt=0), name="recipe_item_quantity_positive"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecipeCostSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("recipe_version", models.PositiveIntegerField(blank=True, null=True)),
                ("price_type", models.CharField(choices=[("ACTUAL", "Actual"), ("ESTIMATED", "Estimated")], max_length=9)),
                ("as_of", models.DateField()),
                ("status", models.CharField(choices=[("COMPLETE", "Complete"), ("INCOMPLETE", "Incomplete")], max_length=10)),
                ("unrounded_cost", models.DecimalField(blank=True, decimal_places=6, max_digits=18, null=True)),
                ("final_cost", models.PositiveIntegerField(blank=True, null=True)),
                ("error_details", models.JSONField(blank=True, default=list)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("menu", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cost_snapshots", to="store.menu")),
                ("recipe", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT, related_name="cost_snapshots", to="inventory.recipe")),
            ],
            options={
                "ordering": ("-created_at", "-pk"),
                "constraints": [
                    models.CheckConstraint(condition=models.Q(price_type__in=("ACTUAL", "ESTIMATED")), name="cost_snapshot_price_type_valid"),
                    models.CheckConstraint(
                        condition=(
                            models.Q(status="COMPLETE", recipe__isnull=False, recipe_version__isnull=False, unrounded_cost__isnull=False, final_cost__isnull=False)
                            | models.Q(status="INCOMPLETE", unrounded_cost__isnull=True, final_cost__isnull=True)
                        ),
                        name="cost_snapshot_complete_valid",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="RecipeCostLine",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("quantity_base", models.DecimalField(decimal_places=4, max_digits=14)),
                ("purchase_base_quantity", models.DecimalField(decimal_places=4, max_digits=14)),
                ("unit_cost", models.DecimalField(decimal_places=8, max_digits=16)),
                ("line_subtotal", models.DecimalField(decimal_places=6, max_digits=18)),
                ("purchase_price", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cost_lines", to="inventory.ingredientpurchaseprice")),
                ("recipe_item", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="cost_lines", to="inventory.recipeitem")),
                ("snapshot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="lines", to="inventory.recipecostsnapshot")),
            ],
            options={
                "ordering": ("recipe_item_id",),
                "constraints": [
                    models.UniqueConstraint(fields=("snapshot", "recipe_item"), name="cost_line_snapshot_item_uniq"),
                    models.CheckConstraint(condition=models.Q(quantity_base__gt=0) & models.Q(purchase_base_quantity__gt=0), name="cost_line_quantities_positive"),
                    models.CheckConstraint(condition=models.Q(unit_cost__gte=0) & models.Q(line_subtotal__gte=0), name="cost_line_amounts_nonnegative"),
                ],
            },
        ),
        migrations.AddField(
            model_name="inventory",
            name="ingredient",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="inventory_records",
                to="inventory.ingredient",
            ),
        ),
    ]
