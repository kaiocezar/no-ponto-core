"""Views de perfis de prestadores de serviço."""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db.models import Count, Max, OuterRef, Q, Subquery
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveAPIView, RetrieveUpdateAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.serializers import BaseSerializer
from rest_framework.views import APIView

from apps.appointments.models import Appointment
from apps.providers.models import ProviderProfile, ServiceCategory
from apps.providers.serializers import (
    ClientAppointmentHistorySerializer,
    ClientListSerializer,
    ClientNoteCreateSerializer,
    ClientNoteSerializer,
    ProviderProfileReadSerializer,
    ProviderProfileWriteSerializer,
    ProviderDashboardNextAppointmentSerializer,
    ServiceCategorySerializer,
)
from core.pagination import CursorPagination


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
    Requer:
    - business_name preenchido
    - endereço completo (street, city, state, zip)
    - pelo menos 1 serviço ativo cadastrado
    """

    permission_classes = [IsAuthenticated]

    _ADDRESS_FIELDS: tuple[str, ...] = (
        "address_street",
        "address_city",
        "address_state",
        "address_zip",
    )

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        profile, _ = ProviderProfile.objects.get_or_create(user=request.user)

        errors: dict[str, str] = {}

        if not profile.business_name:
            errors["business_name"] = "Preencha o nome do negócio antes de publicar."

        missing_address = [field for field in self._ADDRESS_FIELDS if not getattr(profile, field)]
        if missing_address:
            for field in missing_address:
                errors[field] = "Este campo é obrigatório para publicar o perfil."

        if not profile.services.filter(is_active=True).exists():
            errors["services"] = "Cadastre pelo menos um serviço ativo antes de publicar."

        if errors:
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Preencha todos os campos obrigatórios antes de publicar.",
                        "details": errors,
                    }
                },
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
    queryset = ProviderProfile.objects.filter(is_published=True).select_related("user", "category")


class ServiceCategoryListView(ListAPIView):
    """
    GET /api/v1/categories/

    Lista todas as categorias de serviço disponíveis.
    """

    permission_classes = [AllowAny]
    serializer_class = ServiceCategorySerializer
    queryset = ServiceCategory.objects.all()
    pagination_class = None


class DashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        provider = request.user.provider_profile
        provider_tz = ZoneInfo(provider.timezone or "America/Sao_Paulo")
        now_provider = timezone.now().astimezone(provider_tz)
        today_start = datetime.datetime.combine(
            now_provider.date(), datetime.time.min, tzinfo=provider_tz
        )
        tomorrow_start = today_start + datetime.timedelta(days=1)
        week_start = today_start - datetime.timedelta(days=now_provider.weekday())
        month_start = today_start.replace(day=1)
        cache_key = f"dashboard:{provider.id}:{now_provider.date().isoformat()}"

        if cached := cache.get(cache_key):
            return Response(cached)

        provider_qs = Appointment.objects.filter(provider=provider)
        today_qs = provider_qs.filter(start_datetime__gte=today_start, start_datetime__lt=tomorrow_start)
        week_qs = provider_qs.filter(start_datetime__gte=week_start, start_datetime__lt=tomorrow_start)
        month_qs = provider_qs.filter(start_datetime__gte=month_start, start_datetime__lt=tomorrow_start)

        week_total = week_qs.count()
        week_cancelled = week_qs.filter(status=Appointment.Status.CANCELLED).count()
        cancellation_rate = round((week_cancelled / week_total) * 100, 1) if week_total else 0.0

        next_appointments = (
            provider_qs.select_related("service")
            .filter(
                start_datetime__gte=timezone.now(),
                status__in=[Appointment.Status.CONFIRMED, Appointment.Status.PENDING_CONFIRMATION],
            )
            .order_by("start_datetime")[:5]
        )
        next_payload = [
            {
                "id": ap.id,
                "public_id": ap.public_id,
                "client_name": ap.client_name,
                "service_name": ap.service.name,
                "start_datetime": ap.start_datetime,
                "status": ap.status,
            }
            for ap in next_appointments
        ]
        payload = {
            "today": {
                "total": today_qs.count(),
                "confirmed": today_qs.filter(status=Appointment.Status.CONFIRMED).count(),
                "pending_confirmation": today_qs.filter(
                    status=Appointment.Status.PENDING_CONFIRMATION
                ).count(),
                "cancelled": today_qs.filter(status=Appointment.Status.CANCELLED).count(),
                "completed": today_qs.filter(status=Appointment.Status.COMPLETED).count(),
                "no_show": today_qs.filter(status=Appointment.Status.NO_SHOW).count(),
            },
            "week": {
                "total": week_total,
                "confirmed": week_qs.filter(status=Appointment.Status.CONFIRMED).count(),
                "cancelled": week_cancelled,
                "cancellation_rate": cancellation_rate,
            },
            "month": {"total": month_qs.count()},
            "next_appointments": ProviderDashboardNextAppointmentSerializer(next_payload, many=True).data,
        }
        cache.set(cache_key, payload, timeout=120)
        return Response(payload)


class ClientListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        provider = request.user.provider_profile
        search = (request.query_params.get("search") or "").strip()
        base_qs = Appointment.objects.filter(provider=provider)
        if search:
            base_qs = base_qs.filter(
                Q(client_name__icontains=search) | Q(client_phone__icontains=search)
            )

        latest_name_subquery = (
            Appointment.objects.filter(provider=provider, client_phone=OuterRef("client_phone"))
            .order_by("-start_datetime")
            .values("client_name")[:1]
        )
        rows = (
            base_qs.values("client_phone")
            .annotate(
                total_appointments=Count("id"),
                last_appointment_date=Max("start_datetime"),
                client_name=Subquery(latest_name_subquery),
            )
            .order_by("-last_appointment_date")
        )
        return Response(ClientListSerializer(rows, many=True).data)


class ClientAppointmentHistoryView(ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = ClientAppointmentHistorySerializer
    pagination_class = CursorPagination

    def get_queryset(self):  # type: ignore[no-untyped-def]
        provider = self.request.user.provider_profile
        qs = (
            Appointment.objects.filter(provider=provider, client_phone=self.kwargs["phone"])
            .select_related("service", "staff")
            .order_by("-start_datetime")
        )
        if status_filter := self.request.query_params.get("status"):
            qs = qs.filter(status=status_filter)
        if date_from := self.request.query_params.get("date_from"):
            qs = qs.filter(start_datetime__date__gte=date_from)
        if date_to := self.request.query_params.get("date_to"):
            qs = qs.filter(start_datetime__date__lte=date_to)
        return qs


class ClientNoteView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request: Request, phone: str, *args: object, **kwargs: object) -> Response:
        notes = request.user.provider_profile.client_notes.filter(client_phone=phone)
        return Response(ClientNoteSerializer(notes, many=True).data)

    def post(self, request: Request, phone: str, *args: object, **kwargs: object) -> Response:
        serializer = ClientNoteCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        note = request.user.provider_profile.client_notes.create(
            client_phone=phone,
            client_user=Appointment.objects.filter(
                provider=request.user.provider_profile,
                client_phone=phone,
            )
            .exclude(client=None)
            .values_list("client", flat=True)
            .first(),
            created_by=request.user,
            note=serializer.validated_data["note"].strip(),
        )
        return Response(ClientNoteSerializer(note).data, status=status.HTTP_201_CREATED)
