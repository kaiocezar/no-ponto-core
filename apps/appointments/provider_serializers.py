"""Serializers para gestão de agendamentos pelo prestador."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.appointments.models import Appointment
from apps.services.models import Service


class _ProviderServiceBriefSerializer(serializers.ModelSerializer[Service]):
    duration_minutes = serializers.IntegerField(source="duration", read_only=True)

    class Meta:
        model = Service
        fields = ["id", "name", "duration_minutes"]


class ProviderAppointmentListSerializer(serializers.ModelSerializer[Appointment]):
    service = _ProviderServiceBriefSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "public_id",
            "client_name",
            "client_phone",
            "service",
            "status",
            "start_datetime",
            "end_datetime",
            "origin",
        ]


class ProviderAppointmentDetailSerializer(serializers.ModelSerializer[Appointment]):
    service = _ProviderServiceBriefSerializer(read_only=True)

    class Meta:
        model = Appointment
        fields = [
            "id",
            "public_id",
            "client_name",
            "client_phone",
            "client_email",
            "service",
            "status",
            "start_datetime",
            "end_datetime",
            "origin",
            "notes",
            "internal_notes",
            "cancelled_by",
            "cancellation_reason",
            "created_at",
        ]


class ProviderAppointmentPatchSerializer(serializers.ModelSerializer[Appointment]):
    class Meta:
        model = Appointment
        fields = ["internal_notes"]


class ProviderAppointmentCreateSerializer(serializers.Serializer[Any]):
    service_id = serializers.UUIDField()
    start_datetime = serializers.DateTimeField()
    client_name = serializers.CharField(max_length=200)
    client_phone = serializers.CharField(max_length=32)
    origin = serializers.ChoiceField(
        choices=[
            (Appointment.Origin.PHONE, Appointment.Origin.PHONE.label),
            (Appointment.Origin.WALK_IN, Appointment.Origin.WALK_IN.label),
        ],
    )
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    internal_notes = serializers.CharField(required=False, allow_blank=True, default="")


class ProviderCancelSerializer(serializers.Serializer[Any]):
    reason = serializers.CharField(required=False, allow_blank=True, allow_null=True, default=None)
