import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("providers", "0005_populate_owner_staff"),
    ]

    operations = [
        # WorkingHours: remover FK antiga para accounts.User, adicionar FK para providers.Staff
        migrations.RemoveField(
            model_name="workinghours",
            name="staff",
        ),
        migrations.AddField(
            model_name="workinghours",
            name="staff",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="working_hours",
                to="providers.staff",
            ),
        ),
        # ScheduleBlock: remover FK antiga para accounts.User, adicionar FK para providers.Staff
        migrations.RemoveField(
            model_name="scheduleblock",
            name="staff",
        ),
        migrations.AddField(
            model_name="scheduleblock",
            name="staff",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name="schedule_blocks",
                to="providers.staff",
            ),
        ),
    ]
