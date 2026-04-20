"""Views de Staff (equipe do prestador)."""

from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Any

from django.utils import timezone
from rest_framework import generics, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.providers.models import ProviderProfile, ServiceStaff, Staff
from apps.providers.staff_serializers import StaffInviteSerializer, StaffSerializer
from core.permissions import IsProviderStaffOwnerOrManager

INVITE_EXPIRY_DAYS = 7


def _get_provider(request: Request) -> ProviderProfile:
    """Retorna ou cria o ProviderProfile do usuário autenticado."""
    profile, _ = ProviderProfile.objects.get_or_create(user=request.user)
    return profile


class StaffListCreateView(APIView):
    """
    GET  /api/v1/providers/me/staff/      — lista toda a equipe do prestador.
    POST /api/v1/providers/me/staff/      — cria convite de novo membro (owner/manager).
    """

    permission_classes = [IsAuthenticated, IsProviderStaffOwnerOrManager]

    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        provider = _get_provider(request)
        staff_qs = Staff.objects.filter(provider=provider).select_related("user").order_by("name")
        serializer = StaffSerializer(staff_qs, many=True)
        return Response(serializer.data)

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        """Cria convite — gera token e dispara e-mail assíncrono."""
        provider = _get_provider(request)
        serializer = StaffInviteSerializer(
            data=request.data,
            context={"request": request, "provider": provider},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        staff = Staff.objects.create(
            provider=provider,
            name=data["name"],
            invite_email=data["invite_email"],
            role=data["role"],
            invite_token=uuid.uuid4(),
            invite_expires_at=timezone.now() + timedelta(days=INVITE_EXPIRY_DAYS),
            is_active=True,
        )

        from apps.providers.tasks import send_staff_invite_email

        send_staff_invite_email.delay(str(staff.pk))

        return Response(StaffSerializer(staff).data, status=status.HTTP_201_CREATED)


class StaffDetailView(APIView):
    """
    GET    /api/v1/providers/me/staff/{id}/ — detalhe do membro.
    PATCH  /api/v1/providers/me/staff/{id}/ — edita name, role, is_active.
    DELETE /api/v1/providers/me/staff/{id}/ — soft delete (is_active=False).
                                               Bloqueado se o membro possui
                                               agendamentos futuros.
    """

    permission_classes = [IsAuthenticated, IsProviderStaffOwnerOrManager]

    def _get_staff(self, request: Request, pk: str) -> Staff | None:
        provider = _get_provider(request)
        try:
            return Staff.objects.select_related("user").get(pk=pk, provider=provider)
        except Staff.DoesNotExist:
            return None

    def get(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        staff = self._get_staff(request, pk)
        if staff is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(StaffSerializer(staff).data)

    def patch(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        staff = self._get_staff(request, pk)
        if staff is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        # Protege o owner de ser rebaixado ou desativado por managers/practitioners
        requesting_staff = Staff.objects.filter(
            provider=staff.provider,
            user=request.user,
            is_active=True,
        ).first()
        if staff.role == "owner" and requesting_staff and requesting_staff.role != "owner":
            return Response(
                {"detail": "Apenas proprietários podem editar o perfil de outro proprietário."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = StaffSerializer(staff, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        """
        Soft delete — impede desativação se o profissional tem agendamentos futuros.
        Owner não pode ser desativado.
        """
        from apps.appointments.models import Appointment

        staff = self._get_staff(request, pk)
        if staff is None:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if staff.role == "owner":
            return Response(
                {"detail": "O proprietário não pode ser desativado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        has_future = Appointment.objects.filter(
            staff=staff,
            start_datetime__gte=timezone.now(),
            status__in=["pending_confirmation", "confirmed"],
        ).exists()
        if has_future:
            return Response(
                {
                    "code": "STAFF_HAS_FUTURE_APPOINTMENTS",
                    "detail": (
                        "O profissional possui agendamentos futuros. "
                        "Reatribua-os antes de desativá-lo."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        staff.is_active = False
        staff.save(update_fields=["is_active", "updated_at"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class StaffResendInviteView(APIView):
    """
    POST /api/v1/providers/me/staff/{id}/resend-invite/

    Gera novo token de convite e reenvia o e-mail.
    Disponível apenas para staff que ainda não aceitou o convite (user=None).
    """

    permission_classes = [IsAuthenticated, IsProviderStaffOwnerOrManager]

    def post(self, request: Request, pk: str, *args: object, **kwargs: object) -> Response:
        provider = _get_provider(request)
        try:
            staff = Staff.objects.get(pk=pk, provider=provider)
        except Staff.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if staff.user is not None:
            return Response(
                {"detail": "O convite já foi aceito. Não é possível reenviar."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not staff.invite_email:
            return Response(
                {"detail": "O membro não possui e-mail de convite cadastrado."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        staff.invite_token = uuid.uuid4()
        staff.invite_expires_at = timezone.now() + timedelta(days=INVITE_EXPIRY_DAYS)
        staff.save(update_fields=["invite_token", "invite_expires_at", "updated_at"])

        from apps.providers.tasks import send_staff_invite_email

        send_staff_invite_email.delay(str(staff.pk))

        return Response(StaffSerializer(staff).data)


class PublicProviderStaffView(generics.ListAPIView[Staff]):
    """
    GET /api/v1/providers/{slug}/staff/?service_id=

    Lista staff ativo de um provider publicado.
    Quando service_id é informado, filtra apenas staff vinculado ao serviço.
    Sem autenticação.
    """

    serializer_class = StaffSerializer
    permission_classes = [AllowAny]
    pagination_class = None

    def get_queryset(self) -> Any:
        slug: str = self.kwargs["slug"]
        try:
            provider = ProviderProfile.objects.get(slug=slug, is_published=True)
        except ProviderProfile.DoesNotExist:
            return Staff.objects.none()

        qs = Staff.objects.filter(provider=provider, is_active=True).select_related("user")

        service_id = self.request.query_params.get("service_id")
        if service_id:
            try:
                sid = uuid.UUID(service_id)
            except ValueError:
                return Staff.objects.none()
            assigned_ids = ServiceStaff.objects.filter(
                service_id=sid,
                service__provider=provider,
            ).values_list("staff_id", flat=True)
            qs = qs.filter(id__in=assigned_ids)

        return qs.order_by("name")
