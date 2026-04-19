"""Views públicas de agendamento."""

from __future__ import annotations

import datetime

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.appointments.cancellation import validate_cancellation
from apps.appointments.models import (
    Appointment,
    AppointmentStatusHistory,
    generate_public_id,
)
from apps.appointments.phone import normalize_phone_for_match
from apps.appointments.rescheduling import reschedule_appointment_atomically
from apps.appointments.serializers import (
    AppointmentCancelByCodeSerializer,
    AppointmentCreateSerializer,
    AppointmentLookupSerializer,
    AppointmentPublicSerializer,
    AppointmentRescheduleOptionsSerializer,
    AppointmentRescheduleSerializer,
    AppointmentSlotSerializer,
)
from apps.notifications.tasks import (
    notify_provider_cancellation,
    notify_provider_new_appointment,
    send_cancellation_ack_client,
    send_whatsapp_confirmation_request,
)
from apps.providers.models import ProviderProfile
from apps.services.models import Service
from core.exceptions import ServiceUnavailableError, SlotNotAvailableError


def _collect_reschedule_slots(
    appointment: Appointment,
    *,
    limit: int = 10,
    days_ahead: int = 60,
) -> list[dict[str, datetime.datetime]]:
    from core.utils.availability import get_available_slots

    slots: list[dict[str, datetime.datetime]] = []
    today = timezone.localdate()

    for day_offset in range(days_ahead):
        date = today + datetime.timedelta(days=day_offset)
        available = get_available_slots(
            provider=appointment.provider,
            service_duration=appointment.service.duration,
            buffer_after=appointment.service.buffer_after,
            date=date,
            staff=appointment.staff,
        )
        for start in available:
            end = start + datetime.timedelta(minutes=appointment.service.duration)
            slots.append({"start_datetime": start, "end_datetime": end})
            if len(slots) >= limit:
                return slots
    return slots


class AppointmentCreateView(APIView):
    """
    POST /api/v1/appointments/

    Criação pública de agendamento (sem autenticação).
    """

    permission_classes = [AllowAny]

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        ser = AppointmentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        provider = get_object_or_404(
            ProviderProfile.objects.filter(is_published=True),
            slug=data["provider_slug"],
        )

        try:
            service = Service.objects.get(pk=data["service_id"], provider=provider)
        except Service.DoesNotExist:
            raise ServiceUnavailableError(
                detail="Serviço não encontrado para este prestador.",
            ) from None

        if not service.is_active or not service.is_online:
            raise ServiceUnavailableError()

        start = data["start_datetime"]
        if timezone.is_naive(start):
            raise ValidationError(
                {"start_datetime": "Informe data/hora com fuso horário (ISO 8601)."},
            )

        end = start + datetime.timedelta(minutes=service.duration)
        client_phone = normalize_phone_for_match(data["client_phone"])

        with transaction.atomic():
            ProviderProfile.objects.select_for_update().filter(pk=provider.pk).first()
            conflict = (
                Appointment.objects.select_for_update()
                .filter(
                    provider=provider,
                    start_datetime__lt=end,
                    end_datetime__gt=start,
                    status__in=[
                        Appointment.Status.PENDING_CONFIRMATION,
                        Appointment.Status.CONFIRMED,
                    ],
                )
                .exists()
            )
            if conflict:
                raise SlotNotAvailableError()

            public_id = generate_public_id()
            appointment = Appointment.objects.create(
                public_id=public_id,
                provider=provider,
                service=service,
                staff=None,
                client_name=data["client_name"],
                client_phone=client_phone,
                client_email=(data.get("client_email") or "").strip(),
                start_datetime=start,
                end_datetime=end,
                status=Appointment.Status.PENDING_CONFIRMATION,
                origin=Appointment.Origin.ONLINE,
                notes=(data.get("notes") or "").strip(),
                internal_notes="",
                price_at_booking=service.price,
                deposit_paid=False,
            )
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                from_status=None,
                to_status=Appointment.Status.PENDING_CONFIRMATION,
            )

        aid = str(appointment.pk)
        if getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
            send_whatsapp_confirmation_request.apply(args=[aid], throw=True)
            notify_provider_new_appointment.apply(args=[aid], throw=True)
        else:
            send_whatsapp_confirmation_request.delay(aid)
            notify_provider_new_appointment.delay(aid)
        return Response(
            AppointmentPublicSerializer(appointment).data,
            status=status.HTTP_201_CREATED,
        )


class AppointmentLookupView(APIView):
    """
    GET /api/v1/appointments/lookup/?public_id=&phone=
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        public_id = request.query_params.get("public_id")
        phone = request.query_params.get("phone")
        if not public_id or not phone:
            raise ValidationError(
                {"public_id": "Obrigatório", "phone": "Obrigatório"},
            )

        appointment = (
            Appointment.objects.filter(public_id=public_id)
            .select_related("service", "provider")
            .first()
        )
        if appointment is None:
            raise Http404()

        if normalize_phone_for_match(phone) != appointment.client_phone:
            raise Http404()

        return Response(AppointmentLookupSerializer(appointment).data)


class AppointmentCancelByCodeView(APIView):
    """
    POST /api/v1/appointments/cancel-by-code/
    """

    permission_classes = [AllowAny]

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        ser = AppointmentCancelByCodeSerializer(data=request.data)
        ser.is_valid(raise_exception=True)

        public_id = ser.validated_data["public_id"]
        phone = normalize_phone_for_match(ser.validated_data["phone"])
        reason = (ser.validated_data.get("reason") or "").strip() or None
        appointment = (
            Appointment.objects.select_related("provider")
            .filter(public_id=public_id, client_phone=phone)
            .first()
        )
        if appointment is None:
            raise Http404()

        if validation_error := validate_cancellation(
            appointment=appointment,
            cancelled_by=Appointment.CancelledBy.CLIENT,
        ):
            return Response(
                validation_error.as_response_payload(),
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        from_status = appointment.status
        with transaction.atomic():
            appointment.status = Appointment.Status.CANCELLED
            appointment.cancelled_by = Appointment.CancelledBy.CLIENT
            appointment.cancelled_at = timezone.now()
            appointment.cancellation_reason = reason
            appointment.save(
                update_fields=[
                    "status",
                    "cancelled_by",
                    "cancelled_at",
                    "cancellation_reason",
                ],
            )
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                from_status=from_status,
                to_status=Appointment.Status.CANCELLED,
            )

        cache.delete(f"availability:{appointment.provider_id}:{appointment.start_datetime.date()}")
        appointment_id = str(appointment.pk)
        notify_provider_cancellation.apply_async(args=[appointment_id], queue="high_priority")
        send_cancellation_ack_client.apply_async(args=[appointment_id], queue="high_priority")
        return Response(AppointmentLookupSerializer(appointment).data, status=status.HTTP_200_OK)


class AppointmentRescheduleOptionsView(APIView):
    """
    GET /api/v1/appointments/{id}/reschedule-options/?phone=
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        phone = request.query_params.get("phone")
        if not phone:
            raise ValidationError({"phone": "Obrigatório"})

        normalized_phone = normalize_phone_for_match(phone)
        appointment = (
            Appointment.objects.select_related("provider", "service")
            .filter(pk=pk, client_phone=normalized_phone)
            .first()
        )
        if appointment is None:
            raise Http404()

        slots = _collect_reschedule_slots(appointment)
        payload: dict[str, object] = {"slots": AppointmentSlotSerializer(slots, many=True).data}
        if not slots:
            payload["message"] = "Sem horários disponíveis nos próximos 60 dias."

        serializer = AppointmentRescheduleOptionsSerializer(data=payload)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class AppointmentRescheduleView(APIView):
    """
    POST /api/v1/appointments/{id}/reschedule/
    """

    permission_classes = [AllowAny]

    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        serializer = AppointmentRescheduleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        normalized_phone = normalize_phone_for_match(serializer.validated_data["phone"])
        new_start = serializer.validated_data["start_datetime"]
        if timezone.is_naive(new_start):
            raise ValidationError(
                {"start_datetime": "Informe data/hora com fuso horário (ISO 8601)."},
            )

        appointment = (
            Appointment.objects.select_related("provider", "service")
            .filter(pk=pk, client_phone=normalized_phone)
            .first()
        )
        if appointment is None:
            raise Http404()

        result = reschedule_appointment_atomically(
            appointment_id=appointment.pk,
            new_start=new_start,
        )
        if result.code == "slot_taken":
            slots = _collect_reschedule_slots(appointment)
            return Response(
                {
                    "code": "slot_taken",
                    "available_slots": AppointmentSlotSerializer(slots, many=True).data,
                },
                status=status.HTTP_409_CONFLICT,
            )
        if result.code == "not_found":
            raise Http404()
        if result.code == "not_allowed" or result.new_appointment is None:
            if appointment.start_datetime <= timezone.now():
                return Response(
                    {"code": "appointment_in_past"},
                    status=status.HTTP_422_UNPROCESSABLE_ENTITY,
                )
            return Response(
                {"code": "invalid_status_for_reschedule"},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        new_appointment = result.new_appointment

        send_whatsapp_confirmation_request.apply_async(
            args=[str(new_appointment.pk)],
            queue="high_priority",
        )
        return Response(
            AppointmentLookupSerializer(new_appointment).data,
            status=status.HTTP_201_CREATED,
        )
