"""
Conftest raiz — re-exporta fixtures globais para todos os testes do projeto.

As fixtures estão definidas em tests/conftest.py mas precisam ser acessíveis
a partir de qualquer diretório de testes (apps/*/tests/).
"""

from tests.conftest import (  # noqa: F401
    api_client,
    authenticated_client_api,
    authenticated_provider_api,
    client_user,
    django_client,
    provider_user,
)
