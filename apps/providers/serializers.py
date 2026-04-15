"""Serializers de perfis de prestadores de serviço."""

from typing import Any

from rest_framework import serializers

from apps.providers.models import ProviderProfile, ServiceCategory


class ServiceCategorySerializer(serializers.ModelSerializer[ServiceCategory]):
    """Serializer completo de categorias de serviço."""

    class Meta:
        model = ServiceCategory
        fields = ["id", "name", "icon", "slug", "created_at"]


class ProviderProfileReadSerializer(serializers.ModelSerializer[ProviderProfile]):
    """Serializer read-only de perfil de prestador com categoria aninhada."""

    category = ServiceCategorySerializer(read_only=True)
    rating_average = serializers.SerializerMethodField()

    class Meta:
        model = ProviderProfile
        fields = [
            "id",
            "user",
            "slug",
            "business_name",
            "bio",
            "specialty",
            "category",
            "logo_url",
            "cover_url",
            "address_street",
            "address_city",
            "address_state",
            "address_zip",
            "address_lat",
            "address_lng",
            "timezone",
            "default_appointment_duration",
            "default_buffer_time",
            "max_advance_days",
            "min_notice_hours",
            "whatsapp_number",
            "instagram_handle",
            "website_url",
            "is_published",
            "created_at",
            "updated_at",
            "rating_average",
        ]

    def get_rating_average(self, obj: ProviderProfile) -> None:
        # Implementar na task de reviews
        return None


class ProviderProfileWriteSerializer(serializers.ModelSerializer[ProviderProfile]):
    """Serializer de escrita para atualização de perfil de prestador."""

    class Meta:
        model = ProviderProfile
        fields = [
            "business_name",
            "bio",
            "specialty",
            "category",
            "logo_url",
            "cover_url",
            "address_street",
            "address_city",
            "address_state",
            "address_zip",
            "address_lat",
            "address_lng",
            "timezone",
            "default_appointment_duration",
            "default_buffer_time",
            "max_advance_days",
            "min_notice_hours",
            "whatsapp_number",
            "instagram_handle",
            "website_url",
        ]

    def validate_business_name(self, value: str) -> str:
        if value:
            # Verifica apenas slugs reservados (sem consultar o banco)
            ProviderProfile.generate_unique_slug(value, check_reserved_only=True)
        return value

    def update(self, instance: ProviderProfile, validated_data: dict[str, Any]) -> ProviderProfile:
        for attr, val in validated_data.items():
            setattr(instance, attr, val)

        update_fields = list(validated_data.keys()) + ["updated_at"]
        instance.save(update_fields=update_fields)
        return instance
