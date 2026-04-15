"""
Testes BDD — Cadastro de Prestadores.

Feature: Registro de Prestador
  Como visitante da plataforma
  Quero me cadastrar como prestador de serviço
  Para que eu possa publicar meu perfil e receber agendamentos
"""

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.providers.models import ProviderProfile

REGISTER_URL = "/api/v1/accounts/register/"


@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture(autouse=True)
def use_locmem_cache(settings) -> None:  # type: ignore[no-untyped-def]
    """Usa cache em memória para throttle não acumular entre testes."""
    settings.CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }


@pytest.mark.django_db
class TestProviderRegistration:
    """
    BDD Feature: Registro de Prestador

    Cenários cobertos:
    - Registro bem-sucedido com dados válidos
    - Criação automática de ProviderProfile após registro
    - Rejeição de e-mail duplicado
    - Rejeição de payload sem e-mail
    - Rejeição de senha curta demais
    """

    def test_provider_can_register_with_valid_data(self, api_client: APIClient) -> None:
        """
        Dado um visitante com dados válidos
        Quando ele envia POST /accounts/register/
        Então deve receber 201 com tokens access e refresh
        """
        payload = {
            "email": "novo@prestador.com",
            "password": "senha_segura_123",
            "full_name": "Dr. Novo Prestador",
        }

        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == 201
        data = response.json()
        assert "tokens" in data
        assert "access" in data["tokens"]
        assert "refresh" in data["tokens"]
        assert data["tokens"]["access"]
        assert data["tokens"]["refresh"]

    def test_register_creates_provider_profile_automatically(self, api_client: APIClient) -> None:
        """
        Dado um visitante que se cadastra com sucesso
        Quando o registro é concluído
        Então um ProviderProfile deve ser criado automaticamente para o usuário
        """
        payload = {
            "email": "prestador.profile@teste.com",
            "password": "senha_segura_123",
            "full_name": "Maria Prestadora",
        }

        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == 201
        assert ProviderProfile.objects.filter(user__email="prestador.profile@teste.com").exists()

    def test_register_fails_with_duplicate_email(self, api_client: APIClient) -> None:
        """
        Dado um e-mail já cadastrado na plataforma
        Quando um segundo visitante tenta se cadastrar com o mesmo e-mail
        Então deve receber 400 com mensagem de erro
        """
        payload = {
            "email": "duplicado@prestador.com",
            "password": "senha_segura_123",
            "full_name": "Prestador Um",
        }
        api_client.post(REGISTER_URL, payload, format="json")

        payload_dois = {
            "email": "duplicado@prestador.com",
            "password": "outra_senha_123",
            "full_name": "Prestador Dois",
        }
        response = api_client.post(REGISTER_URL, payload_dois, format="json")

        assert response.status_code == 400

    def test_register_fails_without_email(self, api_client: APIClient) -> None:
        """
        Dado um payload sem o campo e-mail
        Quando o visitante tenta se cadastrar
        Então deve receber 400 com erro de validação
        """
        payload = {
            "password": "senha_segura_123",
            "full_name": "Sem Email",
        }

        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == 400

    def test_register_fails_with_short_password(self, api_client: APIClient) -> None:
        """
        Dado um payload com senha menor que 8 caracteres
        Quando o visitante tenta se cadastrar
        Então deve receber 400 com erro de validação de senha
        """
        payload = {
            "email": "curto@senha.com",
            "password": "1234567",  # 7 chars — abaixo do mínimo
            "full_name": "Senha Curta",
        }

        response = api_client.post(REGISTER_URL, payload, format="json")

        assert response.status_code == 400
