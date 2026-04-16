"""Views públicas de agendamento."""

from __future__ import annotations

import datetime

from django.conf import settings
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

from apps.appointments.models import Appointment, AppointmentStatusHistory, generate_public_id
from apps.appointments.phone import normalize_phone_for_match
from apps.appointments.serializers import (
    AppointmentCreateSerializer,
    AppointmentLookupSerializer,
    AppointmentPublicSerializer,
)
from apps.appointments.tasks import send_whatsapp_confirmation
from apps.providers.models import ProviderProfile
from apps.services.models import Service
from core.exceptions import ServiceUnavailableError, SlotNotAvailableError


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
            send_whatsapp_confirmation.apply(args=[aid], throw=True)
        else:
            send_whatsapp_confirmation.delay(aid)
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
