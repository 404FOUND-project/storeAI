from django.contrib import admin

from .models import Sales, SalesItem


class SalesItemInline(admin.TabularInline):
    model = SalesItem
    extra = 0
    raw_id_fields = ("menu",)


@admin.register(Sales)
class SalesAdmin(admin.ModelAdmin):
    list_display = ("id", "store", "sold_at", "total_amount")
    list_filter = ("store",)
    date_hierarchy = "sold_at"
    list_select_related = ("store",)
    list_per_page = 50
    inlines = [SalesItemInline]


@admin.register(SalesItem)
class SalesItemAdmin(admin.ModelAdmin):
    list_display = ("id", "sales", "menu", "quantity", "unit_price")
    list_select_related = ("menu",)
    raw_id_fields = ("sales", "menu")
    search_fields = ("menu__name",)
    list_per_page = 50


from .models import SalesForecast  # noqa: E402


@admin.register(SalesForecast)
class SalesForecastAdmin(admin.ModelAdmin):
    list_display = ("id", "menu", "base_date", "target_date", "predicted_quantity_hot", "predicted_quantity_ice")
    list_filter = ("base_date", "menu")
    list_select_related = ("menu",)
    raw_id_fields = ("menu",)
