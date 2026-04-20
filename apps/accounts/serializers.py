"""Serializers de autenticação e usuário."""

from __future__ import annotations

from typing import Any

import phonenumbers
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
from apps.appointments.models import Appointment
from apps.providers.models import ProviderProfile


class UserMinimalSerializer(serializers.ModelSerializer[User]):
    """Serializer read-only com os campos mínimos do usuário."""

    class Meta:
        model = User
        fields = ["id", "full_name", "email", "avatar_url"]
        read_only_fields = ["id", "full_name", "email", "avatar_url"]


class ProviderRegisterSerializer(serializers.Serializer[User]):
    """Serializer para cadastro de novos prestadores via email/senha."""

    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, min_length=8)
    full_name = serializers.CharField(required=True)

    def validate_email(self, value: str) -> str:
        normalized = value.lower().strip()
        if User.objects.filter(email=normalized).exists():
            raise serializers.ValidationError("Este e-mail já está em uso.")
        return normalized

    def create(self, validated_data: dict[str, Any]) -> dict[str, Any]:
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            full_name=validated_data["full_name"],
            role=User.Role.PROVIDER,
            auth_provider=User.AuthProvider.EMAIL,
        )

        ProviderProfile.objects.create(user=user)

        refresh: RefreshToken = RefreshToken.for_user(user)

        return {
            "user": UserMinimalSerializer(user).data,
            "tokens": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
        }


class RequestOTPSerializer(serializers.Serializer[Any]):
    phone = serializers.CharField(max_length=20)

    def validate_phone(self, value: str) -> str:
        try:
            parsed = phonenumbers.parse(value, None)
        except phonenumbers.NumberParseException as exc:
            raise serializers.ValidationError("Telefone inválido. Use formato E.164.") from exc
        if not phonenumbers.is_valid_number(parsed):
            raise serializers.ValidationError("Telefone inválido. Use formato E.164.")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class VerifyOTPSerializer(serializers.Serializer[Any]):
    phone = serializers.CharField(max_length=20)
    code = serializers.RegexField(regex=r"^\d{6}$")

    def validate_phone(self, value: str) -> str:
        try:
            parsed = phonenumbers.parse(value, None)
        except phonenumbers.NumberParseException as exc:
            raise serializers.ValidationError("Telefone inválido. Use formato E.164.") from exc
        if not phonenumbers.is_valid_number(parsed):
            raise serializers.ValidationError("Telefone inválido. Use formato E.164.")
        return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


class CompleteProfileSerializer(serializers.Serializer[Any]):
    full_name = serializers.CharField(min_length=2, max_length=200)


class ClientMeSerializer(serializers.ModelSerializer[User]):
    class Meta:
        model = User
        fields = ["id", "phone_number", "full_name", "email", "birth_date"]
        read_only_fields = ["id", "phone_number"]

    def validate_email(self, value: str) -> str:
        normalized = value.lower().strip()
        user = self.instance
        if User.objects.filter(email=normalized).exclude(pk=getattr(user, "pk", None)).exists():
            raise serializers.ValidationError("Este e-mail já está em uso.")
        return normalized


class MyAppointmentSerializer(serializers.ModelSerializer[Appointment]):
    service_name = serializers.CharField(source="service.name", read_only=True)
    provider_name = serializers.CharField(source="provider.business_name", read_only=True)
    review_status = serializers.SerializerMethodField()
    review_token = serializers.SerializerMethodField()
    review_rating = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            "id",
            "public_id",
            "status",
            "start_datetime",
            "end_datetime",
            "service_name",
            "provider_name",
            "review_status",
            "review_token",
            "review_rating",
        ]

    def get_review_status(self, obj: Appointment) -> str | None:
        review = getattr(obj, "review", None)
        if review is None:
            return None
        if review.rating is not None:
            return "completed"
        if review.token_expires_at >= timezone.now():
            return "pending"
        return None

    def get_review_token(self, obj: Appointment) -> str | None:
        review = getattr(obj, "review", None)
        if review is None:
            return None
        if review.rating is None and review.token_expires_at >= timezone.now():
            return review.review_token
        return None

    def get_review_rating(self, obj: Appointment) -> int | None:
        review = getattr(obj, "review", None)
        return review.rating if review is not None else None
