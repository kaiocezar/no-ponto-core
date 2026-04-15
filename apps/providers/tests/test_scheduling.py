"""
Tests de horários de funcionamento e bloqueios de agenda.

Feature: Gerenciamento de disponibilidade do prestador
"""

from __future__ import annotations

import datetime
import zoneinfo

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.providers.models import ProviderProfile, ScheduleBlock, WorkingHours
from apps.providers.tests.factories import (
    ProviderProfileFactory,
    ScheduleBlockFactory,
    WorkingHoursFactory,
)

BRT = zoneinfo.ZoneInfo("America/Sao_Paulo")
UTC = datetime.timezone.utc


@pytest.fixture
def provider_profile(provider_user: User) -> ProviderProfile:
    """Perfil do prestador já criado."""
    profile, _ = ProviderProfile.objects.get_or_create(
        user=provider_user,
        defaults={"business_name": "Clínica Teste", "slug": "clinica-teste"},
    )
    return profile


# ── Testes de WorkingHours ────────────────────────────────────────────────────


class TestWorkingHoursAPI:
    """
    Feature: Configuração de horários de funcionamento
    Como prestador
    Quero configurar os horários de atendimento por dia da semana
    Para que os clientes saibam quando posso receber agendamentos
    """

    @pytest.mark.django_db
    def test_provider_can_list_working_hours(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Listagem de horários configurados
          Given um prestador com horários configurados
          When ele faz GET /providers/me/working-hours/
          Then recebe lista com os horários
        """
        WorkingHoursFactory.create(provider=provider_profile, weekday=0)
        WorkingHoursFactory.create(provider=provider_profile, weekday=1)

        response = authenticated_provider_api.get("/api/v1/providers/me/working-hours/")

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    @pytest.mark.django_db
    def test_provider_can_create_working_hours(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Criação de horário para um dia
          Given um prestador autenticado
          When ele faz POST /providers/me/working-hours/ com dados válidos
          Then o horário é criado com status 201
        """
        payload = {
            "weekday": 0,
            "start_time": "08:00:00",
            "end_time": "18:00:00",
            "is_active": True,
        }

        response = authenticated_provider_api.post(
            "/api/v1/providers/me/working-hours/", data=payload
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["weekday"] == 0
        assert WorkingHours.objects.filter(provider=provider_profile, weekday=0).exists()

    @pytest.mark.django_db
    def test_working_hours_validation_start_before_end(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Validação de horário inválido (início após término)
          Given um prestador autenticado
          When ele envia start_time posterior ao end_time
          Then recebe 400 com mensagem de erro
        """
        payload = {
            "weekday": 0,
            "start_time": "18:00:00",
            "end_time": "08:00:00",
            "is_active": True,
        }

        response = authenticated_provider_api.post(
            "/api/v1/providers/me/working-hours/", data=payload
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_provider_can_bulk_replace_working_hours(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Substituição bulk de todos os horários
          Given horários pré-existentes
          When o prestador faz POST /bulk/ com nova grade
          Then os horários antigos são removidos e os novos criados
        """
        WorkingHoursFactory.create(provider=provider_profile, weekday=0)
        WorkingHoursFactory.create(provider=provider_profile, weekday=1)

        payload = {
            "working_hours": [
                {"weekday": 0, "start_time": "09:00:00", "end_time": "17:00:00", "is_active": True},
                {"weekday": 5, "start_time": "09:00:00", "end_time": "12:00:00", "is_active": True},
            ]
        }

        response = authenticated_provider_api.post(
            "/api/v1/providers/me/working-hours/bulk/", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert len(response.data) == 2
        # O horário de weekday=1 deve ter sido removido
        assert not WorkingHours.objects.filter(provider=provider_profile, weekday=1).exists()
        assert WorkingHours.objects.filter(provider=provider_profile, weekday=5).exists()

    @pytest.mark.django_db
    def test_bulk_rejects_duplicate_weekdays(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Validação de dias duplicados no bulk
          Given payload com dois horários para o mesmo dia
          When o prestador faz POST /bulk/
          Then recebe 400 com erro de validação
        """
        payload = {
            "working_hours": [
                {"weekday": 0, "start_time": "08:00:00", "end_time": "12:00:00", "is_active": True},
                {"weekday": 0, "start_time": "13:00:00", "end_time": "18:00:00", "is_active": True},
            ]
        }

        response = authenticated_provider_api.post(
            "/api/v1/providers/me/working-hours/bulk/", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_provider_can_delete_working_hours(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Remoção de horário de funcionamento
          Given um horário existente
          When o prestador faz DELETE
          Then o horário é removido com status 204
        """
        working_hours = WorkingHoursFactory.create(provider=provider_profile, weekday=3)

        response = authenticated_provider_api.delete(
            f"/api/v1/providers/me/working-hours/{working_hours.pk}/"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not WorkingHours.objects.filter(pk=working_hours.pk).exists()

    @pytest.mark.django_db
    def test_unauthenticated_returns_401(self, api_client: APIClient) -> None:
        """
        Scenario: Acesso não autenticado
          Given um cliente sem token
          When tenta acessar /providers/me/working-hours/
          Then recebe 401
        """
        response = api_client.get("/api/v1/providers/me/working-hours/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    @pytest.mark.django_db
    def test_provider_cannot_access_other_providers_hours(
        self,
        authenticated_provider_api: APIClient,
    ) -> None:
        """
        Scenario: Isolamento de dados entre prestadores
          Given horário pertencente a outro prestador
          When o prestador tenta DELETE neste horário
          Then recebe 403 ou 404 (não expõe dados de outros prestadores)
        """
        other_profile = ProviderProfileFactory.create()
        other_hours = WorkingHoursFactory.create(provider=other_profile, weekday=0)

        response = authenticated_provider_api.delete(
            f"/api/v1/providers/me/working-hours/{other_hours.pk}/"
        )

        # A permission class retorna 403 antes de resolver o objeto — ambos são seguros
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)


# ── Testes de ScheduleBlock ───────────────────────────────────────────────────


class TestScheduleBlockAPI:
    """
    Feature: Bloqueios de agenda
    Como prestador
    Quero criar bloqueios de agenda
    Para impedir agendamentos em períodos de férias, feriados ou reuniões
    """

    @pytest.mark.django_db
    def test_provider_can_create_schedule_block(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Criação de bloqueio simples
          Given um prestador autenticado
          When faz POST /providers/me/blocks/ com datas válidas
          Then o bloqueio é criado com status 201
        """
        payload = {
            "start_datetime": "2026-07-01T09:00:00Z",
            "end_datetime": "2026-07-05T18:00:00Z",
            "reason": "Férias",
            "is_recurring": False,
        }

        response = authenticated_provider_api.post(
            "/api/v1/providers/me/blocks/", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["reason"] == "Férias"
        assert ScheduleBlock.objects.filter(provider=provider_profile).count() == 1

    @pytest.mark.django_db
    def test_provider_can_create_recurring_block(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Criação de bloqueio recorrente com RRULE
          Given um prestador autenticado
          When faz POST com is_recurring=True e recurrence_rule válida
          Then o bloqueio recorrente é criado
        """
        payload = {
            "start_datetime": "2026-01-02T12:00:00Z",
            "end_datetime": "2026-01-02T14:00:00Z",
            "reason": "Almoço toda sexta",
            "is_recurring": True,
            "recurrence_rule": "FREQ=WEEKLY;BYDAY=FR",
        }

        response = authenticated_provider_api.post(
            "/api/v1/providers/me/blocks/", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["is_recurring"] is True
        assert response.data["recurrence_rule"] == "FREQ=WEEKLY;BYDAY=FR"

    @pytest.mark.django_db
    def test_recurring_block_requires_rrule(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Bloqueio recorrente sem RRULE deve falhar
          Given is_recurring=True mas sem recurrence_rule
          When faz POST
          Then recebe 400
        """
        payload = {
            "start_datetime": "2026-07-01T09:00:00Z",
            "end_datetime": "2026-07-01T18:00:00Z",
            "is_recurring": True,
            "recurrence_rule": "",
        }

        response = authenticated_provider_api.post(
            "/api/v1/providers/me/blocks/", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_block_end_must_be_after_start(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Validação de datas inválidas
          Given end_datetime anterior a start_datetime
          When faz POST
          Then recebe 400
        """
        payload = {
            "start_datetime": "2026-07-05T18:00:00Z",
            "end_datetime": "2026-07-01T09:00:00Z",
        }

        response = authenticated_provider_api.post(
            "/api/v1/providers/me/blocks/", data=payload, format="json"
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @pytest.mark.django_db
    def test_provider_can_list_blocks_with_date_filter(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Listagem de bloqueios com filtro de data
          Given múltiplos bloqueios em datas diferentes
          When filtra por intervalo de datas
          Then retorna apenas os bloqueios dentro do intervalo
        """
        ScheduleBlockFactory.create(
            provider=provider_profile,
            start_datetime=datetime.datetime(2026, 6, 1, tzinfo=UTC),
            end_datetime=datetime.datetime(2026, 6, 3, tzinfo=UTC),
        )
        ScheduleBlockFactory.create(
            provider=provider_profile,
            start_datetime=datetime.datetime(2026, 12, 20, tzinfo=UTC),
            end_datetime=datetime.datetime(2026, 12, 31, tzinfo=UTC),
        )

        response = authenticated_provider_api.get(
            "/api/v1/providers/me/blocks/?start=2026-06-01T00:00:00Z&end=2026-06-30T23:59:59Z"
        )

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    @pytest.mark.django_db
    def test_provider_can_delete_schedule_block(
        self,
        authenticated_provider_api: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Remoção de bloqueio
          Given um bloqueio existente
          When o prestador faz DELETE
          Then o bloqueio é removido com 204
        """
        block = ScheduleBlockFactory.create(provider=provider_profile)

        response = authenticated_provider_api.delete(
            f"/api/v1/providers/me/blocks/{block.pk}/"
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not ScheduleBlock.objects.filter(pk=block.pk).exists()


# ── Testes de lógica de disponibilidade ──────────────────────────────────────


class TestAvailabilityLogic:
    """
    Feature: Cálculo de slots disponíveis
    Como sistema
    Quero calcular corretamente os horários disponíveis
    Para que clientes vejam apenas slots realmente livres
    """

    @pytest.mark.django_db
    def test_get_available_slots_respects_working_hours(self) -> None:
        """
        Scenario: Slots dentro do horário de funcionamento
          Given prestador que atende 08h-10h (BRT), duração 60min
          When calcula slots para uma segunda-feira
          Then retorna exatamente 08:00 e 09:00 BRT
        """
        from freezegun import freeze_time

        from core.utils.availability import get_available_slots

        profile = ProviderProfileFactory.create(
            timezone="America/Sao_Paulo",
            min_notice_hours=0,
            max_advance_days=365,
        )
        WorkingHoursFactory.create(
            provider=profile,
            weekday=0,  # Segunda
            start_time=datetime.time(8, 0),
            end_time=datetime.time(10, 0),
            is_active=True,
        )

        date = datetime.date(2026, 4, 27)  # Segunda-feira

        with freeze_time("2026-04-27 00:00:00"):
            slots = get_available_slots(
                provider=profile,
                service_duration=60,
                buffer_after=0,
                date=date,
            )

        assert len(slots) == 2
        hours = [s.astimezone(BRT).hour for s in slots]
        assert 8 in hours
        assert 9 in hours

    @pytest.mark.django_db
    def test_slots_excluded_when_no_working_hours(self) -> None:
        """
        Scenario: Prestador sem horário configurado para o dia
          Given prestador sem WorkingHours para domingo
          When calcula slots para um domingo
          Then retorna lista vazia
        """
        from core.utils.availability import get_available_slots

        profile = ProviderProfileFactory.create(min_notice_hours=0, max_advance_days=365)

        date = datetime.date(2026, 4, 26)  # Domingo

        slots = get_available_slots(
            provider=profile,
            service_duration=60,
            buffer_after=0,
            date=date,
        )

        assert slots == []

    @pytest.mark.django_db
    def test_slots_blocked_by_schedule_block(self) -> None:
        """
        Scenario: Slot removido por bloqueio de agenda
          Given prestador que atende 08h-12h BRT com slots de 60min
          And bloqueio das 09h às 11h BRT (12h-14h UTC)
          When calcula slots
          Then apenas 08:00 e 11:00 BRT disponíveis; 09:00 e 10:00 BRT bloqueados
        """
        from freezegun import freeze_time

        from core.utils.availability import get_available_slots

        profile = ProviderProfileFactory.create(
            timezone="America/Sao_Paulo",
            min_notice_hours=0,
            max_advance_days=365,
        )
        WorkingHoursFactory.create(
            provider=profile,
            weekday=0,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(12, 0),
            is_active=True,
        )
        # Bloqueio 09:00-11:00 BRT = 12:00-14:00 UTC
        ScheduleBlockFactory.create(
            provider=profile,
            start_datetime=datetime.datetime(2026, 4, 27, 12, 0, tzinfo=UTC),  # 09:00 BRT
            end_datetime=datetime.datetime(2026, 4, 27, 14, 0, tzinfo=UTC),    # 11:00 BRT
            is_recurring=False,
        )

        date = datetime.date(2026, 4, 27)  # Segunda-feira

        with freeze_time("2026-04-27 00:00:00"):
            slots = get_available_slots(
                provider=profile,
                service_duration=60,
                buffer_after=0,
                date=date,
            )

        slot_hours_brt = [s.astimezone(BRT).hour for s in slots]
        assert 9 not in slot_hours_brt   # Bloqueado: 09:00 BRT
        assert 10 not in slot_hours_brt  # Bloqueado: 10:00 BRT
        assert 8 in slot_hours_brt       # Disponível: 08:00 BRT
        assert 11 in slot_hours_brt      # Disponível: 11:00 BRT

    @pytest.mark.django_db
    def test_slots_before_min_notice_removed(self) -> None:
        """
        Scenario: Remoção de slots dentro do notice mínimo
          Given prestador com min_notice_hours=2
          When calcula slots para hoje às 10:00 UTC
          Then slots antes das 12:00 UTC estão indisponíveis
        """
        from freezegun import freeze_time

        from core.utils.availability import get_available_slots

        profile = ProviderProfileFactory.create(
            timezone="America/Sao_Paulo",
            min_notice_hours=2,
            max_advance_days=365,
        )
        WorkingHoursFactory.create(
            provider=profile,
            weekday=0,
            start_time=datetime.time(8, 0),
            end_time=datetime.time(18, 0),
            is_active=True,
        )

        date = datetime.date(2026, 4, 27)  # Segunda-feira

        # 10:00 UTC = 07:00 BRT, cutoff = 12:00 UTC = 09:00 BRT
        # Slot das 08:00 BRT = 11:00 UTC < cutoff 12:00 UTC → deve ser excluído
        with freeze_time("2026-04-27 10:00:00"):
            slots = get_available_slots(
                provider=profile,
                service_duration=60,
                buffer_after=0,
                date=date,
            )

        slot_hours_brt = [s.astimezone(BRT).hour for s in slots]
        # 08:00 BRT deve estar excluído (dentro do min_notice de 2h)
        assert 8 not in slot_hours_brt
