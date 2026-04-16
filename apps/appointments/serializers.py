"""Serializers de agendamentos públicos."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

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

    class Meta:
        model = Appointment
        fields = [
            "public_id",
            "status",
            "start_datetime",
            "end_datetime",
            "client_name",
            "service",
            "provider",
            "notes",
            "price_at_booking",
        ]
