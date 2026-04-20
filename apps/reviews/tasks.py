"""Tarefas Celery para coleta de avaliacoes."""

from __future__ import annotations

import secrets
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from celery import shared_task

from apps.appointments.models import Appointment
from apps.notifications.whatsapp import get_whatsapp_client
from apps.reviews.models import Review


@shared_task(ignore_result=True)
def send_review_request(appointment_id: str) -> None:
    appointment = (
        Appointment.objects.select_related("provider", "service", "client")
        .filter(pk=appointment_id)
        .first()
    )
    if appointment is None:
        return

    review, created = Review.objects.get_or_create(
        appointment=appointment,
        defaults={
            "provider": appointment.provider,
            "client": appointment.client,
            "client_name": appointment.client_name,
            "review_token": secrets.token_urlsafe(32),
            "token_expires_at": timezone.now() + timedelta(days=7),
        },
    )
    if not created:
        return

    review_url = f"{settings.FRONTEND_URL.rstrip('/')}/avaliar/{review.review_token}"
    get_whatsapp_client().send_template(
        to=appointment.client_phone,
        template_name="review_request",
        variables={
            "nome": appointment.client_name,
            "servico": appointment.service.name,
            "link": review_url,
        },
    )
