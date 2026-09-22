from django.conf import settings
from django.db import models


class Store(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,

        # 사장님 계정 삭제 시 그 사장님 소유의 가게 정보도 같이 삭제됨
        on_delete=models.CASCADE,  

        related_name='stores'
    )

    name = models.CharField(max_length=100)
    address = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    # 사업자 등록 번호
    business_number = models.CharField(max_length=20, blank=True)
    # 업종 / 카테고리
    created_at = models.DateTimeField(auto_now_add=True)
    # 상권 분석용 위도/경도
    latitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=10,
        decimal_places=7,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class Menu(models.Model):
    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='menus'
    )
    name = models.CharField(max_length=100)

    # 음료, 디저트, 식사 등
    category = models.CharField(
        max_length=50, 
        blank=True
    )
    # 판매 가격
    price = models.PositiveIntegerField()
    # 원가
    cost = models.PositiveIntegerField(
        null=True, 
        blank=True
    )
    # 현재 판매 중인지 여부
    is_active = models.BooleanField(default=True)

    create_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    