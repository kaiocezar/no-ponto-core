"""Testes BDD do historico de clientes do prestador."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.appointments.models import Appointment
from apps.providers.tests.factories import ProviderProfileFactory
from apps.services.tests.factories import ServiceFactory


@pytest.mark.django_db
def test_prestador_busca_cliente_ve_historico_e_adiciona_nota() -> None:
    """
    Scenario: Prestador consulta historico e cria nota interna
      Given clientes com agendamentos para o prestador
      When o prestador busca por telefone, abre historico e cria nota
      Then visualiza apenas os proprios dados e notas
    """
    provider = ProviderProfileFactory()
    other_provider = ProviderProfileFactory()
    service = ServiceFactory(provider=provider)
    other_service = ServiceFactory(provider=other_provider)
    start = timezone.now() + datetime.timedelta(days=1)

    Appointment.objects.create(
        public_id="AGD-CLI1",
        provider=provider,
        service=service,
        client_name="Carla Dias",
        client_phone="+551198887766",
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=30),
        status=Appointment.Status.CONFIRMED,
    )
    Appointment.objects.create(
        public_id="AGD-CLI2",
        provider=other_provider,
        service=other_service,
        client_name="Carla Dias",
        client_phone="+551198887766",
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=30),
        status=Appointment.Status.CONFIRMED,
    )

    api = APIClient()
    api.force_authenticate(user=provider.user)

    clients = api.get("/api/v1/providers/me/clients/", {"search": "8877"})
    assert clients.status_code == status.HTTP_200_OK
    assert len(clients.json()) == 1

    history = api.get("/api/v1/providers/me/clients/+551198887766/appointments/")
    assert history.status_code == status.HTTP_200_OK
    assert len(history.json()["data"]) == 1

    created = api.post(
        "/api/v1/providers/me/clients/+551198887766/notes/",
        {"note": "Prefere horario da manha"},
        format="json",
    )
    assert created.status_code == status.HTTP_201_CREATED

    notes = api.get("/api/v1/providers/me/clients/+551198887766/notes/")
    assert notes.status_code == status.HTTP_200_OK
    assert len(notes.json()) == 1
