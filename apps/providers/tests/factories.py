"""Factories para testes de providers."""

import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import ProviderUserFactory
from apps.providers.models import ProviderProfile, ServiceCategory


class ServiceCategoryFactory(DjangoModelFactory):
    """Factory para categorias de serviço."""

    class Meta:
        model = ServiceCategory

    name = factory.Sequence(lambda n: f"Categoria {n}")
    slug = factory.Sequence(lambda n: f"categoria-{n}")
    icon = "scissors"


class ProviderProfileFactory(DjangoModelFactory):
    """Factory para perfis de prestadores."""

    class Meta:
        model = ProviderProfile

    user = factory.SubFactory(ProviderUserFactory)
    business_name = factory.Sequence(lambda n: f"Negócio {n}")
    slug = factory.Sequence(lambda n: f"negocio-{n}")
    bio = "Breve descrição do negócio."
    specialty = "Especialidade"
    is_published = False
