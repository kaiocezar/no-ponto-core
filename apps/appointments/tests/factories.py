"""Factories de agendamentos."""

import datetime
import uuid

import factory
from django.utils import timezone
from factory.django import DjangoModelFactory

from apps.appointments.models import Appointment
from apps.services.tests.factories import ServiceFactory


def _unique_public_id() -> str:
    return f"AGD-{uuid.uuid4().hex[:4].upper()}"


class AppointmentFactory(DjangoModelFactory):
    """Factory de agendamentos para testes."""

    class Meta:
        model = Appointment

    service = factory.SubFactory(ServiceFactory)
    provider = factory.LazyAttribute(lambda o: o.service.provider)
    public_id = factory.LazyFunction(_unique_public_id)
    client_name = factory.Faker("name", locale="pt_BR")
    client_phone = "+5511988887777"
    client_email = ""
    start_datetime = factory.LazyFunction(
        lambda: timezone.now() + datetime.timedelta(days=10),
    )
    end_datetime = factory.LazyAttribute(
        lambda o: o.start_datetime + datetime.timedelta(minutes=o.service.duration),
    )
    status = Appointment.Status.PENDING_CONFIRMATION
    origin = Appointment.Origin.ONLINE
    notes = ""
    internal_notes = ""
    price_at_booking = factory.LazyAttribute(lambda o: o.service.price)
    deposit_paid = False
