from __future__ import annotations

import hashlib
import hmac
import json
from datetime import timedelta
from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest
from django.conf import settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import User
from apps.appointments.models import Appointment, AppointmentStatusHistory
from apps.appointments.tasks import auto_confirm_pending_appointments, send_24h_reminders
from apps.notifications.models import Notification
from apps.notifications.tasks import send_whatsapp_confirmation_request
from apps.notifications.whatsapp.evolution import EvolutionWhatsAppClient
from apps.notifications.whatsapp.meta import MetaWhatsAppClient
from apps.providers.models import ProviderProfile, ServiceCategory
from apps.services.models import Service
from apps.webhooks.models import WhatsAppInboundMessage
from apps.webhooks.tasks import process_whatsapp_response


def _create_appointment(*, status: str = Appointment.Status.PENDING_CONFIRMATION) -> Appointment:
    provider_user = User.objects.create_user(
        email=f"provider-{timezone.now().timestamp()}@test.com",
        password="senha_segura_123",
        role=User.Role.PROVIDER,
        full_name="Prestador",
    )
    category = ServiceCategory.objects.create(
        name="Saude",
        slug=f"saude-{timezone.now().timestamp()}",
    )
    provider = ProviderProfile.objects.create(
        user=provider_user,
        slug=f"provider-{timezone.now().timestamp()}",
        business_name="Clinica Teste",
        is_published=True,
        category=category,
        whatsapp_number="+5511999999999",
    )
    service = Service.objects.create(
        provider=provider,
        name="Consulta",
        price=Decimal("100.00"),
        duration=60,
        is_active=True,
        is_online=True,
    )
    start = timezone.now() + timedelta(days=1)
    return Appointment.objects.create(
        public_id=f"AGD-{str(uuid4())[:8].upper()}",
        provider=provider,
        service=service,
        client_name="Cliente Teste",
        client_phone="+5511988887777",
        start_datetime=start,
        end_datetime=start + timedelta(minutes=service.duration),
        status=status,
    )


@pytest.mark.django_db
def test_meta_whatsapp_client_send_template_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyResponse:
        def raise_for_status(self) -> None:
            return

        def json(self) -> dict[str, Any]:
            return {"messages": [{"id": "wamid.meta"}]}

    def fake_post(*args: object, **kwargs: object) -> DummyResponse:
        return DummyResponse()

    monkeypatch.setattr("apps.notifications.whatsapp.meta.httpx.post", fake_post)
    client = MetaWhatsAppClient()
    result = client.send_template("+5511", "template", {"a": "b"}, ["CONFIRM_x"])
    assert result["external_id"] == "wamid.meta"


@pytest.mark.django_db
def test_evolution_whatsapp_client_send_template_success(monkeypatch: pytest.MonkeyPatch) -> None:
    class DummyResponse:
        def raise_for_status(self) -> None:
            return

        def json(self) -> dict[str, Any]:
            return {"key": {"id": "evolution-id"}}

    def fake_post(*args: object, **kwargs: object) -> DummyResponse:
        return DummyResponse()

    monkeypatch.setattr("apps.notifications.whatsapp.evolution.httpx.post", fake_post)
    client = EvolutionWhatsAppClient()
    result = client.send_template("+5511", "template", {"foo": "bar"})
    assert result["external_id"] == "evolution-id"


@pytest.mark.django_db
def test_send_whatsapp_confirmation_request_creates_notification(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointment = _create_appointment()

    def fake_send_template(**kwargs: object) -> dict[str, str]:
        return {"external_id": "wamid.123", "provider": "meta"}

    monkeypatch.setattr(
        "apps.notifications.tasks.get_whatsapp_client",
        lambda: type("Dummy", (), {"send_template": staticmethod(fake_send_template)})(),
    )
    send_whatsapp_confirmation_request.apply(args=[str(appointment.pk)], throw=True)
    notification = Notification.objects.get(appointment=appointment)
    appointment.refresh_from_db()
    assert notification.external_id == "wamid.123"
    assert appointment.confirmation_sent is True


@pytest.mark.django_db
def test_send_whatsapp_confirmation_request_retries_on_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointment = _create_appointment()
    call_count = {"count": 0}

    def fake_send_template(**kwargs: object) -> dict[str, str]:
        call_count["count"] += 1
        raise RuntimeError("boom")

    monkeypatch.setattr(
        "apps.notifications.tasks.get_whatsapp_client",
        lambda: type("Dummy", (), {"send_template": staticmethod(fake_send_template)})(),
    )

    send_whatsapp_confirmation_request.apply(args=[str(appointment.pk)], throw=True)
    appointment.refresh_from_db()
    assert call_count["count"] >= 1
    assert appointment.confirmation_sent is False


def _signed_payload(payload: dict[str, object]) -> tuple[str, str]:
    body = json.dumps(payload).encode("utf-8")
    signature = hmac.new(settings.WHATSAPP_APP_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return body.decode("utf-8"), f"sha256={signature}"


@pytest.mark.django_db
def test_webhook_post_valid_signature_and_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    appointment = _create_appointment()
    wamid = "wamid.abc123"
    payload = {
        "entry": [
            {
                "changes": [
                    {
                        "value": {
                            "messages": [
                                {
                                    "id": wamid,
                                    "from": appointment.client_phone,
                                    "type": "button",
                                    "button": {"payload": f"CONFIRM_{appointment.pk}"},
                                }
                            ]
                        }
                    }
                ]
            }
        ]
    }
    raw_body, signature = _signed_payload(payload)
    api_client = APIClient()
    called: list[str] = []

    monkeypatch.setattr(
        "apps.webhooks.views.process_whatsapp_response.delay",
        lambda value: called.append(value),
    )
    first = api_client.post(
        "/api/v1/webhooks/whatsapp/",
        data=raw_body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=signature,
    )
    second = api_client.post(
        "/api/v1/webhooks/whatsapp/",
        data=raw_body,
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256=signature,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert WhatsAppInboundMessage.objects.filter(wamid=wamid).count() == 1
    assert called == [wamid]


@pytest.mark.django_db
def test_webhook_post_invalid_signature_returns_403() -> None:
    api_client = APIClient()
    response = api_client.post(
        "/api/v1/webhooks/whatsapp/",
        data=json.dumps({}),
        content_type="application/json",
        HTTP_X_HUB_SIGNATURE_256="sha256=invalid",
    )
    assert response.status_code == 403


@pytest.mark.django_db
def test_webhook_get_verification_token() -> None:
    api_client = APIClient()
    response = api_client.get(
        "/api/v1/webhooks/whatsapp/",
        {
            "hub.mode": "subscribe",
            "hub.verify_token": settings.WHATSAPP_VERIFY_TOKEN,
            "hub.challenge": "12345",
        },
    )
    assert response.status_code == 200
    assert response.content.decode() == "12345"


@pytest.mark.django_db
def test_process_whatsapp_response_confirm_changes_status(monkeypatch: pytest.MonkeyPatch) -> None:
    appointment = _create_appointment()
    inbound = WhatsAppInboundMessage.objects.create(
        wamid="wamid.confirm",
        from_phone=appointment.client_phone,
        button_payload=f"CONFIRM_{appointment.pk}",
    )
    monkeypatch.setattr("apps.webhooks.tasks.send_whatsapp_confirmed_ack.delay", lambda _id: None)
    process_whatsapp_response("wamid.confirm")
    appointment.refresh_from_db()
    inbound.refresh_from_db()
    assert appointment.status == Appointment.Status.CONFIRMED
    assert inbound.processed is True


@pytest.mark.django_db
def test_process_whatsapp_response_cancel_sets_cancelled_by(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointment = _create_appointment()
    WhatsAppInboundMessage.objects.create(
        wamid="wamid.cancel",
        from_phone=appointment.client_phone,
        button_payload=f"CANCEL_{appointment.pk}",
    )
    monkeypatch.setattr("apps.webhooks.tasks.notify_provider_cancellation.delay", lambda _id: None)
    process_whatsapp_response("wamid.cancel")
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CANCELLED
    assert appointment.cancelled_by == Appointment.CancelledBy.CLIENT


@pytest.mark.django_db
def test_process_whatsapp_response_reschedule_sends_link(monkeypatch: pytest.MonkeyPatch) -> None:
    appointment = _create_appointment()
    WhatsAppInboundMessage.objects.create(
        wamid="wamid.reschedule",
        from_phone=appointment.client_phone,
        button_payload=f"RESCHEDULE_{appointment.pk}",
    )
    called: list[str] = []
    monkeypatch.setattr(
        "apps.webhooks.tasks.send_reschedule_link.delay",
        lambda _id: called.append(_id),
    )
    process_whatsapp_response("wamid.reschedule")
    assert called == [str(appointment.pk)]


@pytest.mark.django_db
def test_process_whatsapp_response_rescheduled_creates_new_appointment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    appointment = _create_appointment()
    inbound = WhatsAppInboundMessage.objects.create(
        wamid="wamid.rescheduled.ok",
        from_phone=appointment.client_phone,
        button_payload=(
            f"RESCHEDULED_{appointment.pk}_"
            f"{(appointment.start_datetime + timedelta(days=2)).isoformat()}"
        ),
    )
    sent_confirmations: list[str] = []
    monkeypatch.setattr(
        "apps.webhooks.tasks.send_whatsapp_confirmation_request.delay",
        lambda appointment_id: sent_confirmations.append(appointment_id),
    )

    process_whatsapp_response("wamid.rescheduled.ok")
    inbound.refresh_from_db()
    appointment.refresh_from_db()
    new_appointment = Appointment.objects.exclude(pk=appointment.pk).latest("created_at")

    assert inbound.action_taken == "rescheduled"
    assert appointment.status == Appointment.Status.CANCELLED
    assert new_appointment.status == Appointment.Status.PENDING_CONFIRMATION
    assert sent_confirmations == [str(new_appointment.pk)]


@pytest.mark.django_db
def test_process_whatsapp_response_rescheduled_invalid_format_is_ignored() -> None:
    appointment = _create_appointment()
    inbound = WhatsAppInboundMessage.objects.create(
        wamid="wamid.rescheduled.invalid",
        from_phone=appointment.client_phone,
        button_payload=f"RESCHEDULED_{appointment.pk}",
    )

    process_whatsapp_response("wamid.rescheduled.invalid")
    inbound.refresh_from_db()
    appointment.refresh_from_db()

    assert inbound.processed is True
    assert inbound.action_taken == "ignored"
    assert appointment.status == Appointment.Status.PENDING_CONFIRMATION


@pytest.mark.django_db
def test_process_whatsapp_response_nonexistent_uuid_no_exception() -> None:
    WhatsAppInboundMessage.objects.create(
        wamid="wamid.invalid",
        from_phone="+5511",
        button_payload="CONFIRM_b2b92076-2d50-42b7-b65c-4dc6988d5aab",
    )
    process_whatsapp_response("wamid.invalid")
    inbound = WhatsAppInboundMessage.objects.get(wamid="wamid.invalid")
    assert inbound.processed is True


@pytest.mark.django_db
def test_send_24h_reminders_marks_sent_and_queues(monkeypatch: pytest.MonkeyPatch) -> None:
    appointment = _create_appointment(status=Appointment.Status.CONFIRMED)
    appointment.start_datetime = timezone.now() + timedelta(hours=24)
    appointment.save(update_fields=["start_datetime"])
    calls: list[str] = []
    monkeypatch.setattr(
        "apps.appointments.tasks.send_whatsapp_reminder_24h.delay",
        lambda appointment_id: calls.append(appointment_id),
    )
    send_24h_reminders()
    appointment.refresh_from_db()
    assert appointment.reminder_24h_sent is True
    assert calls == [str(appointment.pk)]


@pytest.mark.django_db
def test_auto_confirm_pending_appointments_only_old_records() -> None:
    old_appointment = _create_appointment()
    recent_appointment = _create_appointment()
    Appointment.objects.filter(pk=old_appointment.pk).update(
        created_at=timezone.now() - timedelta(hours=25)
    )
    Appointment.objects.filter(pk=recent_appointment.pk).update(
        created_at=timezone.now() - timedelta(hours=1)
    )
    auto_confirm_pending_appointments()
    old_appointment.refresh_from_db()
    recent_appointment.refresh_from_db()
    assert old_appointment.status == Appointment.Status.CONFIRMED
    assert recent_appointment.status == Appointment.Status.PENDING_CONFIRMATION
    assert (
        AppointmentStatusHistory.objects.filter(
            appointment=old_appointment,
            to_status=Appointment.Status.CONFIRMED,
        ).exists()
        is True
    )
