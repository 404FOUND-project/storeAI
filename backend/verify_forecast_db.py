from django.db import connection

tables = connection.introspection.table_names()
for name in ["sales_forecastrun", "sales_forecastvalue", "sales_forecast"]:
    print(name, "EXISTS" if name in tables else "MISSING")
    if name in tables:
        with connection.cursor() as cursor:
            cursor.execute(f"SELECT COUNT(*) FROM `{name}`")
            print(" ROWS:", cursor.fetchone()[0])
