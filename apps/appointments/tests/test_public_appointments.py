"""Testes dos endpoints públicos de agendamento."""

from __future__ import annotations

import datetime

import pytest
from django.core.cache import cache
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.appointments.cancellation import validate_cancellation
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
        client_user: User,
    ) -> None:
        api.force_authenticate(user=client_user)
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
        client_user: User,
    ) -> None:
        api.force_authenticate(user=client_user)
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
        client_user: User,
    ) -> None:
        api.force_authenticate(user=client_user)
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
        client_user: User,
    ) -> None:
        api.force_authenticate(user=client_user)
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
        client_user: User,
    ) -> None:
        api.force_authenticate(user=client_user)
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
        client_user: User,
    ) -> None:
        api.force_authenticate(user=client_user)
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

    def test_create_without_auth_returns_401(
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
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_create_with_provider_role_returns_403(
        self,
        api: APIClient,
        published_booking_context: dict[str, object],
        provider_user: User,
    ) -> None:
        api.force_authenticate(user=provider_user)
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
        assert resp.status_code == status.HTTP_403_FORBIDDEN


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

    def test_lookup_includes_cancellation_fields(self, api: APIClient) -> None:
        appt = AppointmentFactory(status=Appointment.Status.CONFIRMED, client_phone="5511999990003")
        appt.provider.min_notice_hours = 2
        appt.provider.save(update_fields=["min_notice_hours"])

        resp = api.get(
            f"/api/v1/appointments/lookup/?public_id={appt.public_id}&phone=%2B5511999990003",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert "can_cancel" in resp.data
        assert "cancel_deadline" in resp.data


@pytest.mark.django_db
class TestValidateCancellation:
    def test_rejects_past_appointment(self) -> None:
        appt = AppointmentFactory(
            start_datetime=timezone.now() - datetime.timedelta(hours=1),
            end_datetime=timezone.now(),
            status=Appointment.Status.CONFIRMED,
        )
        error = validate_cancellation(appt, cancelled_by=Appointment.CancelledBy.CLIENT)
        assert error is not None
        assert error.code == "appointment_in_past"

    def test_rejects_when_notice_window_closed(self) -> None:
        appt = AppointmentFactory(
            start_datetime=timezone.now() + datetime.timedelta(minutes=30),
            end_datetime=timezone.now() + datetime.timedelta(hours=1, minutes=30),
            status=Appointment.Status.CONFIRMED,
        )
        appt.provider.min_notice_hours = 2
        appt.provider.save(update_fields=["min_notice_hours"])
        error = validate_cancellation(appt, cancelled_by=Appointment.CancelledBy.CLIENT)
        assert error is not None
        assert error.code == "cancellation_window_closed"

    def test_rejects_invalid_status(self) -> None:
        appt = AppointmentFactory(status=Appointment.Status.CANCELLED)
        error = validate_cancellation(appt, cancelled_by=Appointment.CancelledBy.CLIENT)
        assert error is not None
        assert error.code == "invalid_status_for_cancellation"

    def test_accepts_valid_cancellation(self) -> None:
        appt = AppointmentFactory(status=Appointment.Status.PENDING_CONFIRMATION)
        appt.provider.min_notice_hours = 1
        appt.provider.save(update_fields=["min_notice_hours"])
        error = validate_cancellation(appt, cancelled_by=Appointment.CancelledBy.CLIENT)
        assert error is None


@pytest.mark.django_db
class TestAppointmentCancelByCode:
    def test_cancel_with_correct_credentials(
        self,
        api: APIClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        appt = AppointmentFactory(
            status=Appointment.Status.CONFIRMED,
            client_phone="5511999990004",
        )
        monkeypatch.setattr(
            "apps.appointments.views.notify_provider_cancellation.apply_async",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "apps.appointments.views.send_cancellation_ack_client.apply_async",
            lambda *args, **kwargs: None,
        )

        resp = api.post(
            "/api/v1/appointments/cancel-by-code/",
            {
                "public_id": appt.public_id,
                "phone": "+5511999990004",
                "reason": "Imprevisto",
            },
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        appt.refresh_from_db()
        assert appt.status == Appointment.Status.CANCELLED
        assert appt.cancelled_by == Appointment.CancelledBy.CLIENT
        assert appt.cancellation_reason == "Imprevisto"
        assert AppointmentStatusHistory.objects.filter(
            appointment=appt,
            to_status=Appointment.Status.CANCELLED,
        ).exists()

    def test_cancel_wrong_phone_returns_404(self, api: APIClient) -> None:
        appt = AppointmentFactory(client_phone="5511999990005")
        resp = api.post(
            "/api/v1/appointments/cancel-by-code/",
            {"public_id": appt.public_id, "phone": "+5511888888888"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_cancel_unknown_public_id_returns_404(self, api: APIClient) -> None:
        resp = api.post(
            "/api/v1/appointments/cancel-by-code/",
            {"public_id": "AGD-XXXX", "phone": "+5511999990005"},
            format="json",
        )
        assert resp.status_code == status.HTTP_404_NOT_FOUND

    def test_cancel_returns_422_when_not_allowed(
        self,
        api: APIClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        appt = AppointmentFactory(
            status=Appointment.Status.CONFIRMED,
            client_phone="5511999990006",
            start_datetime=timezone.now() + datetime.timedelta(minutes=20),
            end_datetime=timezone.now() + datetime.timedelta(hours=1, minutes=20),
        )
        appt.provider.min_notice_hours = 2
        appt.provider.save(update_fields=["min_notice_hours"])
        monkeypatch.setattr(
            "apps.appointments.views.notify_provider_cancellation.apply_async",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "apps.appointments.views.send_cancellation_ack_client.apply_async",
            lambda *args, **kwargs: None,
        )

        resp = api.post(
            "/api/v1/appointments/cancel-by-code/",
            {"public_id": appt.public_id, "phone": "+5511999990006"},
            format="json",
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert resp.data["code"] == "cancellation_window_closed"


@pytest.mark.django_db
class TestAppointmentRescheduleOptions:
    def test_returns_slots_for_valid_phone(
        self,
        api: APIClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        appt = AppointmentFactory(client_phone="5511999990010")
        first_slot = timezone.now() + datetime.timedelta(days=2)
        second_slot = timezone.now() + datetime.timedelta(days=2, hours=1)

        monkeypatch.setattr(
            "core.utils.availability.get_available_slots",
            lambda **kwargs: [first_slot, second_slot],
        )

        resp = api.get(f"/api/v1/appointments/{appt.pk}/reschedule-options/?phone=%2B5511999990010")
        assert resp.status_code == status.HTTP_200_OK
        assert 0 < len(resp.data["slots"]) <= 10
        assert "start_datetime" in resp.data["slots"][0]
        assert "end_datetime" in resp.data["slots"][0]

    def test_returns_message_when_no_slots(
        self,
        api: APIClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        appt = AppointmentFactory(client_phone="5511999990011")
        monkeypatch.setattr("core.utils.availability.get_available_slots", lambda **kwargs: [])

        resp = api.get(f"/api/v1/appointments/{appt.pk}/reschedule-options/?phone=%2B5511999990011")
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["slots"] == []
        assert resp.data["message"] == "Sem horários disponíveis nos próximos 60 dias."

    def test_wrong_phone_returns_404(self, api: APIClient) -> None:
        appt = AppointmentFactory(client_phone="5511999990012")
        resp = api.get(f"/api/v1/appointments/{appt.pk}/reschedule-options/?phone=%2B5511888888888")
        assert resp.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestAppointmentReschedule:
    def test_reschedule_success_creates_new_and_cancels_original(
        self,
        api: APIClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        appt = AppointmentFactory(
            client_phone="5511999990013",
            status=Appointment.Status.CONFIRMED,
            start_datetime=timezone.now() + datetime.timedelta(days=3),
        )
        appt.end_datetime = appt.start_datetime + datetime.timedelta(minutes=appt.service.duration)
        appt.save(update_fields=["end_datetime"])

        monkeypatch.setattr(
            "apps.appointments.views.send_whatsapp_confirmation_request.apply_async",
            lambda *args, **kwargs: None,
        )
        new_start = timezone.now() + datetime.timedelta(days=5, hours=2)
        resp = api.post(
            f"/api/v1/appointments/{appt.pk}/reschedule/",
            {"phone": "+5511999990013", "start_datetime": new_start.isoformat()},
            format="json",
        )
        assert resp.status_code == status.HTTP_201_CREATED

        appt.refresh_from_db()
        assert appt.status == Appointment.Status.CANCELLED
        assert appt.cancelled_by == Appointment.CancelledBy.SYSTEM

        new_appointment = Appointment.objects.get(public_id=resp.data["public_id"])
        assert new_appointment.pk != appt.pk
        assert new_appointment.status == Appointment.Status.PENDING_CONFIRMATION

    def test_reschedule_conflict_returns_409_with_available_slots(
        self,
        api: APIClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        appt = AppointmentFactory(
            client_phone="5511999990014",
            status=Appointment.Status.CONFIRMED,
            start_datetime=timezone.now() + datetime.timedelta(days=3),
        )
        target_start = timezone.now() + datetime.timedelta(days=4, hours=1)
        target_end = target_start + datetime.timedelta(minutes=appt.service.duration)
        AppointmentFactory(
            provider=appt.provider,
            service=appt.service,
            staff=appt.staff,
            status=Appointment.Status.CONFIRMED,
            start_datetime=target_start,
            end_datetime=target_end,
        )
        monkeypatch.setattr(
            "core.utils.availability.get_available_slots",
            lambda **kwargs: [timezone.now() + datetime.timedelta(days=6)],
        )

        resp = api.post(
            f"/api/v1/appointments/{appt.pk}/reschedule/",
            {"phone": "+5511999990014", "start_datetime": target_start.isoformat()},
            format="json",
        )
        assert resp.status_code == status.HTTP_409_CONFLICT
        assert resp.data["code"] == "slot_taken"
        assert isinstance(resp.data["available_slots"], list)

    def test_reschedule_past_appointment_returns_422(self, api: APIClient) -> None:
        appt = AppointmentFactory(
            client_phone="5511999990015",
            status=Appointment.Status.CONFIRMED,
            start_datetime=timezone.now() - datetime.timedelta(hours=2),
            end_datetime=timezone.now() - datetime.timedelta(hours=1),
        )
        new_start = timezone.now() + datetime.timedelta(days=4)
        resp = api.post(
            f"/api/v1/appointments/{appt.pk}/reschedule/",
            {"phone": "+5511999990015", "start_datetime": new_start.isoformat()},
            format="json",
        )
        assert resp.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert resp.data["code"] == "appointment_in_past"

    def test_public_flow_lookup_cancel_reschedule(
        self,
        api: APIClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        appt = AppointmentFactory(
            client_phone="5511999990090",
            status=Appointment.Status.CONFIRMED,
            start_datetime=timezone.now() + datetime.timedelta(days=3),
        )
        appt.end_datetime = appt.start_datetime + datetime.timedelta(minutes=appt.service.duration)
        appt.provider.min_notice_hours = 1
        appt.provider.save(update_fields=["min_notice_hours"])
        appt.save(update_fields=["end_datetime"])

        monkeypatch.setattr(
            "apps.appointments.views.notify_provider_cancellation.apply_async",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "apps.appointments.views.send_cancellation_ack_client.apply_async",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "apps.appointments.views.send_whatsapp_confirmation_request.apply_async",
            lambda *args, **kwargs: None,
        )
        next_slot = timezone.now() + datetime.timedelta(days=6, hours=2)
        monkeypatch.setattr(
            "core.utils.availability.get_available_slots",
            lambda **kwargs: [next_slot],
        )

        lookup = api.get(
            f"/api/v1/appointments/lookup/?public_id={appt.public_id}&phone=%2B5511999990090",
        )
        assert lookup.status_code == status.HTTP_200_OK

        cancel = api.post(
            "/api/v1/appointments/cancel-by-code/",
            {"public_id": appt.public_id, "phone": "+5511999990090", "reason": "Teste"},
            format="json",
        )
        assert cancel.status_code == status.HTTP_200_OK

        options = api.get(
            f"/api/v1/appointments/{appt.pk}/reschedule-options/?phone=%2B5511999990090",
        )
        assert options.status_code == status.HTTP_200_OK
        assert options.data["slots"]

        reschedule = api.post(
            f"/api/v1/appointments/{appt.pk}/reschedule/",
            {"phone": "+5511999990090", "start_datetime": next_slot.isoformat()},
            format="json",
        )
        assert reschedule.status_code == status.HTTP_201_CREATED
        assert reschedule.data["public_id"] != appt.public_id

    def test_cancel_invalidates_availability_cache(
        self,
        api: APIClient,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        appt = AppointmentFactory(
            client_phone="5511999990091",
            status=Appointment.Status.CONFIRMED,
            start_datetime=timezone.now() + datetime.timedelta(days=2),
        )
        appt.end_datetime = appt.start_datetime + datetime.timedelta(minutes=appt.service.duration)
        appt.save(update_fields=["end_datetime"])

        cache_key = f"availability:{appt.provider_id}:{appt.start_datetime.date()}"
        cache.set(cache_key, {"slots": ["dummy"]}, timeout=60)
        assert cache.get(cache_key) is not None

        monkeypatch.setattr(
            "apps.appointments.views.notify_provider_cancellation.apply_async",
            lambda *args, **kwargs: None,
        )
        monkeypatch.setattr(
            "apps.appointments.views.send_cancellation_ack_client.apply_async",
            lambda *args, **kwargs: None,
        )

        resp = api.post(
            "/api/v1/appointments/cancel-by-code/",
            {"public_id": appt.public_id, "phone": "+5511999990091"},
            format="json",
        )
        assert resp.status_code == status.HTTP_200_OK
        assert cache.get(cache_key) is None
