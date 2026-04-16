"""
Configuração global de testes com pytest-django.

Fixtures compartilhadas entre todos os testes.
"""

import pytest
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.models import User

# ── Factories (usando factory_boy) ────────────────────────────────────────────
# Importar apenas quando os modelos estiverem implementados nas tasks

# ── Fixtures de usuário ───────────────────────────────────────────────────────


@pytest.fixture
def api_client() -> APIClient:
    """Cliente de API sem autenticação."""
    return APIClient()


@pytest.fixture
def django_client() -> Client:
    """Cliente Django padrão."""
    return Client()


@pytest.fixture
def client_user(db: None) -> User:
    """Usuário com papel de cliente."""
    return User.objects.create_user(
        phone_number="+5511999999001",
        full_name="Cliente Teste",
        role=User.Role.CLIENT,
    )


@pytest.fixture
def provider_user(db: None) -> User:
    """Usuário com papel de prestador."""
    return User.objects.create_user(
        email="prestador@teste.com",
        password="senha_segura_123",
        full_name="Prestador Teste",
        role=User.Role.PROVIDER,
    )


@pytest.fixture
def authenticated_client_api(api_client: APIClient, client_user: User) -> APIClient:
    """Cliente de API autenticado como cliente."""
    api_client.force_authenticate(user=client_user)
    return api_client


@pytest.fixture
def authenticated_provider_api(api_client: APIClient, provider_user: User) -> APIClient:
    """Cliente de API autenticado como prestador."""
    api_client.force_authenticate(user=provider_user)
    return api_client
