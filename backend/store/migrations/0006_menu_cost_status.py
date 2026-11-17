from django.db import migrations, models


def mark_existing_costs_unverified(apps, schema_editor):
    Menu = apps.get_model("store", "Menu")
    Menu.objects.using(schema_editor.connection.alias).filter(
        cost__isnull=False,
    ).update(cost_status="UNVERIFIED")


class Migration(migrations.Migration):

    dependencies = [
        ("store", "0005_menu_pos_code_menu_serving_temperature_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="menu",
            name="cost_status",
            field=models.CharField(
                choices=[
                    ("UNSET", "Not set"),
                    ("ACTUAL", "Actual price"),
                    ("ESTIMATED", "Estimated price"),
                    ("UNVERIFIED", "Unverified"),
                ],
                default="UNSET",
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name="menu",
            name="cost_calculated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(mark_existing_costs_unverified, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="menu",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    cost_status__in=("UNSET", "ACTUAL", "ESTIMATED", "UNVERIFIED"),
                ),
                name="menu_cost_status_valid",
            ),
        ),
    ]
