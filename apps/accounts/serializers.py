"""Serializers de autenticação e usuário."""

from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.models import User
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

    def create(self, validated_data: dict) -> dict:
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
