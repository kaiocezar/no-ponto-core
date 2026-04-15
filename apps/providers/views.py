"""Views de perfis de prestadores de serviço."""

from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.providers.models import ProviderProfile, ServiceCategory
from apps.providers.serializers import (
    ProviderProfileReadSerializer,
    ProviderProfileWriteSerializer,
    ServiceCategorySerializer,
)


class ProviderMeView(RetrieveUpdateAPIView):
    """
    GET  /api/v1/providers/me/  — retorna o perfil do prestador autenticado.
    PATCH /api/v1/providers/me/ — atualiza o perfil do prestador autenticado.
    """

    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "patch", "head", "options"]

    def get_object(self) -> ProviderProfile:
        profile, _ = ProviderProfile.objects.get_or_create(user=self.request.user)
        return profile

    def get_serializer_class(self) -> type[BaseSerializer]:
        if self.request.method in ("PUT", "PATCH"):
            return ProviderProfileWriteSerializer
        return ProviderProfileReadSerializer


class ProviderPublishView(APIView):
    """
    POST /api/v1/providers/me/publish/

    Publica o perfil do prestador autenticado.
    Requer que o campo business_name esteja preenchido.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        profile, _ = ProviderProfile.objects.get_or_create(user=request.user)

        if not profile.business_name:
            return Response(
                {"error": {"code": "VALIDATION_ERROR", "message": "Preencha o nome do negócio antes de publicar."}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profile.is_published = True
        profile.save(update_fields=["is_published", "updated_at"])

        return Response(
            ProviderProfileReadSerializer(profile, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class ProviderUnpublishView(APIView):
    """
    POST /api/v1/providers/me/unpublish/

    Remove o perfil do prestador autenticado da listagem pública.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        profile, _ = ProviderProfile.objects.get_or_create(user=request.user)

        profile.is_published = False
        profile.save(update_fields=["is_published", "updated_at"])

        return Response(
            ProviderProfileReadSerializer(profile, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class PublicProviderProfileView(RetrieveAPIView):
    """
    GET /api/v1/providers/<slug>/

    Retorna o perfil público de um prestador publicado.
    Retorna 404 automaticamente se não encontrado ou não publicado.
    """

    permission_classes = [AllowAny]
    serializer_class = ProviderProfileReadSerializer
    lookup_field = "slug"
    queryset = ProviderProfile.objects.filter(is_published=True).select_related(
        "user", "category"
    )


class ServiceCategoryListView(ListAPIView):
    """
    GET /api/v1/categories/

    Lista todas as categorias de serviço disponíveis.
    """

    permission_classes = [AllowAny]
    serializer_class = ServiceCategorySerializer
    queryset = ServiceCategory.objects.all()
    pagination_class = None
