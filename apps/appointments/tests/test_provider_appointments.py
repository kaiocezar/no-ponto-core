"""Testes da API de agendamentos do prestador."""

from __future__ import annotations

import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.appointments.models import Appointment
from apps.providers.tests.factories import ProviderProfileFactory
from apps.services.tests.factories import ServiceFactory


@pytest.fixture
def provider_a() -> object:
    return ProviderProfileFactory(whatsapp_number="+5511999999999")


@pytest.fixture
def provider_b() -> object:
    return ProviderProfileFactory()


@pytest.fixture
def service_a(provider_a: object) -> object:
    return ServiceFactory(
        provider=provider_a,
        duration_minutes=60,
        price=Decimal("80.00"),
        is_active=True,
    )


def _auth_client(user: object) -> APIClient:
    c = APIClient()
    c.force_authenticate(user=user)
    return c


@pytest.mark.django_db
def test_list_filters_isolation(
    provider_a: object,
    provider_b: object,
    service_a: object,
) -> None:
    start = timezone.now() + datetime.timedelta(days=2)
    start = start.replace(hour=10, minute=0, second=0, microsecond=0)
    ap1 = Appointment.objects.create(
        public_id="AGD-AAAA",
        provider=provider_a,
        service=service_a,
        client_name="A",
        client_phone="+5511988880001",
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=60),
        status=Appointment.Status.CONFIRMED,
        origin=Appointment.Origin.ONLINE,
    )
    Appointment.objects.create(
        public_id="AGD-BBBB",
        provider=provider_b,
        service=ServiceFactory(provider=provider_b),
        client_name="B",
        client_phone="+5511988880002",
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=60),
        status=Appointment.Status.CONFIRMED,
        origin=Appointment.Origin.ONLINE,
    )

    url = reverse("provider-appointments")
    client = _auth_client(provider_a.user)
    df = start.date().isoformat()
    r = client.get(url, {"date_from": df, "date_to": df, "status": "confirmed"})
    assert r.status_code == status.HTTP_200_OK
    ids = {row["id"] for row in r.json()}
    assert str(ap1.pk) in ids
    assert len(ids) == 1


@pytest.mark.django_db
def test_cannot_access_other_provider_detail(provider_a: object, provider_b: object) -> None:
    svc = ServiceFactory(provider=provider_b)
    start = timezone.now() + datetime.timedelta(days=3)
    ap = Appointment.objects.create(
        public_id="AGD-CCCC",
        provider=provider_b,
        service=svc,
        client_name="X",
        client_phone="+5511988880003",
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=60),
        status=Appointment.Status.CONFIRMED,
    )
    client = _auth_client(provider_a.user)
    url = reverse("provider-appointment-detail", kwargs={"pk": ap.pk})
    r = client.get(url)
    assert r.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_manual_create_and_conflict(provider_a: object, service_a: object) -> None:
    client = _auth_client(provider_a.user)
    url = reverse("provider-appointments")
    start = timezone.now() + datetime.timedelta(days=4)
    start = start.replace(hour=14, minute=0, second=0, microsecond=0)
    payload = {
        "service_id": str(service_a.pk),
        "start_datetime": start.isoformat(),
        "client_name": "Cliente Fone",
        "client_phone": "+5511977776666",
        "origin": "phone",
        "notes": "obs",
        "internal_notes": "int",
    }
    r = client.post(url, payload, format="json")
    assert r.status_code == status.HTTP_201_CREATED
    assert r.json()["status"] == "confirmed"
    assert r.json()["origin"] == "phone"

    r2 = client.post(url, payload, format="json")
    assert r2.status_code == status.HTTP_409_CONFLICT


@pytest.mark.django_db
def test_manual_create_invalid_service(
    provider_a: object,
    provider_b: object,
    service_a: object,
) -> None:
    client = _auth_client(provider_a.user)
    url = reverse("provider-appointments")
    start = (timezone.now() + datetime.timedelta(days=5)).replace(
        hour=9, minute=0, second=0, microsecond=0
    )
    wrong_service = ServiceFactory(provider=provider_b)
    r = client.post(
        url,
        {
            "service_id": str(wrong_service.pk),
            "start_datetime": start.isoformat(),
            "client_name": "Z",
            "client_phone": "+5511966665555",
            "origin": "walk_in",
        },
        format="json",
    )
    assert r.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_patch_internal_notes(provider_a: object, service_a: object) -> None:
    start = timezone.now() + datetime.timedelta(days=6)
    ap = Appointment.objects.create(
        public_id="AGD-DDDD",
        provider=provider_a,
        service=service_a,
        client_name="Y",
        client_phone="+5511955554444",
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=60),
        status=Appointment.Status.CONFIRMED,
    )
    client = _auth_client(provider_a.user)
    url = reverse("provider-appointment-detail", kwargs={"pk": ap.pk})
    r = client.patch(url, {"internal_notes": "novo"}, format="json")
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["internal_notes"] == "novo"


@pytest.mark.django_db
def test_confirm_complete_no_show_cancel_flow(provider_a: object, service_a: object) -> None:
    start = timezone.now() + datetime.timedelta(days=7)
    ap = Appointment.objects.create(
        public_id="AGD-EEEE",
        provider=provider_a,
        service=service_a,
        client_name="Y",
        client_phone="+5511944443333",
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=60),
        status=Appointment.Status.PENDING_CONFIRMATION,
    )
    client = _auth_client(provider_a.user)

    r = client.post(reverse("provider-appointment-confirm", kwargs={"pk": ap.pk}))
    assert r.status_code == status.HTTP_200_OK
    assert r.json()["status"] == "confirmed"

    with patch(
        "apps.appointments.provider_views.send_pending_review_requests.delay",
        MagicMock(),
    ) as m_delay:
        r2 = client.post(reverse("provider-appointment-complete", kwargs={"pk": ap.pk}))
    assert r2.status_code == status.HTTP_200_OK
    m_delay.assert_called_once()

    ap2 = Appointment.objects.create(
        public_id="AGD-FFFF",
        provider=provider_a,
        service=service_a,
        client_name="Z",
        client_phone="+5511933332222",
        start_datetime=start + datetime.timedelta(hours=2),
        end_datetime=start + datetime.timedelta(hours=3),
        status=Appointment.Status.CONFIRMED,
    )
    r3 = client.post(reverse("provider-appointment-no-show", kwargs={"pk": ap2.pk}))
    assert r3.status_code == status.HTTP_200_OK
    assert r3.json()["status"] == "no_show"

    ap3 = Appointment.objects.create(
        public_id="AGD-GGGG",
        provider=provider_a,
        service=service_a,
        client_name="W",
        client_phone="+5511922221111",
        start_datetime=start + datetime.timedelta(days=1),
        end_datetime=start + datetime.timedelta(days=1, hours=1),
        status=Appointment.Status.CONFIRMED,
    )
    with patch(
        "apps.appointments.provider_views.notify_client_provider_cancellation.delay",
        MagicMock(),
    ) as c_delay:
        r4 = client.post(
            reverse("provider-appointment-cancel", kwargs={"pk": ap3.pk}),
            {"reason": "imprevisto"},
            format="json",
        )
    assert r4.status_code == status.HTTP_200_OK
    c_delay.assert_called_once_with(str(ap3.pk))


@pytest.mark.django_db
def test_invalid_transitions(provider_a: object, service_a: object) -> None:
    start = timezone.now() + datetime.timedelta(days=8)
    ap = Appointment.objects.create(
        public_id="AGD-HHHH",
        provider=provider_a,
        service=service_a,
        client_name="Q",
        client_phone="+5511911110000",
        start_datetime=start,
        end_datetime=start + datetime.timedelta(minutes=60),
        status=Appointment.Status.CANCELLED,
    )
    client = _auth_client(provider_a.user)
    r = client.post(reverse("provider-appointment-confirm", kwargs={"pk": ap.pk}))
    assert r.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
