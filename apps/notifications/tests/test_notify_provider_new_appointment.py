"""Testes de hardening de notify_provider_new_appointment."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from celery.exceptions import Retry
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment, generate_public_id
from apps.notifications.models import Notification
from apps.notifications.tasks import notify_provider_new_appointment
from apps.providers.models import ProviderProfile, ServiceCategory
from apps.services.models import Service


def _make_appt(
    *,
    whatsapp: str = "+5511999999999",
    client: User | None = None,
    client_name: str = "Nome legado",
) -> Appointment:
    provider_user = User.objects.create_user(
        email=f"p-{timezone.now().timestamp()}@t.com",
        password="senha_segura_123",
        role=User.Role.PROVIDER,
        full_name="Prestador",
    )
    cat = ServiceCategory.objects.create(
        name="Cat",
        slug=f"cat-{timezone.now().timestamp()}",
    )
    provider = ProviderProfile.objects.create(
        user=provider_user,
        slug=f"slug-{timezone.now().timestamp()}",
        business_name="Neg",
        is_published=True,
        category=cat,
        whatsapp_number=whatsapp,
    )
    service = Service.objects.create(
        provider=provider,
        name="Srv",
        price=Decimal("50"),
        duration_minutes=30,
        is_active=True,
        is_online=True,
    )
    start = timezone.now() + timedelta(days=1)
    return Appointment.objects.create(
        public_id=generate_public_id(),
        provider=provider,
        service=service,
        client=client,
        client_name=client_name,
        client_phone="+5511988887777",
        start_datetime=start,
        end_datetime=start + timedelta(minutes=30),
        status=Appointment.Status.PENDING_CONFIRMATION,
    )


@pytest.mark.django_db
def test_dedup_skips_second_send(monkeypatch: pytest.MonkeyPatch) -> None:
    ap = _make_appt()
    calls: list[int] = []

    def fake_send_template(**kwargs: object) -> dict[str, str]:
        calls.append(1)
        return {"external_id": "wamid.1"}

    monkeypatch.setattr(
        "apps.notifications.tasks.get_whatsapp_client",
        lambda: type("D", (), {"send_template": staticmethod(fake_send_template)})(),
    )
    notify_provider_new_appointment.apply(args=[str(ap.pk)], throw=True)
    notify_provider_new_appointment.apply(args=[str(ap.pk)], throw=True)
    assert len(calls) == 1


@pytest.mark.django_db
def test_stub_email_when_no_whatsapp(monkeypatch: pytest.MonkeyPatch) -> None:
    ap = _make_appt(whatsapp="")

    def boom(**kwargs: object) -> dict[str, str]:
        raise AssertionError("não deve enviar WhatsApp")

    monkeypatch.setattr(
        "apps.notifications.tasks.get_whatsapp_client",
        lambda: type("D", (), {"send_template": staticmethod(boom)})(),
    )
    notify_provider_new_appointment.apply(args=[str(ap.pk)], throw=True)
    n = Notification.objects.get(appointment=ap, type=Notification.Type.NEW_APPOINTMENT_PROVIDER)
    assert n.channel == Notification.Channel.EMAIL
    assert n.status == Notification.Status.FAILED
    assert "MVP" in n.error_message


@pytest.mark.django_db
def test_client_full_name_precedence(monkeypatch: pytest.MonkeyPatch) -> None:
    client = User.objects.create_user(
        phone_number="+5511911122233",
        full_name="Cliente Auth",
        role=User.Role.CLIENT,
    )
    ap = _make_appt(client=client, client_name="Legado")
    captured: dict[str, str] = {}

    def fake_send_template(*, variables: dict[str, str], **kwargs: object) -> dict[str, str]:
        captured.update(variables)
        return {"external_id": "x"}

    monkeypatch.setattr(
        "apps.notifications.tasks.get_whatsapp_client",
        lambda: type("D", (), {"send_template": staticmethod(fake_send_template)})(),
    )
    notify_provider_new_appointment.apply(args=[str(ap.pk)], throw=True)
    assert captured.get("cliente") == "Cliente Auth"


@pytest.mark.django_db
def test_notify_provider_new_appointment_retries_after_transient_send_failure(
    settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Primeira falha no envio levanta Retry do Celery; segunda execução conclui com SENT."""
    settings.CELERY_TASK_ALWAYS_EAGER = False
    ap = _make_appt()
    calls = {"n": 0}

    def fake_send_template(**kwargs: object) -> dict[str, str]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("falha transitória no template")
        return {"external_id": "wamid.retry-ok"}

    monkeypatch.setattr(
        "apps.notifications.tasks.get_whatsapp_client",
        lambda: type("D", (), {"send_template": staticmethod(fake_send_template)})(),
    )

    with pytest.raises(Retry):
        notify_provider_new_appointment.apply(args=[str(ap.pk)], throw=True)

    notify_provider_new_appointment.apply(args=[str(ap.pk)], throw=True)

    n = Notification.objects.get(appointment=ap, type=Notification.Type.NEW_APPOINTMENT_PROVIDER)
    assert n.status == Notification.Status.SENT
    assert calls["n"] == 2
