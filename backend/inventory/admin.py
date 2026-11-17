from django.contrib import admin

from .models import Inventory, MenuIngredient


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        "id", "store", "ingredient_name", "quantity", "unit",
        "expiration_date", "update_at",
    )
    list_filter = ("store", "unit")
    search_fields = ("ingredient_name", "store__name")
    list_select_related = ("store",)
    date_hierarchy = "expiration_date"
    ordering = ("store", "ingredient_name")


@admin.register(MenuIngredient)
class MenuIngredientAdmin(admin.ModelAdmin):
    list_display = ("id", "menu", "inventory", "required_quantity")
    search_fields = ("menu__name", "inventory__ingredient_name")
    list_select_related = ("menu", "inventory")


from .models import (  # noqa: E402  팀원 재료·레시피·원가 표
    Ingredient, IngredientPurchasePrice, IngredientPurchaseSpec,
    Recipe, RecipeCostLine, RecipeCostSnapshot, RecipeItem,
)


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "base_unit", "is_active")
    search_fields = ("name",)
    list_filter = ("is_active", "base_unit")


class RecipeItemInline(admin.TabularInline):
    model = RecipeItem
    extra = 0
    raw_id_fields = ("ingredient",)


@admin.register(Recipe)
class RecipeAdmin(admin.ModelAdmin):
    list_display = ("id", "menu", "variant", "version", "yield_quantity", "is_active", "valid_from")
    list_filter = ("variant", "is_active")
    search_fields = ("menu__name",)
    list_select_related = ("menu",)
    inlines = [RecipeItemInline]


@admin.register(RecipeCostSnapshot)
class RecipeCostSnapshotAdmin(admin.ModelAdmin):
    list_display = ("id", "menu", "recipe", "price_type", "status", "final_cost", "as_of")
    list_filter = ("price_type", "status")
    search_fields = ("menu__name",)
    list_select_related = ("menu", "recipe")


for _m in (RecipeItem, RecipeCostLine, IngredientPurchaseSpec, IngredientPurchasePrice):
    admin.site.register(_m)
