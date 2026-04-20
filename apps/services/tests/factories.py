"""Factories para testes de services."""

import factory
from factory.django import DjangoModelFactory

from apps.providers.tests.factories import ProviderProfileFactory
from apps.services.models import Service


class ServiceFactory(DjangoModelFactory):
    """Factory para serviços de prestadores."""

    class Meta:
        model = Service

    provider = factory.SubFactory(ProviderProfileFactory)
    name = factory.Sequence(lambda n: f"Serviço {n}")
    description = "Descrição do serviço de teste."
    price = factory.Sequence(lambda n: f"{50 + n}.00")
    duration_minutes = 60
    is_active = True
