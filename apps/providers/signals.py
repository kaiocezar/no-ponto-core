"""Signals do app providers."""

from __future__ import annotations

from typing import Any

from django.db.models.signals import post_save
from django.dispatch import receiver


@receiver(post_save, sender="providers.ProviderProfile")
def create_owner_staff_on_provider_created(
    sender: Any,
    instance: Any,
    created: bool,
    **kwargs: Any,
) -> None:
    """
    Cria automaticamente um Staff(role=owner) ao criar um novo ProviderProfile.

    Garante que todo provider sempre tenha um staff proprietário sem precisar
    de lógica extra nas views. Usa get_or_create para idempotência — não duplica
    se a migration de dados já tiver criado o registro.
    """
    if not created:
        return

    from apps.providers.models import Staff  # import tardio para evitar circular

    Staff.objects.get_or_create(
        provider=instance,
        user=instance.user,
        role="owner",
        defaults={
            "name": instance.user.full_name or instance.business_name or str(instance.user),
            "is_active": True,
        },
    )
