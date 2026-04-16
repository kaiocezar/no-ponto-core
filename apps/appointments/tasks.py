"""Tarefas Celery do app de agendamentos."""

from __future__ import annotations

import logging

from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True)
def send_whatsapp_confirmation(self, appointment_id: str) -> None:  # type: ignore[override]
    """Stub: P0-04 implementará envio real."""
    logger.info("WhatsApp stub: appointment %s pendente de confirmação", appointment_id)


@shared_task(bind=True, ignore_result=True)
def auto_confirm_pending_appointments(self) -> None:  # type: ignore[override]
    """Placeholder para confirmação automática (Beat)."""
    logger.debug("auto_confirm_pending_appointments: stub")


@shared_task(bind=True, ignore_result=True)
def mark_no_shows(self) -> None:  # type: ignore[override]
    """Placeholder para marcação de no-show (Beat)."""
    logger.debug("mark_no_shows: stub")
