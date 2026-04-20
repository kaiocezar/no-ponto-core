"""Factories para testes de providers."""

import datetime
import uuid

import factory
from factory.django import DjangoModelFactory

from apps.accounts.tests.factories import ProviderUserFactory
from apps.providers.models import (
    ProviderProfile,
    ScheduleBlock,
    ServiceCategory,
    Staff,
    WorkingHours,
)


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


class WorkingHoursFactory(DjangoModelFactory):
    """Factory para horários de funcionamento."""

    class Meta:
        model = WorkingHours

    provider = factory.SubFactory(ProviderProfileFactory)
    weekday = factory.Sequence(lambda n: n % 7)
    start_time = factory.LazyFunction(lambda: datetime.time(9, 0))
    end_time = factory.LazyFunction(lambda: datetime.time(18, 0))
    is_active = True


class StaffFactory(DjangoModelFactory):
    """Factory para membros da equipe."""

    class Meta:
        model = Staff

    provider = factory.SubFactory(ProviderProfileFactory)
    user = factory.SubFactory(ProviderUserFactory)
    name = factory.Sequence(lambda n: f"Profissional {n}")
    role = "practitioner"
    is_active = True
    invite_email = factory.LazyAttribute(lambda o: f"{o.name.lower().replace(' ', '.')}@test.com")


class StaffInviteFactory(DjangoModelFactory):
    """Factory para Staff ainda não aceito (somente convite)."""

    class Meta:
        model = Staff

    provider = factory.SubFactory(ProviderProfileFactory)
    user = None
    name = factory.Sequence(lambda n: f"Convidado {n}")
    invite_email = factory.Sequence(lambda n: f"convidado{n}@test.com")
    invite_token = factory.LazyFunction(uuid.uuid4)
    role = "practitioner"
    is_active = True


class ScheduleBlockFactory(DjangoModelFactory):
    """Factory para bloqueios de agenda."""

    class Meta:
        model = ScheduleBlock

    provider = factory.SubFactory(ProviderProfileFactory)
    start_datetime = factory.LazyFunction(
        lambda: datetime.datetime(2025, 1, 1, 10, 0, tzinfo=datetime.UTC)
    )
    end_datetime = factory.LazyFunction(
        lambda: datetime.datetime(2025, 1, 1, 11, 0, tzinfo=datetime.UTC)
    )
    reason = "Bloqueio de teste"
    is_recurring = False
