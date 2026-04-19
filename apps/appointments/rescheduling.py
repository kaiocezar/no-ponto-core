"""Lógica de reagendamento reutilizável."""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from uuid import UUID

from django.db import transaction
from django.utils import timezone

from apps.appointments.models import Appointment, AppointmentStatusHistory, generate_public_id


@dataclass(frozen=True)
class RescheduleResult:
    """Resultado da tentativa de reagendamento."""

    code: str
    new_appointment: Appointment | None = None


def reschedule_appointment_atomically(
    *,
    appointment_id: UUID,
    new_start: datetime.datetime,
) -> RescheduleResult:
    """Reagenda um agendamento de forma atômica, cancelando o original."""
    with transaction.atomic():
        locked_appointment = (
            Appointment.objects.select_for_update()
            .select_related("provider", "service")
            .filter(pk=appointment_id)
            .first()
        )
        if locked_appointment is None:
            return RescheduleResult(code="not_found")

        new_end = new_start + datetime.timedelta(minutes=locked_appointment.service.duration)

        if locked_appointment.start_datetime <= timezone.now():
            return RescheduleResult(code="not_allowed")

        if locked_appointment.status in {
            Appointment.Status.NO_SHOW,
            Appointment.Status.COMPLETED,
        }:
            return RescheduleResult(code="not_allowed")

        # Permite reagendar após cancelamento do cliente (fluxo público),
        # mas bloqueia re-reagendamento de um agendamento já cancelado pelo sistema.
        if (
            locked_appointment.status == Appointment.Status.CANCELLED
            and locked_appointment.cancelled_by == Appointment.CancelledBy.SYSTEM
        ):
            return RescheduleResult(code="not_allowed")

        conflict = (
            Appointment.objects.select_for_update()
            .filter(
                provider=locked_appointment.provider,
                staff=locked_appointment.staff,
                start_datetime__lt=new_end,
                end_datetime__gt=new_start,
                status__in=[
                    Appointment.Status.PENDING_CONFIRMATION,
                    Appointment.Status.CONFIRMED,
                ],
            )
            .exclude(pk=locked_appointment.pk)
            .exists()
        )
        if conflict:
            return RescheduleResult(code="slot_taken")

        new_appointment = Appointment.objects.create(
            public_id=generate_public_id(),
            provider=locked_appointment.provider,
            service=locked_appointment.service,
            staff=locked_appointment.staff,
            client_name=locked_appointment.client_name,
            client_phone=locked_appointment.client_phone,
            client_email=locked_appointment.client_email,
            start_datetime=new_start,
            end_datetime=new_end,
            status=Appointment.Status.PENDING_CONFIRMATION,
            origin=locked_appointment.origin,
            notes=locked_appointment.notes,
            internal_notes=locked_appointment.internal_notes,
            price_at_booking=locked_appointment.price_at_booking,
            deposit_paid=locked_appointment.deposit_paid,
        )
        AppointmentStatusHistory.objects.create(
            appointment=new_appointment,
            from_status=None,
            to_status=Appointment.Status.PENDING_CONFIRMATION,
        )

        original_status = locked_appointment.status
        locked_appointment.status = Appointment.Status.CANCELLED
        locked_appointment.cancelled_by = Appointment.CancelledBy.SYSTEM
        locked_appointment.cancelled_at = timezone.now()
        locked_appointment.cancellation_reason = "reagendado"
        locked_appointment.save(
            update_fields=[
                "status",
                "cancelled_by",
                "cancelled_at",
                "cancellation_reason",
            ],
        )
        AppointmentStatusHistory.objects.create(
            appointment=locked_appointment,
            from_status=original_status,
            to_status=Appointment.Status.CANCELLED,
        )

    return RescheduleResult(code="ok", new_appointment=new_appointment)
