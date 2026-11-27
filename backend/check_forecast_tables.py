from django.db import connection

tables = connection.introspection.table_names()
forecast_tables = [t for t in tables if "forecast" in t]
print("FORECAST_TABLES:", forecast_tables)

if "sales_forecast" in tables:
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM sales_forecast")
        print("LEGACY_ROWS:", cursor.fetchone()[0])
else:
    print("LEGACY_ROWS: TABLE_NOT_FOUND")
