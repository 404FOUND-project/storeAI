from django.db import models
from django.db.models import Q
from django.utils import timezone

from store.models import Store


class WeatherLocation(models.Model):
    """Weather-provider identifiers and coordinates for one store."""

    store = models.OneToOneField(
        Store,
        on_delete=models.PROTECT,
        related_name="weather_location",
    )
    # These are the coordinates configured for weather lookups. They are kept
    # here separately from Store coordinates so a weather location can be
    # adjusted without changing the store's general address coordinates.
    latitude = models.DecimalField(max_digits=17, decimal_places=14)
    longitude = models.DecimalField(max_digits=17, decimal_places=14)
    asos_station_id = models.CharField(max_length=8, blank=True)
    forecast_nx = models.PositiveSmallIntegerField(null=True, blank=True)
    forecast_ny = models.PositiveSmallIntegerField(null=True, blank=True)
    mid_temp_region_id = models.CharField(
        max_length=12,
        blank=True,
        help_text="KMA mid-term temperature forecast region code.",
    )
    mid_land_region_id = models.CharField(
        max_length=12,
        blank=True,
        help_text="KMA mid-term land forecast region code.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "weatherdata_location"

    def __str__(self):
        return f"Weather location for {self.store}"


class WeatherCollectionRun(models.Model):
    class SourceType(models.TextChoices):
        OBSERVED = "observed", "Observed"
        FORECAST = "forecast", "Forecast"
        SCENARIO = "scenario", "Scenario"

    class DatasetType(models.TextChoices):
        ASOS_DAILY = "asos_daily", "ASOS daily observations"
        SHORT_FORECAST = "short_forecast", "Short-term forecast"
        MID_TEMPERATURE = "mid_temperature", "Mid-term temperature forecast"
        MID_LAND = "mid_land", "Mid-term land forecast"
        SCENARIO = "scenario", "Synthetic scenario"

    class Status(models.TextChoices):
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    location = models.ForeignKey(
        WeatherLocation,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="collection_runs",
    )
    source_type = models.CharField(max_length=10, choices=SourceType.choices)
    # Forecast dataset and location are obtained from forecast_publication.
    # Observed/scenario runs carry these fields directly.
    dataset_type = models.CharField(max_length=24, choices=DatasetType.choices, null=True, blank=True)
    forecast_publication = models.ForeignKey(
        "WeatherForecastPublication",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="collection_runs",
    )
    collected_at = models.DateTimeField(default=timezone.now)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    http_status = models.PositiveSmallIntegerField(null=True, blank=True)
    api_result_code = models.CharField(max_length=24, blank=True)
    error_code = models.CharField(max_length=64, blank=True)
    error_message = models.TextField(blank=True)
    record_count = models.PositiveIntegerField(default=0)
    # Sanitized request parameters only. Never put serviceKey or full URLs here.
    request_parameters = models.JSONField(default=dict, blank=True)
    scenario_name = models.CharField(max_length=100, blank=True)
    scenario_version = models.CharField(max_length=40, blank=True)
    generation_rule = models.TextField(blank=True)
    random_seed = models.BigIntegerField(null=True, blank=True)

    class Meta:
        db_table = "weatherdata_collection_run"
        indexes = [
            models.Index(fields=("source_type", "dataset_type", "collected_at")),
            models.Index(fields=("forecast_publication", "status", "collected_at")),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        source_type="forecast",
                        dataset_type__isnull=True,
                        location__isnull=True,
                        forecast_publication__isnull=False,
                    )
                    | Q(
                        source_type="observed",
                        dataset_type="asos_daily",
                        location__isnull=False,
                        forecast_publication__isnull=True,
                    )
                    | Q(
                        source_type="scenario",
                        dataset_type="scenario",
                        location__isnull=False,
                        forecast_publication__isnull=True,
                    )
                ),
                name="weather_collection_run_context_valid",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.source_type == self.SourceType.FORECAST:
            if self.forecast_publication_id is None:
                raise ValidationError({"forecast_publication": "Forecast runs require a publication."})
            if self.location_id is not None or self.dataset_type is not None:
                raise ValidationError("Forecast location and dataset type must come from its publication.")
        elif self.forecast_publication_id is not None:
            raise ValidationError({"forecast_publication": "Only forecast runs may reference a publication."})

    @property
    def effective_location(self):
        if self.forecast_publication_id:
            return self.forecast_publication.location
        return self.location

    @property
    def effective_dataset_type(self):
        if self.forecast_publication_id:
            return self.forecast_publication.dataset_type
        return self.dataset_type

    @property
    def issued_at(self):
        if self.forecast_publication_id:
            return self.forecast_publication.issued_at
        return None

    def __str__(self):
        return f"{self.effective_dataset_type} {self.collected_at:%Y-%m-%d %H:%M:%S}"


class WeatherDatum(models.Model):
    class DataLayer(models.TextChoices):
        RAW = "raw", "Raw provider value"
        DERIVED = "derived", "Derived value"

    class ValueKind(models.TextChoices):
        NUMERIC = "numeric", "Numeric value"
        TEXT = "text", "Text value"

    class QualityStatus(models.TextChoices):
        VALID = "valid", "Valid"
        MISSING = "missing", "Missing"
        ESTIMATED = "estimated", "Estimated"
        SUSPECT = "suspect", "Suspect"
        NOT_APPLICABLE = "not_applicable", "Not applicable"

    collection_run = models.ForeignKey(
        WeatherCollectionRun,
        on_delete=models.PROTECT,
        related_name="data",
    )
    forecast_publication = models.ForeignKey(
        "WeatherForecastPublication",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="data",
    )
    data_layer = models.CharField(max_length=8, choices=DataLayer.choices)
    # A timezone-aware valid timestamp. Daily observations and daily mid-term
    # values use midnight KST; intraday forecasts retain their forecast hour.
    valid_at = models.DateTimeField()
    variable = models.CharField(max_length=40)
    period = models.CharField(max_length=12, default="daily")
    value_kind = models.CharField(
        max_length=8,
        choices=ValueKind.choices,
        default=ValueKind.NUMERIC,
    )
    value_numeric = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        null=True,
        blank=True,
    )
    value_text = models.CharField(max_length=120, blank=True)
    unit = models.CharField(max_length=24, blank=True)
    source_field = models.CharField(max_length=40, blank=True)
    quality_status = models.CharField(
        max_length=16,
        choices=QualityStatus.choices,
        default=QualityStatus.VALID,
    )
    quality_note = models.CharField(max_length=240, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "weatherdata_datum"
        indexes = [
            models.Index(fields=("valid_at", "variable")),
            models.Index(fields=("data_layer", "valid_at")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "collection_run",
                    "valid_at",
                    "variable",
                    "period",
                    "data_layer",
                ),
                name="weather_datum_run_target_variable_uniq",
            ),
            models.UniqueConstraint(
                fields=(
                    "forecast_publication",
                    "valid_at",
                    "variable",
                    "period",
                    "data_layer",
                ),
                name="weather_datum_publication_target_uniq",
            ),
            models.CheckConstraint(
                condition=Q(value_kind__in=("numeric", "text")),
                name="weather_datum_value_kind_valid",
            ),
            models.CheckConstraint(
                condition=(
                    (
                        Q(quality_status__in=("missing", "not_applicable"))
                        & Q(value_numeric__isnull=True, value_text="")
                    )
                    | (
                        Q(quality_status__in=("valid", "estimated", "suspect"))
                        & (
                            Q(value_kind="numeric", value_numeric__isnull=False, value_text="")
                            | (Q(value_kind="text", value_numeric__isnull=True) & ~Q(value_text=""))
                        )
                    )
                ),
                name="weather_datum_value_matches_quality_kind",
            ),
        ]

    def clean(self):
        from django.core.exceptions import ValidationError

        is_forecast = self.collection_run.source_type == WeatherCollectionRun.SourceType.FORECAST
        if is_forecast:
            if self.forecast_publication_id is None:
                raise ValidationError({"forecast_publication": "Forecast data require a publication."})
            if self.forecast_publication_id != self.collection_run.forecast_publication_id:
                raise ValidationError("Forecast data must reference the publication of its collection run.")
        elif self.forecast_publication_id is not None:
            raise ValidationError({"forecast_publication": "Only forecast data may reference a publication."})


class WeatherForecastPublication(models.Model):
    class DatasetType(models.TextChoices):
        SHORT_FORECAST = "short_forecast", "Short-term forecast"
        MID_TEMPERATURE = "mid_temperature", "Mid-term temperature forecast"
        MID_LAND = "mid_land", "Mid-term land forecast"

    location = models.ForeignKey(
        WeatherLocation,
        on_delete=models.PROTECT,
        related_name="forecast_publications",
    )
    dataset_type = models.CharField(max_length=24, choices=DatasetType.choices)
    issued_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "weatherdata_forecast_publication"
        constraints = [
            models.UniqueConstraint(
                fields=("location", "dataset_type", "issued_at"),
                name="weather_forecast_publication_uniq",
            ),
            models.CheckConstraint(
                condition=Q(dataset_type__in=("short_forecast", "mid_temperature", "mid_land")),
                name="weather_publication_dataset_is_forecast",
            ),
        ]

    def __str__(self):
        return f"{self.dataset_type} issued {self.issued_at:%Y-%m-%d %H:%M:%S}"

    @property
    def latest_successful_run(self):
        return self.collection_runs.filter(
            status=WeatherCollectionRun.Status.SUCCEEDED
        ).order_by("-collected_at", "-pk").first()

    def __str__(self):
        return f"{self.variable} at {self.valid_at:%Y-%m-%d %H:%M}"
