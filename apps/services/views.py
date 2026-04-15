"""Views de serviços do prestador."""

from typing import Any

from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response

from apps.providers.models import ProviderProfile
from apps.services.models import Service
from apps.services.serializers import ServiceSerializer


class ProviderServiceListCreateView(generics.ListCreateAPIView[Service]):
    """
    GET  /api/v1/providers/me/services/ — lista serviços do prestador autenticado.
    POST /api/v1/providers/me/services/ — cria novo serviço para o prestador autenticado.

    O queryset é sempre filtrado pelo provider vinculado ao usuário da requisição,
    eliminando qualquer risco de acesso cruzado.
    """

    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None  # Serviços não precisam de paginação cursor

    def get_queryset(self) -> Any:
        provider, _ = ProviderProfile.objects.get_or_create(user=self.request.user)
        return (
            Service.objects.filter(provider=provider, is_active=True)
            .select_related("provider")
            .order_by("name")
        )

    def perform_create(self, serializer: ServiceSerializer) -> None:  # type: ignore[override]
        """Injeta o provider do usuário autenticado na criação do serviço."""
        provider, _ = ProviderProfile.objects.get_or_create(user=self.request.user)
        serializer.save(provider=provider)


class ProviderServiceDetailView(generics.RetrieveUpdateDestroyAPIView[Service]):
    """
    GET    /api/v1/providers/me/services/{uuid}/ — detalhe de um serviço.
    PATCH  /api/v1/providers/me/services/{uuid}/ — atualiza um serviço.
    DELETE /api/v1/providers/me/services/{uuid}/ — soft delete (is_active=False).

    O queryset filtra pelo provider do usuário autenticado — retorna 404
    automaticamente se o serviço pertencer a outro prestador.
    """

    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self) -> Any:
        provider, _ = ProviderProfile.objects.get_or_create(user=self.request.user)
        # Inclui is_active=False para permitir GET/PATCH em serviços já desativados
        return Service.objects.filter(provider=provider).select_related("provider")

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """
        Soft delete: marca o serviço como inativo em vez de excluí-lo do banco.
        Preserva o histórico de agendamentos vinculados ao serviço.
        """
        service = self.get_object()
        service.deactivate()
        return Response(status=status.HTTP_204_NO_CONTENT)
