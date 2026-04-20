import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("appointments", "0004_appointment_client"),
        ("providers", "0006_update_staff_fk_working_hours_schedule_block"),
    ]

    operations = [
        migrations.RemoveField(
            model_name="appointment",
            name="staff",
        ),
        migrations.AddField(
            model_name="appointment",
            name="staff",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="staff_appointments",
                to="providers.staff",
            ),
        ),
    ]
