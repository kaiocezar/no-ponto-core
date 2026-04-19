"""Tarefas Celery periodicas do app de agendamentos."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatusHistory
from apps.notifications.tasks import send_whatsapp_reminder_1h, send_whatsapp_reminder_24h
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def send_24h_reminders() -> None:
    now = timezone.now()
    window_start = now + timedelta(hours=23)
    window_end = now + timedelta(hours=25)
    appointments = Appointment.objects.filter(
        status=Appointment.Status.CONFIRMED,
        start_datetime__gte=window_start,
        start_datetime__lte=window_end,
        reminder_24h_sent=False,
    )
    for appointment in appointments:
        appointment.reminder_24h_sent = True
        appointment.save(update_fields=["reminder_24h_sent"])
        send_whatsapp_reminder_24h.delay(str(appointment.pk))


@shared_task(ignore_result=True)
def send_1h_reminders() -> None:
    now = timezone.now()
    window_start = now + timedelta(minutes=55)
    window_end = now + timedelta(minutes=65)
    appointments = Appointment.objects.filter(
        status=Appointment.Status.CONFIRMED,
        start_datetime__gte=window_start,
        start_datetime__lte=window_end,
        reminder_1h_sent=False,
    )
    for appointment in appointments:
        appointment.reminder_1h_sent = True
        appointment.save(update_fields=["reminder_1h_sent"])
        send_whatsapp_reminder_1h.delay(str(appointment.pk))


@shared_task(ignore_result=True)
def auto_confirm_pending_appointments() -> None:
    threshold = timezone.now() - timedelta(hours=24)
    appointments = Appointment.objects.filter(
        status=Appointment.Status.PENDING_CONFIRMATION,
        created_at__lte=threshold,
    )
    for appointment in appointments:
        from_status = appointment.status
        with transaction.atomic():
            appointment.status = Appointment.Status.CONFIRMED
            appointment.save(update_fields=["status"])
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                from_status=from_status,
                to_status=Appointment.Status.CONFIRMED,
            )


@shared_task(ignore_result=True)
def mark_no_shows() -> None:
    now = timezone.now()
    appointments = Appointment.objects.filter(
        status=Appointment.Status.CONFIRMED,
        end_datetime__lt=now,
    )
    for appointment in appointments:
        from_status = appointment.status
        with transaction.atomic():
            appointment.status = Appointment.Status.NO_SHOW
            appointment.save(update_fields=["status"])
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                from_status=from_status,
                to_status=Appointment.Status.NO_SHOW,
            )
