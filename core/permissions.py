"""Permissões customizadas para a API."""

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView


class IsProviderOwner(BasePermission):
    """Permite acesso apenas ao dono do ProviderProfile."""

    message = "Você não tem permissão para acessar este recurso."

    def has_permission(self, request: Request, view: APIView) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        return hasattr(request.user, "provider_profile")

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        provider = getattr(obj, "provider", obj)
        return getattr(provider, "user_id", None) == request.user.pk


class IsProviderStaffOwner(BasePermission):
    """
    Permite acesso apenas quando o usuário autenticado possui um Staff(role=owner)
    ativo vinculado ao seu ProviderProfile.
    """

    message = "Apenas proprietários podem executar esta ação."

    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.providers.models import Staff  # import tardio para evitar circular

        user = request.user
        if not user or not user.is_authenticated:
            return False
        provider = getattr(user, "provider_profile", None)
        if provider is None:
            return False
        return Staff.objects.filter(
            provider=provider,
            user=user,
            role="owner",
            is_active=True,
        ).exists()


class IsProviderStaffOwnerOrManager(BasePermission):
    """
    Permite acesso quando o usuário autenticado possui Staff com role owner
    ou manager ativo no seu ProviderProfile.
    """

    message = "Apenas proprietários ou gerentes podem executar esta ação."

    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.providers.models import Staff  # import tardio para evitar circular

        user = request.user
        if not user or not user.is_authenticated:
            return False
        provider = getattr(user, "provider_profile", None)
        if provider is None:
            return False
        return Staff.objects.filter(
            provider=provider,
            user=user,
            role__in=("owner", "manager"),
            is_active=True,
        ).exists()


class IsProviderUser(IsProviderOwner):
    """Alias para endpoints do prestador (mesmas regras que IsProviderOwner)."""


class IsProviderOwnerOrReadOnly(BasePermission):
    """
    GET/HEAD/OPTIONS são públicos.
    POST/PUT/PATCH/DELETE requerem ser o owner do provider.
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        provider = getattr(obj, "provider", obj)
        return getattr(provider, "user_id", None) == request.user.pk


class IsOwnerOrReadOnly(BasePermission):
    """Permite leitura para qualquer um, escrita apenas para o dono do objeto."""

    def has_object_permission(self, request: Request, view: APIView, obj: object) -> bool:
        if request.method in ("GET", "HEAD", "OPTIONS"):
            return True
        return getattr(obj, "user_id", getattr(obj, "client_id", None)) == request.user.pk


class IsClientUser(BasePermission):
    """Permite acesso apenas para usuários autenticados com role de cliente."""

    message = "Apenas clientes podem acessar este recurso."

    def has_permission(self, request: Request, view: APIView) -> bool:
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return getattr(user, "role", None) == "client"
