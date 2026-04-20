"""Testes BDD do fluxo completo de avaliacao pos-consulta."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.appointments.models import Appointment
from apps.providers.models import ProviderProfile
from apps.providers.tests.factories import ProviderProfileFactory
from apps.reviews.models import Review
from apps.reviews.tasks import send_review_request
from apps.services.tests.factories import ServiceFactory


@pytest.mark.django_db
def test_fluxo_concluir_agendamento_gerar_review_enviar_e_atualizar_media() -> None:
    """
    Scenario: Fluxo de ponta a ponta da avaliacao
      Given um agendamento confirmado do prestador
      When o prestador conclui e a task gera token de review
      Then o cliente envia nota e a media do provider e atualizada
    """
    provider: ProviderProfile = ProviderProfileFactory()
    service = ServiceFactory(provider=provider, price=Decimal("120.00"))
    start = timezone.now() + datetime.timedelta(hours=3)
    appointment = Appointment.objects.create(
        public_id="AGD-REV1",
        provider=provider,
        service=service,
        client_name="Maria Silva",
        client_phone="+5511999999000",
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=service.duration_minutes),
        status=Appointment.Status.CONFIRMED,
        origin=Appointment.Origin.ONLINE,
    )
    provider_api = APIClient()
    provider_api.force_authenticate(user=provider.user)

    with patch("apps.appointments.views.send_review_request.apply_async") as mocked_apply:
        response = provider_api.post(f"/api/v1/appointments/{appointment.pk}/complete/")
    assert response.status_code == status.HTTP_200_OK
    mocked_apply.assert_called_once_with(args=[str(appointment.pk)], countdown=7200)

    with patch("apps.reviews.tasks.get_whatsapp_client") as mocked_client:
        mocked_client.return_value.send_template.return_value = {"external_id": "x"}
        send_review_request(str(appointment.pk))
    review = Review.objects.get(appointment=appointment)
    assert review.rating is None

    public_api = APIClient()
    submit = public_api.post(
        f"/api/v1/reviews/by-token/{review.review_token}/",
        {"rating": 5, "comment": "Excelente"},
        format="json",
    )
    assert submit.status_code == status.HTTP_200_OK
    provider.refresh_from_db()
    assert provider.total_reviews == 1
    assert float(provider.average_rating or 0) == 5.0
