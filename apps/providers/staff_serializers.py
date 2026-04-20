"""Serializers de Staff (equipe do prestador)."""

from __future__ import annotations

from typing import Any

from rest_framework import serializers

from apps.accounts.serializers import UserMinimalSerializer
from apps.providers.models import Staff


class StaffSerializer(serializers.ModelSerializer[Staff]):
    """
    Serializer completo de Staff para leitura/edição pelo prestador.

    Campos read-only: id, user, created_at.
    Campos editáveis pelo PATCH: name, role, is_active, avatar_url.
    """

    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = Staff
        fields = [
            "id",
            "name",
            "role",
            "is_active",
            "avatar_url",
            "invite_email",
            "invite_token",
            "invite_expires_at",
            "user",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "invite_token",
            "invite_expires_at",
            "user",
            "created_at",
            "updated_at",
        ]

    def validate_role(self, value: str) -> str:
        """Impede que um manager/practitioner promova alguém a owner."""
        instance: Staff | None = self.instance
        if value == "owner" and instance and instance.role != "owner":
            raise serializers.ValidationError("Não é possível alterar o papel para proprietário.")
        return value


class StaffInviteSerializer(serializers.Serializer[Staff]):
    """Serializer para criação de convite de Staff."""

    name = serializers.CharField(max_length=200)
    invite_email = serializers.EmailField()
    role = serializers.ChoiceField(choices=["manager", "practitioner"])

    def validate_invite_email(self, value: str) -> str:
        return value.lower().strip()

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """
        Verifica se já existe um Staff ativo com esse email no mesmo provider
        (duplicatas de convite pendente).
        """
        provider = self.context.get("provider")
        email = attrs["invite_email"]
        if (
            provider
            and Staff.objects.filter(
                provider=provider,
                invite_email=email,
                is_active=True,
            ).exists()
        ):
            raise serializers.ValidationError(
                {"invite_email": "Já existe um convite ativo para este e-mail."}
            )
        return attrs
