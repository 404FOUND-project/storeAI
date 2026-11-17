from django.contrib import admin

from .models import Menu, Store


@admin.register(Store)
class StoreAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "address", "phone", "owner", "created_at")
    search_fields = ("name", "address", "owner__username")


@admin.register(Menu)
class MenuAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "price", "store")
    list_filter = ("store",)
    search_fields = ("name",)
