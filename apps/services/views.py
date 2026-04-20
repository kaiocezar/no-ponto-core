"""Views de serviços do prestador."""

from __future__ import annotations

from typing import Any

from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.providers.models import ProviderProfile
from apps.services.models import Service
from apps.services.serializers import ServiceSerializer


def _get_or_create_provider(request: Request) -> ProviderProfile:
    provider, _ = ProviderProfile.objects.get_or_create(user=request.user)
    return provider


class ProviderServiceListCreateView(generics.ListCreateAPIView[Service]):
    """
    GET  /api/v1/providers/me/services/ — lista TODOS os serviços (ativos e inativos).
    POST /api/v1/providers/me/services/ — cria novo serviço.

    O queryset filtra pelo provider vinculado ao usuário autenticado.
    """

    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_queryset(self) -> Any:
        provider = _get_or_create_provider(self.request)
        return (
            Service.objects.filter(provider=provider)
            .prefetch_related("staff_members")
            .order_by("name")
        )

    def get_serializer_context(self) -> dict[str, Any]:
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def perform_create(self, serializer: ServiceSerializer) -> None:  # type: ignore[override]
        """Injeta o provider do usuário autenticado na criação do serviço."""
        provider = _get_or_create_provider(self.request)
        serializer.save(provider=provider)


class ProviderServiceDetailView(generics.RetrieveUpdateDestroyAPIView[Service]):
    """
    GET    /api/v1/providers/me/services/{uuid}/ — detalhe de um serviço.
    PATCH  /api/v1/providers/me/services/{uuid}/ — atualiza um serviço.
    DELETE /api/v1/providers/me/services/{uuid}/ — deleta fisicamente se sem agendamentos;
                                                    caso contrário retorna 400.

    O queryset filtra pelo provider do usuário autenticado — retorna 404
    automaticamente se o serviço pertencer a outro prestador.
    """

    serializer_class = ServiceSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self) -> Any:
        provider = _get_or_create_provider(self.request)
        return Service.objects.filter(provider=provider).prefetch_related("staff_members")

    def get_serializer_context(self) -> dict[str, Any]:
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def destroy(self, request: Request, *args: object, **kwargs: object) -> Response:
        """
        Deleta fisicamente apenas quando o serviço não possui agendamentos vinculados.
        Com agendamentos existentes retorna 400 orientando a desativar via /deactivate/.
        """
        service = self.get_object()
        if service.appointments.exists():
            return Response(
                {
                    "code": "SERVICE_HAS_APPOINTMENTS",
                    "detail": (
                        "O serviço possui agendamentos vinculados e não pode ser excluído. "
                        "Use a ação /deactivate/ para desativá-lo."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        service.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProviderServiceActivateView(APIView):
    """POST /api/v1/providers/me/services/{uuid}/activate/ — reativa um serviço."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        provider = _get_or_create_provider(request)
        try:
            service = Service.objects.get(pk=pk, provider=provider)
        except Service.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        service.is_active = True
        service.deactivated_at = None
        service.save(update_fields=["is_active", "deactivated_at", "updated_at"])
        return Response(
            ServiceSerializer(service, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class ProviderServiceDeactivateView(APIView):
    """POST /api/v1/providers/me/services/{uuid}/deactivate/ — desativa (soft delete) um serviço."""

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        provider = _get_or_create_provider(request)
        try:
            service = Service.objects.get(pk=pk, provider=provider)
        except Service.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        service.deactivate()
        return Response(
            ServiceSerializer(service, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class PublicProviderServicesView(generics.ListAPIView[Service]):
    """
    GET /api/v1/providers/{slug}/services/

    Lista serviços públicos (is_active=True, is_online=True) de um provider publicado.
    Sem autenticação.
    """

    serializer_class = ServiceSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self) -> Any:
        slug: str = self.kwargs["slug"]
        try:
            provider = ProviderProfile.objects.get(slug=slug, is_published=True)
        except ProviderProfile.DoesNotExist:
            return Service.objects.none()

        return (
            Service.objects.filter(provider=provider, is_active=True, is_online=True)
            .prefetch_related("staff_members")
            .order_by("name")
        )
