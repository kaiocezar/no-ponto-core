"""API de agendamentos para o prestador autenticado."""

from __future__ import annotations

import contextlib
import datetime
import uuid
from typing import Any

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated
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
from apps.appointments.provider_serializers import (
    ProviderAppointmentCreateSerializer,
    ProviderAppointmentDetailSerializer,
    ProviderAppointmentListSerializer,
    ProviderAppointmentPatchSerializer,
    ProviderCancelSerializer,
)
from apps.notifications.tasks import (
    notify_client_provider_cancellation,
    send_pending_review_requests,
)
from apps.providers.models import ProviderProfile
from apps.services.models import Service
from core.exceptions import SlotNotAvailableError
from core.permissions import IsProviderUser


def _provider_profile(request: Request) -> Any:
    return request.user.provider_profile


def _provider_appointment_queryset(request: Request) -> Any:
    return (
        Appointment.objects.filter(provider=_provider_profile(request))
        .select_related("service", "client")
        .order_by("start_datetime")
    )


def _parse_date_param(value: str, name: str) -> datetime.date:
    try:
        return datetime.date.fromisoformat(value)
    except ValueError as exc:
        raise ValidationError({name: "Use o formato ISO (AAAA-MM-DD)."}) from exc


class ProviderAppointmentListCreateView(ListCreateAPIView):
    """GET lista / POST criação manual (confirmado, sem WhatsApp de confirmação)."""

    permission_classes = [IsAuthenticated, IsProviderUser]
    pagination_class = None

    def get_serializer_class(
        self,
    ) -> type[ProviderAppointmentListSerializer | ProviderAppointmentCreateSerializer]:
        if self.request.method == "POST":
            return ProviderAppointmentCreateSerializer
        return ProviderAppointmentListSerializer

    def get_queryset(self) -> Any:
        qs = _provider_appointment_queryset(self.request)
        params = self.request.query_params
        if df := params.get("date_from"):
            d0 = _parse_date_param(df, "date_from")
            qs = qs.filter(start_datetime__date__gte=d0)
        if dt := params.get("date_to"):
            d1 = _parse_date_param(dt, "date_to")
            qs = qs.filter(start_datetime__date__lte=d1)
        if st := params.get("status"):
            qs = qs.filter(status=st)
        if sid := params.get("staff_id"):
            with contextlib.suppress(ValueError):
                qs = qs.filter(staff_id=uuid.UUID(sid))
        return qs

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        provider = _provider_profile(request)
        ser = ProviderAppointmentCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = ser.validated_data

        try:
            service = Service.objects.get(pk=data["service_id"], provider=provider)
        except Service.DoesNotExist as exc:
            raise ValidationError(
                {"service_id": "Serviço não encontrado para o seu perfil."},
            ) from exc

        start = data["start_datetime"]
        if timezone.is_naive(start):
            raise ValidationError(
                {"start_datetime": "Informe data/hora com fuso horário (ISO 8601)."},
            )

        end = start + datetime.timedelta(minutes=service.duration_minutes)
        phone = normalize_phone_for_match(data["client_phone"])

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
                client=None,
                client_name=data["client_name"].strip(),
                client_phone=phone,
                client_email="",
                start_datetime=start,
                end_datetime=end,
                status=Appointment.Status.CONFIRMED,
                origin=data["origin"],
                notes=(data.get("notes") or "").strip(),
                internal_notes=(data.get("internal_notes") or "").strip(),
                price_at_booking=service.price,
                deposit_paid=False,
            )
            AppointmentStatusHistory.objects.create(
                appointment=appointment,
                from_status=None,
                to_status=Appointment.Status.CONFIRMED,
            )

        return Response(
            ProviderAppointmentDetailSerializer(appointment).data,
            status=status.HTTP_201_CREATED,
        )


class ProviderAppointmentDetailView(RetrieveUpdateAPIView):
    """GET detalhe / PATCH internal_notes."""

    permission_classes = [IsAuthenticated, IsProviderUser]
    lookup_field = "pk"

    def get_queryset(self) -> Any:
        return _provider_appointment_queryset(self.request)

    def get_serializer_class(
        self,
    ) -> type[ProviderAppointmentDetailSerializer | ProviderAppointmentPatchSerializer]:
        if self.request.method == "PATCH":
            return ProviderAppointmentPatchSerializer
        return ProviderAppointmentDetailSerializer


class _ProviderAppointmentActionView(APIView):
    permission_classes = [IsAuthenticated, IsProviderUser]

    def get_appointment(self, request: Request, pk: str) -> Appointment:
        return get_object_or_404(_provider_appointment_queryset(request), pk=pk)


class ProviderAppointmentConfirmView(_ProviderAppointmentActionView):
    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        appointment = self.get_appointment(request, pk)
        if appointment.status != Appointment.Status.PENDING_CONFIRMATION:
            return Response(
                {"code": "invalid_status", "detail": "Apenas pendentes de confirmação."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        prev = appointment.status
        appointment.status = Appointment.Status.CONFIRMED
        appointment.save(update_fields=["status"])
        AppointmentStatusHistory.objects.create(
            appointment=appointment,
            from_status=prev,
            to_status=Appointment.Status.CONFIRMED,
        )
        return Response(ProviderAppointmentDetailSerializer(appointment).data)


class ProviderAppointmentCompleteView(_ProviderAppointmentActionView):
    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        appointment = self.get_appointment(request, pk)
        if appointment.status != Appointment.Status.CONFIRMED:
            return Response(
                {"code": "invalid_status", "detail": "Apenas agendamentos confirmados."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        prev = appointment.status
        appointment.status = Appointment.Status.COMPLETED
        appointment.save(update_fields=["status"])
        AppointmentStatusHistory.objects.create(
            appointment=appointment,
            from_status=prev,
            to_status=Appointment.Status.COMPLETED,
        )
        send_pending_review_requests.delay()
        return Response(ProviderAppointmentDetailSerializer(appointment).data)


class ProviderAppointmentNoShowView(_ProviderAppointmentActionView):
    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        appointment = self.get_appointment(request, pk)
        if appointment.status != Appointment.Status.CONFIRMED:
            return Response(
                {"code": "invalid_status", "detail": "Apenas agendamentos confirmados."},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        prev = appointment.status
        appointment.status = Appointment.Status.NO_SHOW
        appointment.save(update_fields=["status"])
        AppointmentStatusHistory.objects.create(
            appointment=appointment,
            from_status=prev,
            to_status=Appointment.Status.NO_SHOW,
        )
        return Response(ProviderAppointmentDetailSerializer(appointment).data)


class ProviderAppointmentCancelView(_ProviderAppointmentActionView):
    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        appointment = self.get_appointment(request, pk)
        ser = ProviderCancelSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        reason = (ser.validated_data.get("reason") or "").strip() or None

        if err := validate_cancellation(appointment, cancelled_by=Appointment.CancelledBy.PROVIDER):
            return Response(err.as_response_payload(), status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        prev = appointment.status
        with transaction.atomic():
            appointment.status = Appointment.Status.CANCELLED
            appointment.cancelled_by = Appointment.CancelledBy.PROVIDER
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
                from_status=prev,
                to_status=Appointment.Status.CANCELLED,
            )

        notify_client_provider_cancellation.delay(str(appointment.pk))
        return Response(ProviderAppointmentDetailSerializer(appointment).data)
