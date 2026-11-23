from django.core.exceptions import ValidationError
from django.db import models, transaction
from store.models import Store, Menu


class SalesItemQuerySet(models.QuerySet):
    """Validate each line with the same model rules before bulk persistence."""

    def _validate_objects(self, objs):
        for obj in objs:
            if not isinstance(obj, self.model):
                raise TypeError(f"Expected {self.model.__name__} instance, got {type(obj).__name__}.")
            obj.full_clean()

    def bulk_create(
        self,
        objs,
        batch_size=None,
        ignore_conflicts=False,
        update_conflicts=False,
        update_fields=None,
        unique_fields=None,
    ):
        objs = list(objs)
        self._validate_objects(objs)
        # Validate every row before opening the write path, then ensure a DB
        # error cannot leave an earlier batch inserted on its own.
        with transaction.atomic(using=self.db):
            return super().bulk_create(
                objs,
                batch_size=batch_size,
                ignore_conflicts=ignore_conflicts,
                update_conflicts=update_conflicts,
                update_fields=update_fields,
                unique_fields=unique_fields,
            )

    def bulk_update(self, objs, fields, batch_size=None):
        objs = list(objs)
        if {"menu", "menu_id", "serving_temperature"}.intersection(fields):
            self._validate_objects(objs)
        with transaction.atomic(using=self.db):
            return super().bulk_update(objs, fields, batch_size=batch_size)

    def update(self, **kwargs):
        protected_fields = {"menu", "menu_id", "serving_temperature"}
        changed_fields = protected_fields.intersection(kwargs)
        if changed_fields:
            if any(hasattr(kwargs[field], "resolve_expression") for field in changed_fields):
                raise ValidationError(
                    "Expressions cannot update menu or serving temperature without row validation."
                )
            objects = list(self.select_related("menu"))
            for obj in objects:
                for field in changed_fields:
                    setattr(obj, field, kwargs[field])
                obj.full_clean()
        with transaction.atomic(using=self.db):
            return super().update(**kwargs)

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
    # 외부 원본(POS/더미 CSV)의 주문 ID. 직접 입력한 주문은 NULL.
    source_order_id = models.CharField(
        max_length=32,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            # 매장별 유일: 원본 주문번호는 POS(매장) 단위로 부여되므로 (store, source_order_id)로 제한.
            # MySQL 유니크 인덱스는 NULL을 서로 다른 값으로 취급하므로 기존/수기 주문(NULL)과 호환된다.
            models.UniqueConstraint(
                fields=('store', 'source_order_id'),
                name='sales_store_source_order_id_uniq',
            ),
            models.CheckConstraint(
                condition=models.Q(source_order_id__isnull=True) | ~models.Q(source_order_id=''),
                name='sales_source_order_id_not_empty',
            ),
        ]

    def __str__(self):
        return f"{self.store.name} - {self.sold_at}"

class SalesItem(models.Model):
    class ServingTemperature(models.TextChoices):
        HOT = "HOT", "HOT"
        ICE = "ICE", "ICE"

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
    serving_temperature = models.CharField(
        max_length=3,
        choices=ServingTemperature.choices,
        null=True,
        blank=True,
    )

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(serving_temperature__isnull=True)
                    | models.Q(serving_temperature__in=("HOT", "ICE"))
                ),
                name="salesitem_serving_temp_valid",
            ),
        ]

    objects = SalesItemQuerySet.as_manager()

    def clean(self):
        super().clean()
        temperature = self.serving_temperature
        if temperature == "":
            self.serving_temperature = None
            temperature = None
        if temperature is None:
            return

        if self.menu_id is None:
            raise ValidationError({"menu": "A menu is required when an order line has a serving temperature."})

        try:
            menu = self.menu
        except Menu.DoesNotExist as exc:
            raise ValidationError({"menu": "The selected menu does not exist."}) from exc

        availability = menu.serving_temperature
        allowed = {
            Menu.ServingTemperature.BOTH: {"HOT", "ICE"},
            Menu.ServingTemperature.HOT: {"HOT"},
            Menu.ServingTemperature.ICE: {"ICE"},
            Menu.ServingTemperature.UNKNOWN: set(),
        }.get(availability, set())
        if temperature not in allowed:
            raise ValidationError({
                "serving_temperature": (
                    f"{menu.name} does not allow temperature {temperature}."
                )
            })

    def save(self, *args, **kwargs):
        self.full_clean()
        return super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.menu.name} - {self.quantity}"
# Create your models here.

class ForecastRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "RUNNING", "Running"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    store = models.ForeignKey(
        Store,
        on_delete=models.CASCADE,
        related_name="forecast_runs",
    )
    as_of = models.DateField()
    generated_at = models.DateTimeField(auto_now_add=True)
    model_version = models.CharField(max_length=50)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    metrics = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-generated_at"]
        indexes = [
            models.Index(fields=["store", "as_of"]),
            models.Index(fields=["store", "generated_at"]),
        ]

    def __str__(self):
        return f"{self.store_id} - {self.as_of} - {self.model_version}"


class ForecastValue(models.Model):
    class Granularity(models.TextChoices):
        DAILY = "DAILY", "Daily"
        HOURLY = "HOURLY", "Hourly"
        MENU = "MENU", "Menu"

    class Metric(models.TextChoices):
        SALES = "SALES", "Sales"
        ORDERS = "ORDERS", "Orders"
        QUANTITY = "QUANTITY", "Quantity"

    class ServingTemperature(models.TextChoices):
        HOT = "HOT", "HOT"
        ICE = "ICE", "ICE"

    run = models.ForeignKey(
        ForecastRun,
        on_delete=models.CASCADE,
        related_name="values",
    )
    series_key = models.CharField(max_length=150)
    granularity = models.CharField(max_length=10, choices=Granularity.choices)
    metric = models.CharField(max_length=10, choices=Metric.choices)
    target_date = models.DateField()
    target_hour = models.PositiveSmallIntegerField(null=True, blank=True)
    menu = models.ForeignKey(
        Menu,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="forecast_values",
    )
    serving_temperature = models.CharField(
        max_length=3,
        choices=ServingTemperature.choices,
        null=True,
        blank=True,
    )
    predicted_value = models.DecimalField(max_digits=18, decimal_places=2)
    lower_bound = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    upper_bound = models.DecimalField(
        max_digits=18, decimal_places=2, null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["target_date", "target_hour", "series_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "series_key", "target_date"],
                name="forecast_value_run_date_uniq",
            ),
        ]
        indexes = [
            models.Index(fields=["run", "target_date"]),
            models.Index(fields=["granularity", "metric", "target_date"]),
        ]

    def __str__(self):
        return f"{self.run_id} - {self.series_key} - {self.predicted_value}"
