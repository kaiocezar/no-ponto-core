"""Models de serviços oferecidos pelos prestadores."""

import uuid

from django.db import models
from django.utils import timezone


class Service(models.Model):
    """
    Serviço oferecido por um prestador.

    Usa soft delete via is_active=False para não perder histórico
    de agendamentos que referenciam o serviço.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        "providers.ProviderProfile",
        on_delete=models.CASCADE,
        related_name="services",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Duração em minutos.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    is_online = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Se falso, o serviço não aparece para agendamento online público.",
    )
    buffer_after = models.PositiveIntegerField(
        default=0,
        help_text="Minutos de buffer após o término do serviço (afeta disponibilidade).",
    )
    color = models.CharField(max_length=7, null=True, blank=True)
    currency = models.CharField(max_length=3, default="BRL")
    requires_deposit = models.BooleanField(default=False)
    deposit_amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    max_clients = models.PositiveIntegerField(default=1)
    staff_members = models.ManyToManyField(
        "providers.Staff",
        through="providers.ServiceStaff",
        related_name="services",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Campo auxiliar para soft delete via deactivation
    deactivated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "services_service"
        ordering = ["name"]
        verbose_name = "Serviço"
        verbose_name_plural = "Serviços"
        indexes = [
            models.Index(fields=["provider", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.provider})"

    def deactivate(self) -> None:
        """
        Realiza soft delete marcando o serviço como inativo.
        O registro permanece no banco para preservar histórico de agendamentos.
        """
        self.is_active = False
        self.deactivated_at = timezone.now()
        self.save(update_fields=["is_active", "deactivated_at", "updated_at"])
