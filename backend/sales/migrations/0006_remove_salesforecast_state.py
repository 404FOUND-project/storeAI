from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ("sales", "0005_forecastrun_forecastvalue"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(name="SalesForecast"),
            ],
        ),
    ]
