from django.db import models
from store.models import Store, Menu

class Sales(models.Model):
    store = models.ForeignKey(
        Store, 
        on_delete=models.CASCADE, 
        related_name='sales'
    )

    # 실제 판매가 발생한 시간
    sold_at = models.DateTimeField()
    # 주문 전체 금액
    total_amount = models.PositiveBigIntegerField()
    create_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return f"{self.store.name} - {self.sold_at}"

class SalesItem(models.Model):
    sales = models.ForeignKey(
        Sales, 
        on_delete=models.CASCADE, 
        related_name='items'
    )

    menu = models.ForeignKey(
        Menu, 
        on_delete=models.PROTECT,
        related_name='sales_items'
    )

    # 해당 메뉴 주문 수량
    quantity = models.PositiveIntegerField()
    # 구매 당시 메뉴 가격
    unit_price = models.PositiveIntegerField()  

    def __str__(self):
        return f"{self.menu.name} - {self.quantity}"
# Create your models here.
