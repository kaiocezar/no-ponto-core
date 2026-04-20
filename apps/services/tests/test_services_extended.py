"""
Testes BDD expandidos — Serviços: campos novos, activate/deactivate, delete físico,
ServiceStaff, endpoints públicos.
"""

from __future__ import annotations

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.providers.models import ServiceStaff
from apps.providers.tests.factories import ProviderProfileFactory, StaffFactory
from apps.services.models import Service
from apps.services.tests.factories import ServiceFactory

LIST_CREATE_URL = "/api/v1/providers/me/services/"


def detail_url(pk: object) -> str:
    return f"/api/v1/providers/me/services/{pk}/"


def activate_url(pk: object) -> str:
    return f"/api/v1/providers/me/services/{pk}/activate/"


def deactivate_url(pk: object) -> str:
    return f"/api/v1/providers/me/services/{pk}/deactivate/"


@pytest.fixture
def provider_profile(db):
    return ProviderProfileFactory()


@pytest.fixture
def authenticated_provider(provider_profile):
    client = APIClient()
    client.force_authenticate(user=provider_profile.user)
    return client


# ── Campos novos ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestServiceNewFields:
    """
    Feature: Campos novos no serviço
    Como prestador
    Quero informar cor, moeda, depósito e capacidade
    Para exibir serviços completos no painel
    """

    def test_creates_service_with_all_new_fields(
        self, authenticated_provider: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: Criar serviço com campos completos
          Given um prestador autenticado
          When POST com todos os campos novos
          Then 201 e campos persistidos corretamente
        """
        payload = {
            "name": "Consulta",
            "price": None,
            "duration_minutes": 45,
            "color": "#FF5733",
            "currency": "BRL",
            "requires_deposit": True,
            "deposit_amount": "50.00",
            "max_clients": 1,
        }
        resp = authenticated_provider.post(LIST_CREATE_URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        data = resp.json()
        assert data["color"] == "#FF5733"
        assert data["requires_deposit"] is True
        assert data["deposit_amount"] == "50.00"
        assert data["price"] is None

    def test_requires_deposit_without_amount_returns_400(
        self, authenticated_provider: APIClient
    ) -> None:
        """
        Scenario: requires_deposit=true sem deposit_amount
          When POST com requires_deposit=true e sem deposit_amount
          Then 400 com erro em deposit_amount
        """
        payload = {
            "name": "Serviço X",
            "duration_minutes": 30,
            "requires_deposit": True,
        }
        resp = authenticated_provider.post(LIST_CREATE_URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_duration_minutes_zero_returns_400(self, authenticated_provider: APIClient) -> None:
        """
        Scenario: duration_minutes=0
          When POST com duration_minutes=0
          Then 400
        """
        payload = {"name": "X", "duration_minutes": 0}
        resp = authenticated_provider.post(LIST_CREATE_URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST

    def test_list_returns_active_and_inactive_services(
        self, authenticated_provider: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: Listagem inclui inativos
          Given um serviço ativo e um inativo
          When GET /providers/me/services/
          Then ambos aparecem na resposta
        """
        ServiceFactory(provider=provider_profile, name="Ativo", is_active=True)
        ServiceFactory(provider=provider_profile, name="Inativo", is_active=False)
        resp = authenticated_provider.get(LIST_CREATE_URL)
        assert resp.status_code == status.HTTP_200_OK
        names = [s["name"] for s in resp.json()]
        assert "Ativo" in names
        assert "Inativo" in names


# ── Activate / Deactivate ─────────────────────────────────────────────────────


@pytest.mark.django_db
class TestServiceActivateDeactivate:
    """
    Feature: Ativar e desativar serviços
    Como prestador
    Quero controlar o status dos meus serviços
    Para gerenciar o que é exibido no painel
    """

    def test_deactivate_sets_is_active_false(
        self, authenticated_provider: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: Desativar serviço
          Given um serviço ativo
          When POST /deactivate/
          Then 200 e is_active=False
        """
        service = ServiceFactory(provider=provider_profile, is_active=True)
        resp = authenticated_provider.post(deactivate_url(service.pk))
        assert resp.status_code == status.HTTP_200_OK
        service.refresh_from_db()
        assert service.is_active is False

    def test_activate_sets_is_active_true(
        self, authenticated_provider: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: Reativar serviço desativado
          Given um serviço inativo
          When POST /activate/
          Then 200 e is_active=True
        """
        service = ServiceFactory(provider=provider_profile, is_active=False)
        resp = authenticated_provider.post(activate_url(service.pk))
        assert resp.status_code == status.HTTP_200_OK
        service.refresh_from_db()
        assert service.is_active is True


# ── DELETE físico ─────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestServicePhysicalDelete:
    """
    Feature: Exclusão física de serviços sem agendamentos
    Como prestador
    Quero excluir serviços que nunca foram usados
    Para manter a lista limpa
    """

    def test_delete_service_without_appointments_physically_removes(
        self, authenticated_provider: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: DELETE sem agendamentos
          Given um serviço sem agendamentos
          When DELETE /providers/me/services/{id}/
          Then 204 e registro removido do banco
        """
        service = ServiceFactory(provider=provider_profile)
        pk = service.pk
        resp = authenticated_provider.delete(detail_url(pk))
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        assert not Service.objects.filter(pk=pk).exists()

    def test_delete_service_with_appointments_returns_400(
        self, authenticated_provider: APIClient, provider_profile: object, db: None
    ) -> None:
        """
        Scenario: DELETE com agendamentos existentes
          Given um serviço com agendamentos
          When DELETE
          Then 400 com code SERVICE_HAS_APPOINTMENTS
        """
        from apps.accounts.models import User
        from apps.appointments.models import Appointment, generate_public_id

        service = ServiceFactory(provider=provider_profile)
        User.objects.create_user(
            email="cliente@test.com",
            phone_number="+5511999990001",
            role=User.Role.CLIENT,
        )
        Appointment.objects.create(
            public_id=generate_public_id(),
            provider=provider_profile,
            service=service,
            staff=None,
            client=None,
            client_name="Cliente Teste",
            client_phone="+5511999990001",
            client_email="",
            start_datetime="2030-01-01T10:00:00+00:00",
            end_datetime="2030-01-01T11:00:00+00:00",
            status=Appointment.Status.CONFIRMED,
            origin=Appointment.Origin.ONLINE,
        )
        resp = authenticated_provider.delete(detail_url(service.pk))
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.json()["code"] == "SERVICE_HAS_APPOINTMENTS"


# ── ServiceStaff ──────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestServiceStaff:
    """
    Feature: Vinculação de staff a serviços
    Como prestador
    Quero associar profissionais a serviços
    Para controlar quem pode realizar cada serviço
    """

    def test_creates_service_with_staff_ids(
        self, authenticated_provider: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: Criar serviço com staff_ids
          Given dois staff ativos do provider
          When POST com staff_ids
          Then serviço criado com os dois staff vinculados
        """
        staff1 = StaffFactory(provider=provider_profile)
        staff2 = StaffFactory(provider=provider_profile)
        payload = {
            "name": "Serviço com staff",
            "duration_minutes": 30,
            "staff_ids": [str(staff1.pk), str(staff2.pk)],
        }
        resp = authenticated_provider.post(LIST_CREATE_URL, payload, format="json")
        assert resp.status_code == status.HTTP_201_CREATED
        service = Service.objects.get(name="Serviço com staff")
        assert service.staff_members.count() == 2

    def test_patch_replaces_staff_ids(
        self, authenticated_provider: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: PATCH substitui lista de staff
          Given um serviço com staff1 vinculado
          When PATCH com staff_ids=[staff2]
          Then apenas staff2 fica vinculado
        """
        staff1 = StaffFactory(provider=provider_profile)
        staff2 = StaffFactory(provider=provider_profile)
        service = ServiceFactory(provider=provider_profile)
        ServiceStaff.objects.create(service=service, staff=staff1)

        resp = authenticated_provider.patch(
            detail_url(service.pk),
            {"staff_ids": [str(staff2.pk)]},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        service.refresh_from_db()
        ids = list(service.staff_members.values_list("id", flat=True))
        assert staff2.pk in ids
        assert staff1.pk not in ids

    def test_invalid_staff_id_returns_400(
        self, authenticated_provider: APIClient, provider_profile: object
    ) -> None:
        """
        Scenario: staff_id inválido
          When POST com staff_id de outro provider
          Then 400
        """
        other = ProviderProfileFactory()
        foreign_staff = StaffFactory(provider=other)
        payload = {
            "name": "Serviço inválido",
            "duration_minutes": 30,
            "staff_ids": [str(foreign_staff.pk)],
        }
        resp = authenticated_provider.post(LIST_CREATE_URL, payload, format="json")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST


# ── Endpoint público ──────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestPublicProviderServices:
    """
    Feature: Endpoint público de serviços
    Como visitante
    Quero ver serviços ativos de um provider
    Para escolher o que agendar
    """

    def test_public_services_returns_only_active_online(self, db: None) -> None:
        """
        Scenario: Filtro is_active+is_online
          Given provider publicado com 3 serviços (ativo/online, ativo/offline, inativo)
          When GET /{slug}/services/
          Then retorna apenas o ativo+online
        """
        provider = ProviderProfileFactory(is_published=True)
        ServiceFactory(provider=provider, name="Visível", is_active=True, is_online=True)
        ServiceFactory(provider=provider, name="Offline", is_active=True, is_online=False)
        ServiceFactory(provider=provider, name="Inativo", is_active=False, is_online=True)

        resp = APIClient().get(f"/api/v1/providers/{provider.slug}/services/")
        assert resp.status_code == status.HTTP_200_OK
        names = [s["name"] for s in resp.json()]
        assert "Visível" in names
        assert "Offline" not in names
        assert "Inativo" not in names

    def test_public_services_unpublished_provider_returns_empty(self, db: None) -> None:
        """
        Scenario: Provider não publicado retorna lista vazia
          Given provider não publicado com serviços ativos
          When GET /{slug}/services/
          Then retorna 200 com lista vazia
        """
        provider = ProviderProfileFactory(is_published=False)
        ServiceFactory(provider=provider, is_active=True, is_online=True)

        resp = APIClient().get(f"/api/v1/providers/{provider.slug}/services/")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.json() == []

    def test_public_services_no_auth_required(self, db: None) -> None:
        """
        Scenario: Sem autenticação retorna 200
        """
        provider = ProviderProfileFactory(is_published=True)
        ServiceFactory(provider=provider, is_active=True, is_online=True)
        resp = APIClient().get(f"/api/v1/providers/{provider.slug}/services/")
        assert resp.status_code == status.HTTP_200_OK
