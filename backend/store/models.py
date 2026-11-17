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
        max_digits=17,
        decimal_places=14,
        null=True,
        blank=True
    )
    longitude = models.DecimalField(
        max_digits=17,
        decimal_places=14,
        null=True,
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
class Menu(models.Model):
    class CostStatus(models.TextChoices):
        UNSET = "UNSET", "Not set"
        ACTUAL = "ACTUAL", "Actual price"
        ESTIMATED = "ESTIMATED", "Estimated price"
        UNVERIFIED = "UNVERIFIED", "Unverified"

    class ServingTemperature(models.TextChoices):
        BOTH = "BOTH", "HOT and ICE"
        HOT = "HOT", "HOT only"
        ICE = "ICE", "ICE only"
        UNKNOWN = "UNKNOWN", "Unknown"

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name='menus'
    )
    pos_code = models.CharField(max_length=32, null=True, blank=True)
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
    cost_status = models.CharField(
        max_length=10,
        choices=CostStatus.choices,
        default=CostStatus.UNSET,
    )
    cost_calculated_at = models.DateTimeField(
        null=True,
        blank=True,
    )
    # 현재 판매 중인지 여부
    is_active = models.BooleanField(default=True)
    serving_temperature = models.CharField(
        max_length=7,
        choices=ServingTemperature.choices,
        default=ServingTemperature.UNKNOWN,
    )

    create_at = models.DateTimeField(auto_now_add=True)
    update_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=('store', 'pos_code'),
                name='menu_store_pos_code_uniq',
            ),
            models.CheckConstraint(
                condition=models.Q(pos_code__isnull=True) | ~models.Q(pos_code=''),
                name='menu_pos_code_not_empty',
            ),
            models.CheckConstraint(
                condition=models.Q(serving_temperature__in=('BOTH', 'HOT', 'ICE', 'UNKNOWN')),
                name='menu_serving_temp_valid',
            ),
            models.CheckConstraint(
                condition=models.Q(cost_status__in=('UNSET', 'ACTUAL', 'ESTIMATED', 'UNVERIFIED')),
                name='menu_cost_status_valid',
            ),
        ]

    def __str__(self):
        return self.name
