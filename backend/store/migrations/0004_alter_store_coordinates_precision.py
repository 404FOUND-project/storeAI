from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('store', '0003_menu'),
    ]

    operations = [
        migrations.AlterField(
            model_name='store',
            name='latitude',
            field=models.DecimalField(blank=True, decimal_places=14, max_digits=17, null=True),
        ),
        migrations.AlterField(
            model_name='store',
            name='longitude',
            field=models.DecimalField(blank=True, decimal_places=14, max_digits=17, null=True),
        ),
    ]