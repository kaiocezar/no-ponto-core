"""Views de gerenciamento de horários e bloqueios de agenda."""

from __future__ import annotations

import datetime

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.providers.models import ProviderProfile, ScheduleBlock, WorkingHours
from apps.providers.serializers import (
    ScheduleBlockSerializer,
    WorkingHoursBulkSerializer,
    WorkingHoursSerializer,
)
from core.permissions import IsProviderOwner


class WorkingHoursListCreateView(APIView):
    """
    GET  /api/v1/providers/me/working-hours/  — lista horários do prestador
    POST /api/v1/providers/me/working-hours/  — cria horário para um dia
    """

    permission_classes = [IsAuthenticated, IsProviderOwner]

    def _get_provider(self, request: Request) -> ProviderProfile:
        profile, _ = ProviderProfile.objects.get_or_create(user=request.user)
        return profile

    def get(self, request: Request) -> Response:
        provider = self._get_provider(request)
        qs = WorkingHours.objects.filter(provider=provider, staff__isnull=True).order_by("weekday")
        serializer = WorkingHoursSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request: Request) -> Response:
        provider = self._get_provider(request)
        serializer = WorkingHoursSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(provider=provider)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class WorkingHoursDetailView(APIView):
    """
    PUT    /api/v1/providers/me/working-hours/{id}/  — atualiza horário
    DELETE /api/v1/providers/me/working-hours/{id}/  — remove horário
    """

    permission_classes = [IsAuthenticated, IsProviderOwner]

    def _get_object(self, request: Request, pk: str) -> WorkingHours:
        profile, _ = ProviderProfile.objects.get_or_create(user=request.user)
        return get_object_or_404(WorkingHours, pk=pk, provider=profile)

    def put(self, request: Request, pk: str) -> Response:
        working_hours = self._get_object(request, pk)
        serializer = WorkingHoursSerializer(working_hours, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request: Request, pk: str) -> Response:
        working_hours = self._get_object(request, pk)
        working_hours.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class WorkingHoursBulkView(APIView):
    """
    POST /api/v1/providers/me/working-hours/bulk/

    Cria/substitui todos os horários de uma vez.
    Remove horários existentes e cria os novos em transação atômica.
    """

    permission_classes = [IsAuthenticated, IsProviderOwner]

    def post(self, request: Request) -> Response:
        from django.db import transaction

        serializer = WorkingHoursBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile, _ = ProviderProfile.objects.get_or_create(user=request.user)

        with transaction.atomic():
            # Remove horários existentes do estabelecimento (não de profissionais)
            WorkingHours.objects.filter(provider=profile, staff__isnull=True).delete()

            # Cria os novos
            new_hours = [
                WorkingHours(provider=profile, **item)
                for item in serializer.validated_data["working_hours"]
            ]
            created = WorkingHours.objects.bulk_create(new_hours)

        result_serializer = WorkingHoursSerializer(created, many=True)
        return Response(result_serializer.data, status=status.HTTP_201_CREATED)


class ScheduleBlockListCreateView(APIView):
    """
    GET  /api/v1/providers/me/blocks/  — lista bloqueios
    POST /api/v1/providers/me/blocks/  — cria bloqueio
    """

    permission_classes = [IsAuthenticated, IsProviderOwner]

    def _get_provider(self, request: Request) -> ProviderProfile:
        profile, _ = ProviderProfile.objects.get_or_create(user=request.user)
        return profile

    def get(self, request: Request) -> Response:
        provider = self._get_provider(request)
        qs = ScheduleBlock.objects.filter(provider=provider).order_by("start_datetime")

        # Filtro por data (opcional)
        start_param = request.query_params.get("start")
        end_param = request.query_params.get("end")
        if start_param:
            qs = qs.filter(end_datetime__gte=start_param)
        if end_param:
            qs = qs.filter(start_datetime__lte=end_param)

        serializer = ScheduleBlockSerializer(qs, many=True)
        return Response(serializer.data)

    def post(self, request: Request) -> Response:
        provider = self._get_provider(request)
        serializer = ScheduleBlockSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(provider=provider)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class ScheduleBlockDetailView(APIView):
    """
    PUT    /api/v1/providers/me/blocks/{id}/  — atualiza bloqueio
    DELETE /api/v1/providers/me/blocks/{id}/  — remove bloqueio
    """

    permission_classes = [IsAuthenticated, IsProviderOwner]

    def _get_object(self, request: Request, pk: str) -> ScheduleBlock:
        profile, _ = ProviderProfile.objects.get_or_create(user=request.user)
        return get_object_or_404(ScheduleBlock, pk=pk, provider=profile)

    def put(self, request: Request, pk: str) -> Response:
        block = self._get_object(request, pk)
        serializer = ScheduleBlockSerializer(block, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def delete(self, request: Request, pk: str) -> Response:
        block = self._get_object(request, pk)
        block.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProviderAvailabilityView(APIView):
    """
    GET /api/v1/providers/{slug}/availability/
    ?service_id={uuid}&date={YYYY-MM-DD}&staff_id={uuid}

    Retorna lista de slots disponíveis para o dia/serviço/profissional.
    Endpoint público — não requer autenticação.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, slug: str) -> Response:
        provider = get_object_or_404(ProviderProfile, slug=slug, is_published=True)

        service_id = request.query_params.get("service_id")
        date_str = request.query_params.get("date")
        staff_id = request.query_params.get("staff_id")

        if not service_id or not date_str:
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "service_id e date são obrigatórios.",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return Response(
                {
                    "error": {
                        "code": "VALIDATION_ERROR",
                        "message": "Formato de data inválido. Use YYYY-MM-DD.",
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Obter serviço para pegar duração e buffer
        try:
            from apps.services.models import Service

            service = Service.objects.get(pk=service_id, provider=provider, is_active=True)
            service_duration = service.duration
            buffer_after = service.buffer_after
        except Exception:
            return Response(
                {"error": {"code": "NOT_FOUND", "message": "Serviço não encontrado."}},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Resolver staff se fornecido
        staff = None
        if staff_id:
            import contextlib

            from apps.accounts.models import User

            with contextlib.suppress(User.DoesNotExist):
                staff = User.objects.get(pk=staff_id)

        from core.utils.availability import get_available_slots

        slots = get_available_slots(
            provider=provider,
            service_duration=service_duration,
            buffer_after=buffer_after,
            date=date,
            staff=staff,
        )

        # Serializar como lista de {start, end, staff_id}
        duration = datetime.timedelta(minutes=service_duration)
        result = [
            {
                "start": slot.isoformat(),
                "end": (slot + duration).isoformat(),
                "staff_id": str(staff.pk) if staff else None,
            }
            for slot in slots
        ]

        return Response(result)
