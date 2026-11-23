from datetime import date
from sales.ml.forecast_engine import generate_forecasts

result = generate_forecasts(
    store_id=1,
    as_of=date(2026, 11, 22),
    persist=True,
)

print("STATUS:", result.get("status"))
print("RUN_ID:", result.get("run_id"))
print("AS_OF:", result.get("as_of"))
print("TARGET_DATES:", result.get("target_dates"))
print("SERIES_COUNT:", result.get("total_series_count"))
print("VALUE_COUNT:", result.get("forecast_value_count"))
