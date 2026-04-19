"""Tasks de processamento de mensagens inbound do WhatsApp."""

from __future__ import annotations

import logging
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatusHistory
from apps.notifications.tasks import (
    notify_provider_cancellation,
    send_reschedule_link,
    send_whatsapp_confirmed_ack,
)
from apps.webhooks.models import WhatsAppInboundMessage
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def process_whatsapp_response(wamid: str) -> None:
    try:
        inbound = WhatsAppInboundMessage.objects.select_related("related_appointment").get(
            wamid=wamid
        )
    except WhatsAppInboundMessage.DoesNotExist:
        return

    if inbound.processed:
        return

    payload = inbound.button_payload or ""
    if "_" not in payload:
        inbound.processed = True
        inbound.action_taken = "ignored"
        inbound.save(update_fields=["processed", "action_taken"])
        return

    action, raw_appointment_id = payload.split("_", 1)
    try:
        appointment_uuid = UUID(raw_appointment_id)
    except ValueError:
        inbound.processed = True
        inbound.action_taken = "invalid_payload"
        inbound.save(update_fields=["processed", "action_taken"])
        return

    try:
        appointment = Appointment.objects.get(pk=appointment_uuid)
    except Appointment.DoesNotExist:
        inbound.processed = True
        inbound.action_taken = "appointment_not_found"
        inbound.save(update_fields=["processed", "action_taken"])
        return

    inbound.related_appointment = appointment
    update_fields = ["related_appointment"]

    with transaction.atomic():
        if action == "CONFIRM" and appointment.status == Appointment.Status.PENDING_CONFIRMATION:
            old_status = appointment.status
            appointment.status = Appointment.Status.CONFIRMED
            appointment.save(update_fields=["status"])
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                from_status=old_status,
                to_status=Appointment.Status.CONFIRMED,
            )
            send_whatsapp_confirmed_ack.delay(str(appointment.pk))
            action_taken = "confirmed"
        elif action == "CANCEL":
            old_status = appointment.status
            appointment.status = Appointment.Status.CANCELLED
            appointment.cancelled_by = Appointment.CancelledBy.CLIENT
            appointment.cancelled_at = timezone.now()
            appointment.save(update_fields=["status", "cancelled_by", "cancelled_at"])
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                from_status=old_status,
                to_status=Appointment.Status.CANCELLED,
            )
            notify_provider_cancellation.delay(str(appointment.pk))
            action_taken = "cancelled"
        elif action == "RESCHEDULE":
            send_reschedule_link.delay(str(appointment.pk))
            action_taken = "reschedule_link_sent"
        else:
            action_taken = "ignored"

        inbound.processed = True
        inbound.action_taken = action_taken
        update_fields.extend(["processed", "action_taken"])
        inbound.save(update_fields=update_fields)
