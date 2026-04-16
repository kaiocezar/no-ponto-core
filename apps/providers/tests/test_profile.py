"""
Testes BDD — Perfil de Prestador.

Feature: Gerenciamento de Perfil de Prestador
  Como prestador de serviço autenticado
  Quero gerenciar meu perfil na plataforma
  Para que clientes possam me encontrar e agendar serviços
"""

import pytest
from django.core.exceptions import ValidationError
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.providers.models import ProviderProfile
from apps.providers.tests.factories import ProviderProfileFactory
from apps.services.tests.factories import ServiceFactory

ME_URL = "/api/v1/providers/me/"
PUBLISH_URL = "/api/v1/providers/me/publish/"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
class TestProviderProfile:
    """
    BDD Feature: Gerenciamento de Perfil de Prestador

    Cenários cobertos:
    - Geração automática de slug a partir do nome do negócio
    - Sufixo numérico em colisão de slug
    - Slug reservado levanta ValidationError
    - Prestador autenticado acessa /me/
    - Usuário não autenticado não acessa /me/
    - Perfil publicado é acessível publicamente
    - Perfil não publicado retorna 404 no endpoint público
    - Outro usuário autenticado não vê perfil não publicado
    """

    def test_slug_generated_from_business_name(self, db: None) -> None:
        """
        Dado um prestador com business_name='Dr. João Silva'
        Quando o perfil é salvo sem slug
        Então o slug deve ser 'dr-joao-silva'
        """
        user = User.objects.create_user(
            email="joao@teste.com",
            password="senha_segura_123",
            role=User.Role.PROVIDER,
        )
        profile = ProviderProfile(user=user, business_name="Dr. João Silva")
        profile.save()

        assert profile.slug == "dr-joao-silva"

    def test_slug_collision_adds_numeric_suffix(self, db: None) -> None:
        """
        Dado dois prestadores com o mesmo business_name
        Quando ambos são salvos sem slug
        Então o segundo deve receber sufixo '-2'
        """
        user1 = User.objects.create_user(
            email="joao1@teste.com",
            password="senha_segura_123",
            role=User.Role.PROVIDER,
        )
        user2 = User.objects.create_user(
            email="joao2@teste.com",
            password="senha_segura_123",
            role=User.Role.PROVIDER,
        )

        profile1 = ProviderProfile(user=user1, business_name="Dr João")
        profile1.save()

        profile2 = ProviderProfile(user=user2, business_name="Dr João")
        profile2.save()

        assert profile1.slug == "dr-joao"
        assert profile2.slug == "dr-joao-2"

    def test_reserved_slug_raises_validation_error(self, db: None) -> None:
        """
        Dado um business_name que gera um slug reservado (ex: 'Admin')
        Quando tentamos gerar o slug
        Então deve levantar ValidationError
        """
        with pytest.raises(ValidationError):
            ProviderProfile.generate_unique_slug("Admin")

    def test_provider_can_view_own_profile(self, api_client: APIClient, db: None) -> None:
        """
        Dado um prestador autenticado
        Quando ele acessa GET /providers/me/
        Então deve receber 200 com seus dados de perfil
        """
        profile = ProviderProfileFactory()
        api_client.force_authenticate(user=profile.user)

        response = api_client.get(ME_URL)

        assert response.status_code == 200

    def test_unauthenticated_cannot_access_me(self, api_client: APIClient) -> None:
        """
        Dado um cliente sem autenticação
        Quando ele tenta acessar GET /providers/me/
        Então deve receber 401
        """
        response = api_client.get(ME_URL)

        assert response.status_code == 401

    def test_published_profile_accessible_publicly(self, api_client: APIClient, db: None) -> None:
        """
        Dado um perfil de prestador com is_published=True
        Quando qualquer usuário acessa GET /providers/<slug>/
        Então deve receber 200
        """
        profile = ProviderProfileFactory(is_published=True)

        response = api_client.get(f"/api/v1/providers/{profile.slug}/")

        assert response.status_code == 200

    def test_unpublished_profile_returns_404(self, api_client: APIClient, db: None) -> None:
        """
        Dado um perfil de prestador com is_published=False
        Quando qualquer usuário acessa GET /providers/<slug>/
        Então deve receber 404
        """
        profile = ProviderProfileFactory(is_published=False)

        response = api_client.get(f"/api/v1/providers/{profile.slug}/")

        assert response.status_code == 404

    def test_other_user_cannot_see_unpublished_profile(
        self, api_client: APIClient, db: None
    ) -> None:
        """
        Dado um perfil não publicado e um segundo usuário autenticado
        Quando o segundo usuário acessa o endpoint público do perfil
        Então deve receber 404 (o endpoint público só expõe perfis publicados)
        """
        profile = ProviderProfileFactory(is_published=False)

        outro_user = User.objects.create_user(
            email="outro@usuario.com",
            password="senha_segura_123",
            role=User.Role.CLIENT,
        )
        api_client.force_authenticate(user=outro_user)

        response = api_client.get(f"/api/v1/providers/{profile.slug}/")

        assert response.status_code == 404


@pytest.mark.django_db
class TestProviderPublishValidation:
    """
    BDD Feature: Validação de publicação do perfil

    Cenários cobertos:
    - Publicar sem endereço retorna 400 com detalhes dos campos
    - Publicar sem serviço ativo retorna 400
    - Publicar com endereço e serviço ativo retorna 200
    """

    def _make_complete_profile(self) -> ProviderProfile:
        """Cria um perfil com todos os campos de endereço preenchidos."""
        return ProviderProfileFactory(
            business_name="Barbearia do João",
            address_street="Rua das Flores, 100",
            address_city="São Paulo",
            address_state="SP",
            address_zip="01310-100",
        )

    def test_publish_without_address_returns_400(self, api_client: APIClient, db: None) -> None:
        """
        Scenario: Tentativa de publicar sem endereço
          Given um perfil sem campos de endereço preenchidos
          When POST /providers/me/publish/
          Then resposta 400 com code VALIDATION_ERROR
          And detalhes informando os campos de endereço ausentes
        """
        profile = ProviderProfileFactory(
            business_name="Negócio Sem Endereço",
            address_street="",
            address_city="",
            address_state="",
            address_zip="",
        )
        ServiceFactory(provider=profile, is_active=True)
        api_client.force_authenticate(user=profile.user)

        response = api_client.post(PUBLISH_URL)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "address_street" in error["details"]
        assert "address_city" in error["details"]
        assert "address_state" in error["details"]
        assert "address_zip" in error["details"]

    def test_publish_without_active_service_returns_400(
        self, api_client: APIClient, db: None
    ) -> None:
        """
        Scenario: Tentativa de publicar sem serviço ativo
          Given um perfil com endereço completo mas sem serviços ativos
          When POST /providers/me/publish/
          Then resposta 400 com code VALIDATION_ERROR
          And detalhe informando que pelo menos um serviço ativo é necessário
        """
        profile = self._make_complete_profile()
        # Cria serviço inativo — não deve contar para a validação
        ServiceFactory(provider=profile, is_active=False)
        api_client.force_authenticate(user=profile.user)

        response = api_client.post(PUBLISH_URL)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert "services" in error["details"]

    def test_publish_with_address_and_active_service_returns_200(
        self, api_client: APIClient, db: None
    ) -> None:
        """
        Scenario: Publicação bem-sucedida
          Given um perfil com business_name, endereço completo e ao menos um serviço ativo
          When POST /providers/me/publish/
          Then resposta 200
          And is_published do perfil é True
        """
        profile = self._make_complete_profile()
        ServiceFactory(provider=profile, is_active=True)
        api_client.force_authenticate(user=profile.user)

        response = api_client.post(PUBLISH_URL)

        assert response.status_code == status.HTTP_200_OK
        profile.refresh_from_db()
        assert profile.is_published is True

    def test_publish_without_business_name_returns_400(
        self, api_client: APIClient, db: None
    ) -> None:
        """
        Scenario: Tentativa de publicar sem business_name
          Given um perfil sem nome do negócio, mas com endereço e serviço
          When POST /providers/me/publish/
          Then resposta 400 informando o campo business_name ausente
        """
        profile = ProviderProfileFactory(
            business_name="",
            slug="slug-temporario",
            address_street="Rua A, 1",
            address_city="SP",
            address_state="SP",
            address_zip="01000-000",
        )
        ServiceFactory(provider=profile, is_active=True)
        api_client.force_authenticate(user=profile.user)

        response = api_client.post(PUBLISH_URL)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        error = response.json()["error"]
        assert "business_name" in error["details"]
