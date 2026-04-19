"""Serializers de agendamentos públicos."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from rest_framework import serializers

from apps.appointments.cancellation import get_cancel_deadline, validate_cancellation
from apps.appointments.models import Appointment
from apps.providers.models import ProviderProfile
from apps.services.models import Service


class AppointmentCreateSerializer(serializers.Serializer[Any]):
    """Payload público para criar agendamento."""

    provider_slug = serializers.SlugField()
    service_id = serializers.UUIDField()
    start_datetime = serializers.DateTimeField()
    client_name = serializers.CharField(max_length=200)
    client_phone = serializers.CharField(max_length=32)
    client_email = serializers.EmailField(required=False, allow_blank=True, default="")
    notes = serializers.CharField(required=False, allow_blank=True, default="")


class _ServiceBriefSerializer(serializers.ModelSerializer[Service]):
    duration_minutes = serializers.IntegerField(source="duration", read_only=True)

    class Meta:
        model = Service
        fields = ["id", "name", "duration_minutes"]


class _ProviderBriefSerializer(serializers.ModelSerializer[ProviderProfile]):
    class Meta:
        model = ProviderProfile
        fields = ["slug", "business_name"]


class AppointmentPublicSerializer(serializers.ModelSerializer[Appointment]):
    service = _ServiceBriefSerializer(read_only=True)
    provider = _ProviderBriefSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "public_id",
            "status",
            "start_datetime",
            "end_datetime",
            "service",
            "provider",
        ]


class AppointmentLookupSerializer(serializers.ModelSerializer[Appointment]):
    service = _ServiceBriefSerializer(read_only=True)
    provider = _ProviderBriefSerializer(read_only=True)
    can_cancel = serializers.SerializerMethodField()
    cancel_deadline = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "public_id",
            "status",
            "start_datetime",
            "end_datetime",
            "client_name",
            "service",
            "provider",
            "notes",
            "price_at_booking",
            "can_cancel",
            "cancel_deadline",
        ]

    def get_can_cancel(self, obj: Appointment) -> bool:
        return validate_cancellation(obj, cancelled_by=Appointment.CancelledBy.CLIENT) is None

    def get_cancel_deadline(self, obj: Appointment) -> datetime | None:
        return get_cancel_deadline(obj)


class AppointmentCancelByCodeSerializer(serializers.Serializer[Any]):
    """Payload público para cancelamento por código + telefone."""

    public_id = serializers.CharField(max_length=32)
    phone = serializers.CharField(max_length=32)
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True)


class AppointmentSlotSerializer(serializers.Serializer[Any]):
    """Representa um slot de reagendamento."""

    start_datetime = serializers.DateTimeField()
    end_datetime = serializers.DateTimeField()


class AppointmentRescheduleOptionsSerializer(serializers.Serializer[Any]):
    """Resposta de opções de reagendamento."""

    slots = AppointmentSlotSerializer(many=True)
    message = serializers.CharField(required=False)


class AppointmentRescheduleSerializer(serializers.Serializer[Any]):
    """Payload para reagendamento por link público."""

    phone = serializers.CharField(max_length=32)
    start_datetime = serializers.DateTimeField()
