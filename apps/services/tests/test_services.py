"""
Testes BDD — Serviços do Prestador.

Feature: Gerenciamento de Serviços
  Como prestador de serviço autenticado
  Quero gerenciar meus serviços
  Para que clientes possam visualizar e agendar meus serviços
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient

from apps.providers.models import ProviderProfile
from apps.providers.tests.factories import ProviderProfileFactory
from apps.services.models import Service
from apps.services.tests.factories import ServiceFactory

LIST_CREATE_URL = "/api/v1/providers/me/services/"


def detail_url(pk: object) -> str:
    return f"/api/v1/providers/me/services/{pk}/"


# ── Fixtures locais ───────────────────────────────────────────────────────────


@pytest.fixture
def provider_profile(db: None) -> ProviderProfile:
    """ProviderProfile com usuário associado."""
    return ProviderProfileFactory()


@pytest.fixture
def authenticated_provider(provider_profile: ProviderProfile) -> APIClient:
    """APIClient autenticado como o prestador do provider_profile."""
    client = APIClient()
    client.force_authenticate(user=provider_profile.user)
    return client


@pytest.fixture
def other_provider_profile(db: None) -> ProviderProfile:
    """Segundo ProviderProfile para testes de isolamento."""
    return ProviderProfileFactory()


@pytest.fixture
def other_authenticated_provider(other_provider_profile: ProviderProfile) -> APIClient:
    client = APIClient()
    client.force_authenticate(user=other_provider_profile.user)
    return client


# ── Testes ────────────────────────────────────────────────────────────────────


@pytest.mark.django_db
class TestProviderServiceCreate:
    """
    Feature: Criação de serviços
    Como prestador autenticado
    Quero criar serviços
    Para que apareçam no meu perfil
    """

    def test_provider_creates_service_with_valid_data_returns_201(
        self,
        authenticated_provider: APIClient,
    ) -> None:
        """
        Scenario: Criação bem-sucedida
          Given um prestador autenticado
          When POST /providers/me/services/ com dados válidos
          Then resposta 201 com o serviço criado
          And o serviço está vinculado ao provider do usuário
        """
        payload = {
            "name": "Corte de cabelo",
            "description": "Corte masculino clássico.",
            "price": "45.00",
            "duration_minutes": 30,
            "is_active": True,
        }

        response = authenticated_provider.post(LIST_CREATE_URL, payload, format="json")

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Corte de cabelo"
        assert data["price"] == "45.00"
        assert data["duration_minutes"] == 30
        assert Service.objects.filter(name="Corte de cabelo").exists()

    def test_provider_creates_service_provider_is_set_automatically(
        self,
        authenticated_provider: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Provider injetado automaticamente
          Given um prestador autenticado
          When POST /providers/me/services/
          Then o campo provider do serviço criado é o do usuário autenticado
        """
        payload = {"name": "Barba", "price": "25.00", "duration_minutes": 20}

        authenticated_provider.post(LIST_CREATE_URL, payload, format="json")

        service = Service.objects.get(name="Barba")
        assert service.provider_id == provider_profile.pk


@pytest.mark.django_db
class TestProviderServiceList:
    """
    Feature: Listagem de serviços
    Como prestador autenticado
    Quero listar meus serviços
    Para ter visibilidade do que ofereço
    """

    def test_provider_lists_own_services(
        self,
        authenticated_provider: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Listagem paginada de serviços
          Given dois serviços ativos do prestador autenticado
          When GET /providers/me/services/
          Then resposta 200 com a lista dos dois serviços dentro de data[]
        """
        ServiceFactory.create_batch(2, provider=provider_profile)

        response = authenticated_provider.get(LIST_CREATE_URL)

        assert response.status_code == status.HTTP_200_OK
        # A paginação global emite { data: [...], meta: {...} }
        assert len(response.json()) == 2

    def test_provider_does_not_see_other_providers_services(
        self,
        authenticated_provider: APIClient,
        provider_profile: ProviderProfile,
        other_provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Isolamento de dados entre prestadores
          Given um serviço do prestador A e um serviço do prestador B
          When o prestador A lista seus serviços
          Then apenas o serviço do prestador A aparece
        """
        ServiceFactory(provider=provider_profile, name="Meu Serviço")
        ServiceFactory(provider=other_provider_profile, name="Serviço Alheio")

        response = authenticated_provider.get(LIST_CREATE_URL)

        assert response.status_code == status.HTTP_200_OK
        names = [s["name"] for s in response.json()]
        assert "Meu Serviço" in names
        assert "Serviço Alheio" not in names

    def test_inactive_services_not_shown_in_list(
        self,
        authenticated_provider: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Serviços inativos não aparecem na listagem
          Given um serviço ativo e um inativo do mesmo prestador
          When GET /providers/me/services/
          Then apenas o ativo aparece
        """
        ServiceFactory(provider=provider_profile, name="Ativo", is_active=True)
        ServiceFactory(provider=provider_profile, name="Inativo", is_active=False)

        response = authenticated_provider.get(LIST_CREATE_URL)

        names = [s["name"] for s in response.json()]
        assert "Ativo" in names
        assert "Inativo" not in names


@pytest.mark.django_db
class TestProviderServiceUpdate:
    """
    Feature: Atualização de serviços
    Como prestador autenticado
    Quero atualizar serviços existentes
    Para manter minha oferta atualizada
    """

    def test_provider_updates_service_with_patch(
        self,
        authenticated_provider: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: PATCH bem-sucedido
          Given um serviço do prestador autenticado
          When PATCH /providers/me/services/{id}/ com novo preço
          Then resposta 200 e preço atualizado no banco
        """
        service = ServiceFactory(provider=provider_profile, price="50.00")

        response = authenticated_provider.patch(
            detail_url(service.pk),
            {"price": "75.00"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        service.refresh_from_db()
        assert str(service.price) == "75.00"

    def test_other_provider_cannot_update_service_returns_404(
        self,
        other_authenticated_provider: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Outro prestador não consegue atualizar serviço alheio
          Given um serviço pertencente ao prestador A
          When o prestador B tenta PATCH no serviço
          Then resposta 404 (sem vazar informação de existência)
        """
        service = ServiceFactory(provider=provider_profile)

        response = other_authenticated_provider.patch(
            detail_url(service.pk),
            {"price": "999.00"},
            format="json",
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProviderServiceSoftDelete:
    """
    Feature: Remoção de serviços
    Como prestador autenticado
    Quero remover serviços
    Preservando o histórico de agendamentos anteriores
    """

    def test_provider_deletes_service_soft_delete(
        self,
        authenticated_provider: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Soft delete bem-sucedido
          Given um serviço ativo do prestador autenticado
          When DELETE /providers/me/services/{id}/
          Then resposta 204
          And o serviço permanece no banco com is_active=False
        """
        service = ServiceFactory(provider=provider_profile, is_active=True)

        response = authenticated_provider.delete(detail_url(service.pk))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        service.refresh_from_db()
        assert service.is_active is False
        assert service.deactivated_at is not None

    def test_deleted_service_remains_in_database(
        self,
        authenticated_provider: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Registro não é excluído fisicamente
          Given um serviço ativo
          When DELETE é chamado
          Then o registro ainda existe no banco de dados
        """
        service = ServiceFactory(provider=provider_profile)
        service_pk = service.pk

        authenticated_provider.delete(detail_url(service_pk))

        assert Service.objects.filter(pk=service_pk).exists()

    def test_other_provider_cannot_delete_service_returns_404(
        self,
        other_authenticated_provider: APIClient,
        provider_profile: ProviderProfile,
    ) -> None:
        """
        Scenario: Outro prestador não consegue deletar serviço alheio
          Given um serviço pertencente ao prestador A
          When o prestador B tenta DELETE
          Then resposta 404
        """
        service = ServiceFactory(provider=provider_profile)

        response = other_authenticated_provider.delete(detail_url(service.pk))

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProviderServiceSecurity:
    """
    Feature: Segurança dos endpoints de serviços
    Como sistema
    Quero garantir que apenas usuários autorizados acessem os serviços
    """

    def test_unauthenticated_list_returns_401(self) -> None:
        """
        Scenario: Não autenticado recebe 401 na listagem
          Given nenhuma autenticação
          When GET /providers/me/services/
          Then resposta 401
        """
        client = APIClient()
        response = client.get(LIST_CREATE_URL)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_create_returns_401(self) -> None:
        """
        Scenario: Não autenticado recebe 401 na criação
          Given nenhuma autenticação
          When POST /providers/me/services/
          Then resposta 401
        """
        client = APIClient()
        response = client.post(
            LIST_CREATE_URL,
            {"name": "Teste", "price": "10.00", "duration_minutes": 30},
            format="json",
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_detail_returns_401(
        self, db: None, provider_profile: ProviderProfile
    ) -> None:
        """
        Scenario: Não autenticado recebe 401 no detalhe
          Given nenhuma autenticação
          When GET /providers/me/services/{id}/
          Then resposta 401
        """
        service = ServiceFactory(provider=provider_profile)
        client = APIClient()
        response = client.get(detail_url(service.pk))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
