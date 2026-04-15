"""Serializers de perfis de prestadores de serviço."""

from typing import Any

from rest_framework import serializers

from apps.providers.models import ProviderProfile, ScheduleBlock, ServiceCategory, WorkingHours


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


class WorkingHoursSerializer(serializers.ModelSerializer[WorkingHours]):
    """Serializer de horários de funcionamento."""

    start_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])
    end_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])

    class Meta:
        model = WorkingHours
        fields = ["id", "weekday", "start_time", "end_time", "is_active"]
        read_only_fields = ["id"]


class _WorkingHoursItemSerializer(serializers.Serializer[Any]):
    """Serializer de um item dentro do payload bulk."""

    weekday = serializers.IntegerField(min_value=0, max_value=6)
    start_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])
    end_time = serializers.TimeField(format="%H:%M", input_formats=["%H:%M", "%H:%M:%S"])
    is_active = serializers.BooleanField(default=True)

    def validate(self, data: dict[str, Any]) -> dict[str, Any]:
        if data["start_time"] >= data["end_time"]:
            raise serializers.ValidationError("O horário de abertura deve ser anterior ao de fechamento.")
        return data


class WorkingHoursBulkSerializer(serializers.Serializer[Any]):
    """Serializer para criação/substituição em lote de horários."""

    working_hours = _WorkingHoursItemSerializer(many=True)


class ScheduleBlockSerializer(serializers.ModelSerializer[ScheduleBlock]):
    """Serializer de bloqueios de agenda."""

    class Meta:
        model = ScheduleBlock
        fields = ["id", "start_datetime", "end_datetime", "reason", "created_at"]
        read_only_fields = ["id", "created_at"]
