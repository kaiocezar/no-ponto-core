from django.db import migrations


def create_owner_staff(apps, schema_editor):
    ProviderProfile = apps.get_model("providers", "ProviderProfile")
    Staff = apps.get_model("providers", "Staff")

    for pp in ProviderProfile.objects.select_related("user").all():
        name = pp.user.full_name or pp.business_name or pp.user.email or str(pp.user.id)
        if not Staff.objects.filter(provider=pp, role="owner").exists():
            Staff.objects.create(
                provider=pp,
                user=pp.user,
                name=name,
                role="owner",
                is_active=True,
            )


def reverse_owner_staff(apps, schema_editor):
    Staff = apps.get_model("providers", "Staff")
    Staff.objects.filter(role="owner").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("providers", "0004_add_service_staff"),
    ]

    operations = [
        migrations.RunPython(create_owner_staff, reverse_owner_staff),
    ]
