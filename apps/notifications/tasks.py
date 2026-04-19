"""Tarefas Celery de notificacoes WhatsApp."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.notifications.models import Notification
from apps.notifications.whatsapp import get_whatsapp_client
from celery import shared_task

logger = logging.getLogger(__name__)


def _send_template_and_track(
    *,
    appointment: Appointment,
    to: str,
    template_name: str,
    notification_type: str,
    variables: dict[str, str],
    buttons: list[str] | None = None,
    notification: Notification | None = None,
) -> None:
    if notification is None:
        notification = Notification.objects.create(
            appointment=appointment,
            channel=Notification.Channel.WHATSAPP,
            type=notification_type,
            status=Notification.Status.PENDING,
            template_name=template_name,
            payload={"to": to, "variables": variables, "buttons": buttons or []},
        )
    else:
        notification.channel = Notification.Channel.WHATSAPP
        notification.type = notification_type
        notification.status = Notification.Status.PENDING
        notification.template_name = template_name
        notification.payload = {"to": to, "variables": variables, "buttons": buttons or []}
        notification.error_message = ""
        notification.external_id = ""
        notification.sent_at = None
        notification.save(
            update_fields=[
                "channel",
                "type",
                "status",
                "template_name",
                "payload",
                "error_message",
                "external_id",
                "sent_at",
            ],
        )
    payload = get_whatsapp_client().send_template(
        to=to,
        template_name=template_name,
        variables=variables,
        buttons=buttons,
    )
    notification.external_id = payload.get("external_id", "")
    notification.status = Notification.Status.SENT
    notification.sent_at = timezone.now()
    notification.save(update_fields=["external_id", "status", "sent_at"])


def _resolve_client_display_name(appointment: Appointment) -> str:
    client = appointment.client
    if client is not None:
        full = (client.full_name or "").strip()
        if full:
            return full
    return appointment.client_name


@shared_task(bind=True, ignore_result=True, max_retries=3, queue="high_priority")
def send_whatsapp_confirmation_request(self, appointment_id: str) -> None:  # type: ignore[override]
    try:
        appointment = Appointment.objects.select_related("provider", "service").get(
            pk=appointment_id
        )
        _send_template_and_track(
            appointment=appointment,
            to=appointment.client_phone,
            template_name="appointment_confirmation_request",
            notification_type=Notification.Type.CONFIRMATION_REQUEST,
            variables={
                "nome": appointment.client_name,
                "servico": appointment.service.name,
                "data_hora": timezone.localtime(appointment.start_datetime).strftime("%d/%m %H:%M"),
            },
            buttons=[
                f"CONFIRM_{appointment.pk}",
                f"CANCEL_{appointment.pk}",
                f"RESCHEDULE_{appointment.pk}",
            ],
        )
        appointment.confirmation_sent = True
        appointment.save(update_fields=["confirmation_sent"])
    except Exception as exc:
        logger.exception("Falha ao enviar confirmacao WhatsApp para %s", appointment_id)
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            return
        countdown = 2**self.request.retries
        raise self.retry(exc=exc, countdown=countdown) from exc


@shared_task(bind=True, ignore_result=True, max_retries=3, queue="high_priority")
def notify_provider_new_appointment(self, appointment_id: str) -> None:  # type: ignore[override]
    try:
        appointment = Appointment.objects.select_related("provider", "service", "client").get(
            pk=appointment_id
        )
        client_label = _resolve_client_display_name(appointment)

        try:
            with transaction.atomic():
                notification, created = Notification.objects.get_or_create(
                    appointment=appointment,
                    type=Notification.Type.NEW_APPOINTMENT_PROVIDER,
                    defaults={
                        "channel": Notification.Channel.WHATSAPP,
                        "status": Notification.Status.PENDING,
                        "template_name": "",
                        "payload": {},
                    },
                )
        except IntegrityError:
            notification = Notification.objects.get(
                appointment=appointment,
                type=Notification.Type.NEW_APPOINTMENT_PROVIDER,
            )
            created = False

        if not created and notification.status == Notification.Status.SENT:
            return

        whatsapp_number = (appointment.provider.whatsapp_number or "").strip()
        if not whatsapp_number:
            notification.channel = Notification.Channel.EMAIL
            notification.status = Notification.Status.FAILED
            notification.error_message = "Email não configurado no MVP"
            notification.save(
                update_fields=["channel", "status", "error_message"],
            )
            logger.warning(
                "Prestador %s sem WhatsApp: stub de email para novo agendamento %s",
                appointment.provider_id,
                appointment_id,
            )
            return

        _send_template_and_track(
            appointment=appointment,
            to=whatsapp_number,
            template_name="new_appointment_provider",
            notification_type=Notification.Type.NEW_APPOINTMENT_PROVIDER,
            variables={
                "cliente": client_label,
                "servico": appointment.service.name,
                "data_hora": timezone.localtime(appointment.start_datetime).strftime("%d/%m %H:%M"),
            },
            notification=notification,
        )
    except Exception as exc:
        logger.exception("Falha ao notificar prestador sobre agendamento %s", appointment_id)
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            return
        countdown = 2**self.request.retries
        raise self.retry(exc=exc, countdown=countdown) from exc


@shared_task(ignore_result=True)
def send_whatsapp_confirmed_ack(appointment_id: str) -> None:
    appointment = Appointment.objects.select_related("service").get(pk=appointment_id)
    _send_template_and_track(
        appointment=appointment,
        to=appointment.client_phone,
        template_name="appointment_confirmed",
        notification_type=Notification.Type.CONFIRMED_ACK,
        variables={"servico": appointment.service.name},
    )


@shared_task(ignore_result=True)
def notify_provider_cancellation(appointment_id: str) -> None:
    appointment = Appointment.objects.select_related("provider").get(pk=appointment_id)
    whatsapp_number = appointment.provider.whatsapp_number
    if not whatsapp_number:
        return
    _send_template_and_track(
        appointment=appointment,
        to=whatsapp_number,
        template_name="appointment_cancelled_by_client",
        notification_type=Notification.Type.CANCELLED_PROVIDER,
        variables={"cliente": appointment.client_name},
    )


@shared_task(ignore_result=True)
def send_cancellation_ack_client(appointment_id: str) -> None:
    appointment = Appointment.objects.select_related("service").get(pk=appointment_id)
    _send_template_and_track(
        appointment=appointment,
        to=appointment.client_phone,
        template_name="appointment_cancelled_by_client",
        notification_type=Notification.Type.CANCELLED_CLIENT_ACK,
        variables={"servico": appointment.service.name},
        buttons=[f"RESCHEDULE_{appointment.pk}"],
    )


@shared_task(ignore_result=True)
def notify_client_provider_cancellation(appointment_id: str) -> None:
    """Fila aviso ao cliente quando o prestador cancela (delega ao template existente)."""
    send_cancellation_ack_client.delay(appointment_id)


@shared_task(ignore_result=True)
def send_whatsapp_reminder_24h(appointment_id: str) -> None:
    appointment = Appointment.objects.select_related("service").get(pk=appointment_id)
    _send_template_and_track(
        appointment=appointment,
        to=appointment.client_phone,
        template_name="appointment_reminder_24h",
        notification_type=Notification.Type.REMINDER_24H,
        variables={
            "servico": appointment.service.name,
            "data_hora": timezone.localtime(appointment.start_datetime).strftime("%d/%m %H:%M"),
        },
        buttons=[
            f"CONFIRM_{appointment.pk}",
            f"CANCEL_{appointment.pk}",
            f"RESCHEDULE_{appointment.pk}",
        ],
    )
    appointment.reminder_24h_sent = True
    appointment.save(update_fields=["reminder_24h_sent"])


@shared_task(ignore_result=True)
def send_whatsapp_reminder_1h(appointment_id: str) -> None:
    appointment = Appointment.objects.select_related("service").get(pk=appointment_id)
    _send_template_and_track(
        appointment=appointment,
        to=appointment.client_phone,
        template_name="appointment_reminder_1h",
        notification_type=Notification.Type.REMINDER_1H,
        variables={
            "servico": appointment.service.name,
            "data_hora": timezone.localtime(appointment.start_datetime).strftime("%d/%m %H:%M"),
        },
    )
    appointment.reminder_1h_sent = True
    appointment.save(update_fields=["reminder_1h_sent"])


@shared_task(ignore_result=True)
def send_reschedule_link(appointment_id: str) -> None:
    appointment = Appointment.objects.select_related("provider").get(pk=appointment_id)
    link = f"{settings.FRONTEND_URL.rstrip('/')}/{appointment.provider.slug}/agendar"
    _send_template_and_track(
        appointment=appointment,
        to=appointment.client_phone,
        template_name="reschedule_link",
        notification_type=Notification.Type.RESCHEDULE_LINK,
        variables={"link": link},
    )


@shared_task(ignore_result=True)
def send_pending_review_requests() -> None:
    logger.debug("send_pending_review_requests: stub")
