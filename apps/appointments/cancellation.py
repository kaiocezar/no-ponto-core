"""Regras de negócio para cancelamento de agendamentos."""

from __future__ import annotations

import datetime
from dataclasses import dataclass

from django.utils import timezone

from apps.appointments.models import Appointment


@dataclass(frozen=True)
class CancellationError:
    """Erro de validação de cancelamento com payload para resposta HTTP."""

    code: str
    details: dict[str, int] | None = None

    def as_response_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code}
        if self.details:
            payload.update(self.details)
        return payload


def get_cancel_deadline(appointment: Appointment) -> datetime.datetime | None:
    """Calcula deadline de cancelamento para o cliente."""
    if appointment.status in {
        Appointment.Status.CANCELLED,
        Appointment.Status.NO_SHOW,
        Appointment.Status.COMPLETED,
    }:
        return None
    return appointment.start_datetime - datetime.timedelta(
        hours=appointment.provider.min_notice_hours
    )


def validate_cancellation(
    appointment: Appointment,
    cancelled_by: str,
) -> CancellationError | None:
    """Valida se o agendamento pode ser cancelado no momento."""
    if appointment.start_datetime <= timezone.now():
        return CancellationError(code="appointment_in_past")

    if appointment.status not in {
        Appointment.Status.PENDING_CONFIRMATION,
        Appointment.Status.CONFIRMED,
    }:
        return CancellationError(code="invalid_status_for_cancellation")

    if cancelled_by == Appointment.CancelledBy.CLIENT:
        deadline = get_cancel_deadline(appointment)
        if deadline is not None and timezone.now() > deadline:
            return CancellationError(
                code="cancellation_window_closed",
                details={"min_notice_hours": appointment.provider.min_notice_hours},
            )

    return None
