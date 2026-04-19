"""Models de notificacoes outbound."""

from __future__ import annotations

import uuid

from django.db import models


class Notification(models.Model):
    """Rastreia notificacoes enviadas para appointments."""

    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"

    class Type(models.TextChoices):
        CONFIRMATION_REQUEST = "confirmation_request", "Confirmacao de agendamento"
        NEW_APPOINTMENT_PROVIDER = "new_appointment_provider", "Novo agendamento para prestador"
        CONFIRMED_ACK = "confirmed_ack", "Confirmacao recebida"
        CANCELLED_PROVIDER = "cancelled_provider", "Cancelamento para prestador"
        REMINDER_24H = "reminder_24h", "Lembrete 24h"
        REMINDER_1H = "reminder_1h", "Lembrete 1h"
        RESCHEDULE_LINK = "reschedule_link", "Link de reagendamento"

    class Status(models.TextChoices):
        PENDING = "pending", "Pendente"
        SENT = "sent", "Enviado"
        FAILED = "failed", "Falhou"
        DELIVERED = "delivered", "Entregue"
        READ = "read", "Lido"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    channel = models.CharField(max_length=32, choices=Channel.choices)
    type = models.CharField(max_length=64, choices=Type.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    external_id = models.CharField(max_length=255, blank=True)
    template_name = models.CharField(max_length=255, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "notifications_notification"
        indexes = [
            models.Index(fields=["appointment", "type"]),
            models.Index(fields=["status", "created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.type} ({self.status})"
