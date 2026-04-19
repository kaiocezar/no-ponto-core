"""EMAIL channel + partial unique for new_appointment_provider per appointment."""

from django.db import migrations, models
from django.db.models import Q


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0002_alter_notification_type"),
    ]

    operations = [
        migrations.AlterField(
            model_name="notification",
            name="channel",
            field=models.CharField(
                choices=[("whatsapp", "WhatsApp"), ("email", "Email")],
                max_length=32,
            ),
        ),
        migrations.AddConstraint(
            model_name="notification",
            constraint=models.UniqueConstraint(
                condition=Q(type="new_appointment_provider"),
                fields=("appointment",),
                name="notifications_new_provider_one_per_appt",
            ),
        ),
    ]
