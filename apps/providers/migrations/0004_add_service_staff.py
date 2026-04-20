import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("providers", "0003_add_staff"),
        ("services", "0003_service_new_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="ServiceStaff",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "service",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_staff",
                        to="services.service",
                    ),
                ),
                (
                    "staff",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="service_assignments",
                        to="providers.staff",
                    ),
                ),
            ],
            options={
                "verbose_name": "Serviço por Profissional",
                "verbose_name_plural": "Serviços por Profissional",
                "db_table": "providers_service_staff",
                "unique_together": {("service", "staff")},
            },
        ),
    ]
