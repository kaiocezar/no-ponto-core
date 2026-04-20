"""Models de agendamentos."""

from __future__ import annotations

import secrets
import string
import uuid

from django.db import models


def generate_public_id() -> str:
    """Gera public_id único no formato AGD-XXXX com até 10 tentativas."""
    chars = string.ascii_uppercase + string.digits
    for _ in range(10):
        candidate = "AGD-" + "".join(secrets.choice(chars) for _ in range(4))
        if not Appointment.objects.filter(public_id=candidate).exists():
            return candidate
    msg = "Não foi possível gerar public_id único após 10 tentativas."
    raise RuntimeError(msg)


class Appointment(models.Model):
    """Agendamento entre cliente (sem conta) e prestador."""

    class Status(models.TextChoices):
        PENDING_CONFIRMATION = "pending_confirmation", "Pendente confirmação"
        CONFIRMED = "confirmed", "Confirmado"
        CANCELLED = "cancelled", "Cancelado"
        COMPLETED = "completed", "Concluído"
        NO_SHOW = "no_show", "Não compareceu"
        AWAITING_PAYMENT = "awaiting_payment", "Aguardando pagamento"

    class Origin(models.TextChoices):
        ONLINE = "online", "Online"
        WHATSAPP = "whatsapp", "WhatsApp"
        PHONE = "phone", "Telefone"
        WALK_IN = "walk_in", "Presencial"
        IMPORTED = "imported", "Importado"

    class CancelledBy(models.TextChoices):
        CLIENT = "client", "Cliente"
        PROVIDER = "provider", "Prestador"
        SYSTEM = "system", "Sistema"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    public_id = models.CharField(max_length=32, unique=True, db_index=True)
    provider = models.ForeignKey(
        "providers.ProviderProfile",
        on_delete=models.CASCADE,
        related_name="appointments",
    )
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.PROTECT,
        related_name="appointments",
    )
    staff = models.ForeignKey(
        "providers.Staff",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_appointments",
    )
    client = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    client_name = models.CharField(max_length=200)
    client_phone = models.CharField(max_length=32)
    client_email = models.EmailField(blank=True)
    start_datetime = models.DateTimeField(db_index=True)
    end_datetime = models.DateTimeField(db_index=True)
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.PENDING_CONFIRMATION,
        db_index=True,
    )
    origin = models.CharField(
        max_length=32,
        choices=Origin.choices,
        default=Origin.ONLINE,
    )
    notes = models.TextField(blank=True)
    internal_notes = models.TextField(blank=True)
    price_at_booking = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    deposit_paid = models.BooleanField(default=False)
    confirmation_sent = models.BooleanField(default=False)
    reminder_24h_sent = models.BooleanField(default=False)
    reminder_1h_sent = models.BooleanField(default=False)
    cancelled_by = models.CharField(
        max_length=16,
        choices=CancelledBy.choices,
        null=True,
        blank=True,
    )
    cancellation_reason = models.TextField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appointments_appointment"
        verbose_name = "Agendamento"
        verbose_name_plural = "Agendamentos"
        indexes = [
            models.Index(fields=["provider", "start_datetime", "end_datetime"]),
            models.Index(fields=["public_id"]),
        ]

    def __str__(self) -> str:
        return f"{self.public_id} ({self.provider.slug})"


class AppointmentStatusHistory(models.Model):
    """Histórico de transições de status."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        Appointment,
        on_delete=models.CASCADE,
        related_name="status_history",
    )
    from_status = models.CharField(max_length=32, blank=True, null=True)
    to_status = models.CharField(max_length=32)
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "appointments_appointment_status_history"
        ordering = ["changed_at"]
        verbose_name = "Histórico de status"
        verbose_name_plural = "Históricos de status"

    def __str__(self) -> str:
        return f"{self.to_status} ({self.changed_at})"
