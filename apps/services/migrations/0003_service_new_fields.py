from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("services", "0002_agendamento_online_cliente"),
    ]

    operations = [
        migrations.RenameField(
            model_name="service",
            old_name="duration",
            new_name="duration_minutes",
        ),
        migrations.AlterField(
            model_name="service",
            name="price",
            field=models.DecimalField(
                max_digits=10,
                decimal_places=2,
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="service",
            name="color",
            field=models.CharField(max_length=7, null=True, blank=True),
        ),
        migrations.AddField(
            model_name="service",
            name="currency",
            field=models.CharField(max_length=3, default="BRL"),
        ),
        migrations.AddField(
            model_name="service",
            name="requires_deposit",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="service",
            name="deposit_amount",
            field=models.DecimalField(
                max_digits=10,
                decimal_places=2,
                null=True,
                blank=True,
            ),
        ),
        migrations.AddField(
            model_name="service",
            name="max_clients",
            field=models.PositiveIntegerField(default=1),
        ),
    ]
