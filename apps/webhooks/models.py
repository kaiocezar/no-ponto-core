"""Models de mensagens inbound via webhook."""

from __future__ import annotations

import uuid

from django.db import models


class WhatsAppInboundMessage(models.Model):
    """Mensagem recebida do webhook WhatsApp para processamento assincrono."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    wamid = models.CharField(max_length=255, unique=True, db_index=True)
    from_phone = models.CharField(max_length=32)
    body = models.TextField(blank=True)
    message_type = models.CharField(max_length=32, blank=True)
    button_payload = models.CharField(max_length=255, blank=True)
    related_appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inbound_whatsapp_messages",
    )
    processed = models.BooleanField(default=False, db_index=True)
    action_taken = models.CharField(max_length=64, blank=True)
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "webhooks_whatsapp_inbound_message"
        indexes = [
            models.Index(fields=["processed", "received_at"]),
        ]

    def __str__(self) -> str:
        return self.wamid
