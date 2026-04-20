import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("providers", "0002_add_working_hours_and_schedule_block"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Staff",
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
                ("invite_email", models.EmailField(blank=True, null=True)),
                ("invite_token", models.UUIDField(blank=True, null=True)),
                ("invite_expires_at", models.DateTimeField(blank=True, null=True)),
                ("name", models.CharField(max_length=200)),
                ("avatar_url", models.URLField(blank=True, max_length=500, null=True)),
                (
                    "role",
                    models.CharField(
                        choices=[
                            ("owner", "Proprietário"),
                            ("manager", "Gerente"),
                            ("practitioner", "Profissional"),
                        ],
                        default="practitioner",
                        max_length=20,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "provider",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="staff_members",
                        to="providers.providerprofile",
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="staff_roles",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Membro da Equipe",
                "verbose_name_plural": "Membros da Equipe",
                "db_table": "providers_staff",
                "indexes": [
                    models.Index(
                        fields=["provider", "is_active"],
                        name="providers_st_provide_is_active_idx",
                    ),
                ],
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(invite_token__isnull=False),
                        fields=["invite_token"],
                        name="staff_invite_token_unique",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(user__isnull=False)
                        | models.Q(invite_email__isnull=False),
                        name="staff_must_have_user_or_email",
                    ),
                ],
            },
        ),
    ]
