"""URLs do app appointments."""

from django.urls import path

from apps.appointments.views import AppointmentCreateView, AppointmentLookupView

urlpatterns = [
    path("", AppointmentCreateView.as_view(), name="appointment-create"),
    path("lookup/", AppointmentLookupView.as_view(), name="appointment-lookup"),
]
