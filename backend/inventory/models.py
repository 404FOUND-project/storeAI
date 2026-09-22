from django.db import models
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