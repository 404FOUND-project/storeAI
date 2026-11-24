from sales.models import ForecastRun, ForecastValue

run = ForecastRun.objects.get(pk=1)
values = ForecastValue.objects.filter(run=run)

print("RUN_STATUS:", run.status)
print("MODEL_VERSION:", run.model_version)
print("TOTAL_VALUES:", values.count())
print("UNIQUE_SERIES:", values.values("series_key").distinct().count())
print("DAILY:", values.filter(granularity="DAILY").count())
print("HOURLY:", values.filter(granularity="HOURLY").count())
print("MENU:", values.filter(granularity="MENU").count())
print("DATE_RANGE:", values.order_by("target_date").first().target_date, values.order_by("-target_date").first().target_date)
print("METRICS:", run.metrics)
