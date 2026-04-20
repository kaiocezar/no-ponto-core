"""Serializers de serviços."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Any

from rest_framework import serializers

from apps.providers.models import ServiceStaff, Staff
from apps.services.models import Service


class StaffMinimalSerializer(serializers.Serializer[Staff]):
    """Representação mínima de Staff para leitura em serviços."""

    id = serializers.UUIDField(read_only=True)
    name = serializers.CharField(read_only=True)
    role = serializers.CharField(read_only=True)
    avatar_url = serializers.URLField(read_only=True, allow_null=True)


class ServiceSerializer(serializers.ModelSerializer[Service]):
    """
    Serializer completo de serviços do prestador.

    Escrita: name, description, price, duration_minutes, is_active, is_online,
             buffer_after, color, currency, requires_deposit, deposit_amount,
             max_clients, staff_ids (lista de UUIDs de Staff).
    Leitura: id, staff (lista resumida), created_at.
    """

    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        coerce_to_string=True,
        allow_null=True,
        required=False,
    )
    deposit_amount = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        coerce_to_string=True,
        allow_null=True,
        required=False,
    )
    duration_minutes = serializers.IntegerField()

    # Escrita: lista de UUIDs de Staff para vincular ao serviço
    staff_ids = serializers.ListField(
        child=serializers.UUIDField(),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="Lista de IDs de Staff a vincular. Substituição total no PATCH.",
    )
    # Leitura: staff resumido
    staff = StaffMinimalSerializer(
        source="staff_members",
        many=True,
        read_only=True,
    )

    class Meta:
        model = Service
        fields = [
            "id",
            "name",
            "description",
            "price",
            "duration_minutes",
            "is_active",
            "is_online",
            "buffer_after",
            "color",
            "currency",
            "requires_deposit",
            "deposit_amount",
            "max_clients",
            "staff_ids",
            "staff",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    # ── Validações de campo ──────────────────────────────────────────────────

    def validate_duration_minutes(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError("A duração deve ser maior que zero.")
        return value

    def validate_price(self, value: object) -> object:
        if isinstance(value, Decimal) and value < Decimal("0"):
            raise serializers.ValidationError("O preço não pode ser negativo.")
        return value

    def validate_deposit_amount(self, value: object) -> object:
        if isinstance(value, Decimal) and value < Decimal("0"):
            raise serializers.ValidationError("O valor do depósito não pode ser negativo.")
        return value

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Valida regras cross-field de depósito."""
        requires_deposit = attrs.get(
            "requires_deposit",
            getattr(self.instance, "requires_deposit", False),
        )
        deposit_amount = attrs.get(
            "deposit_amount",
            getattr(self.instance, "deposit_amount", None),
        )

        if requires_deposit and deposit_amount is None:
            raise serializers.ValidationError(
                {"deposit_amount": "Informe o valor do depósito quando requires_deposit=true."}
            )
        return attrs

    # ── Helpers ──────────────────────────────────────────────────────────────

    def _get_provider(self) -> Any:
        """Retorna o ProviderProfile da request ou do service existente."""
        request = self.context.get("request")
        if request and hasattr(request.user, "provider_profile"):
            return request.user.provider_profile
        if self.instance:
            return self.instance.provider
        return None

    def _sync_staff(self, service: Service, staff_ids: list[uuid.UUID]) -> None:
        """
        Substitui todos os vínculos ServiceStaff do serviço pelos staff_ids informados.

        Valida que todos os IDs pertencem ao provider do serviço.
        """
        provider = service.provider
        if staff_ids:
            valid_staff = Staff.objects.filter(
                id__in=staff_ids,
                provider=provider,
                is_active=True,
            )
            valid_ids = {s.id for s in valid_staff}
            invalid = set(staff_ids) - valid_ids
            if invalid:
                raise serializers.ValidationError(
                    {"staff_ids": f"Staff inválido ou inativo: {invalid}"}
                )
        ServiceStaff.objects.filter(service=service).delete()
        ServiceStaff.objects.bulk_create(
            [ServiceStaff(service=service, staff_id=sid) for sid in staff_ids]
        )

    # ── Create / Update ──────────────────────────────────────────────────────

    def create(self, validated_data: dict[str, Any]) -> Service:
        staff_ids: list[uuid.UUID] = validated_data.pop("staff_ids", [])
        service: Service = super().create(validated_data)
        if staff_ids:
            self._sync_staff(service, staff_ids)
        return service

    def update(self, instance: Service, validated_data: dict[str, Any]) -> Service:
        staff_ids: list[uuid.UUID] | None = validated_data.pop("staff_ids", None)
        service: Service = super().update(instance, validated_data)
        if staff_ids is not None:
            self._sync_staff(service, staff_ids)
        return service
