"""Serializers de serviços."""

from rest_framework import serializers

from apps.services.models import Service


class ServiceSerializer(serializers.ModelSerializer[Service]):
    """
    Serializer de serviços do prestador.

    Campos de escrita: name, description, price, duration, is_active.
    Campos read_only: id, created_at.
    """

    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        coerce_to_string=True,
    )
    duration_minutes = serializers.IntegerField(source="duration")

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
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def validate_duration_minutes(self, value: int) -> int:
        if value <= 0:
            raise serializers.ValidationError("A duração deve ser maior que zero.")
        return value

    def validate_price(self, value: object) -> object:
        from decimal import Decimal

        if isinstance(value, Decimal) and value < Decimal("0"):
            raise serializers.ValidationError("O preço não pode ser negativo.")
        return value
