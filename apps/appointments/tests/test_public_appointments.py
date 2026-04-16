"""Testes dos endpoints públicos de agendamento."""

from __future__ import annotations

import datetime

import pytest
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.appointments.models import Appointment, AppointmentStatusHistory
from apps.appointments.tests.factories import AppointmentFactory
from apps.providers.tests.factories import ProviderProfileFactory
from apps.services.tests.factories import ServiceFactory


@pytest.fixture
def api() -> APIClient:
    return APIClient()


@pytest.fixture
def published_booking_context(db: None) -> dict[str, object]:
    provider = ProviderProfileFactory(is_published=True, slug="salao-teste-p0-03")
    service = ServiceFactory(
        provider=provider,
        name="Corte",
        duration=60,
        is_active=True,
        is_online=True,
    )
    return {"provider": provider, "service": service}


def _future_slot() -> datetime.datetime:
    base = timezone.now() + datetime.timedelta(days=25)
    return base.replace(hour=15, minute=0, second=0, microsecond=0)


@pytest.mark.django_db
class TestAppointmentCreate:
    def test_valid_payload_returns_201_with_public_id(
        self,
        api: APIClient,
        published_booking_context: dict[str, object],
    ) -> None:
        provider = published_booking_context["provider"]
        service = published_booking_context["service"]
        start = _future_slot()
        resp = api.post(
            "/api/v1/appointments/",
            {
                "provider_slug": provider.slug,
                "service_id": str(service.id),
                "start_datetime": start.isoformat(),
                "client_name": "Cliente Novo",
                "client_phone": "+5511988877766",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["public_id"].startswith("AGD-")
        assert resp.data["status"] == "pending_confirmation"
        assert "service" in resp.data and "provider" in resp.data

    def test_unknown_provider_slug_returns_404(
        self,
        api: APIClient,
        published_booking_context: dict[str, object],
    ) -> None:
        service = published_booking_context["service"]
        start = _future_slot()
        resp = api.post(
            "/api/v1/appointments/",
            {
                "provider_slug": "slug-inexistente-xyz",
                "service_id": str(service.id),
                "start_datetime": start.isoformat(),
                "client_name": "X",
                "client_phone": "+5511988877766",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_inactive_service_returns_400(
        self,
        api: APIClient,
        published_booking_context: dict[str, object],
    ) -> None:
        provider = published_booking_context["provider"]
        service = published_booking_context["service"]
        service.is_active = False
        service.save(update_fields=["is_active"])
        start = _future_slot()
        resp = api.post(
            "/api/v1/appointments/",
            {
                "provider_slug": provider.slug,
                "service_id": str(service.id),
                "start_datetime": start.isoformat(),
                "client_name": "X",
                "client_phone": "+5511988877766",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["error"]["code"] == "service_unavailable"

    def test_offline_service_returns_400(
        self,
        api: APIClient,
        published_booking_context: dict[str, object],
    ) -> None:
        provider = published_booking_context["provider"]
        service = published_booking_context["service"]
        service.is_online = False
        service.save(update_fields=["is_online"])
        start = _future_slot()
        resp = api.post(
            "/api/v1/appointments/",
            {
                "provider_slug": provider.slug,
                "service_id": str(service.id),
                "start_datetime": start.isoformat(),
                "client_name": "X",
                "client_phone": "+5511988877766",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert resp.data["error"]["code"] == "service_unavailable"

    def test_double_booking_returns_409(
        self,
        api: APIClient,
        published_booking_context: dict[str, object],
    ) -> None:
        provider = published_booking_context["provider"]
        service = published_booking_context["service"]
        start = _future_slot()
        body = {
            "provider_slug": provider.slug,
            "service_id": str(service.id),
            "start_datetime": start.isoformat(),
            "client_name": "A",
            "client_phone": "+5511988877766",
        }
        r1 = api.post("/api/v1/appointments/", body, format="json")
        assert r1.status_code == status.HTTP_201_CREATED
        r2 = api.post(
            "/api/v1/appointments/",
            {**body, "client_name": "B"},
            format="json",
        )
        assert r2.status_code == status.HTTP_409_CONFLICT
        assert r2.data["error"]["code"] == "slot_not_available"

    def test_creates_status_history(
        self,
        api: APIClient,
        published_booking_context: dict[str, object],
    ) -> None:
        provider = published_booking_context["provider"]
        service = published_booking_context["service"]
        start = _future_slot() + datetime.timedelta(hours=2)
        resp = api.post(
            "/api/v1/appointments/",
            {
                "provider_slug": provider.slug,
                "service_id": str(service.id),
                "start_datetime": start.isoformat(),
                "client_name": "Hist",
                "client_phone": "+5511988877700",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED
        appt = Appointment.objects.get(public_id=resp.data["public_id"])
        hist = AppointmentStatusHistory.objects.filter(appointment=appt)
        assert hist.count() == 1
        h = hist.first()
        assert h is not None
        assert h.from_status is None
        assert h.to_status == Appointment.Status.PENDING_CONFIRMATION


@pytest.mark.django_db
class TestAppointmentLookup:
    def test_lookup_success(self, api: APIClient) -> None:
        appt = AppointmentFactory(client_phone="5511999990001")
        url = f"/api/v1/appointments/lookup/?public_id={appt.public_id}&phone=%2B5511999990001"
        resp = api.get(url)
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["public_id"] == appt.public_id
        assert resp.data["client_name"] == appt.client_name

    def test_lookup_wrong_phone_returns_404(self, api: APIClient) -> None:
        appt = AppointmentFactory(client_phone="5511999990002")
        resp = api.get(
            f"/api/v1/appointments/lookup/?public_id={appt.public_id}&phone=%2B5511888888888",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_lookup_unknown_public_id_returns_404(self, api: APIClient) -> None:
        resp = api.get(
            "/api/v1/appointments/lookup/?public_id=AGD-XXXX&phone=%2B5511999990002",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_lookup_phone_formatting_normalized(self, api: APIClient) -> None:
        appt = AppointmentFactory(client_phone="5511999990003")
        resp = api.get(
            f"/api/v1/appointments/lookup/?public_id={appt.public_id}&phone=(11)%2099999-0003",
        )
        assert resp.status_code == status.HTTP_200_OK

    def test_lookup_missing_params_returns_400(self, api: APIClient) -> None:
        resp = api.get("/api/v1/appointments/lookup/")
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
