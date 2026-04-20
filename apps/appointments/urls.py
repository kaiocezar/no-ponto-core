"""URLs do app appointments."""

from django.urls import path

from apps.appointments.views import (
    AppointmentCancelByCodeView,
    AppointmentCompleteView,
    AppointmentCreateView,
    AppointmentLookupView,
    AppointmentRescheduleOptionsView,
    AppointmentRescheduleView,
)

urlpatterns = [
    path("", AppointmentCreateView.as_view(), name="appointment-create"),
    path("lookup/", AppointmentLookupView.as_view(), name="appointment-lookup"),
    path(
        "cancel-by-code/",
        AppointmentCancelByCodeView.as_view(),
        name="appointment-cancel-by-code",
    ),
    path(
        "<uuid:pk>/reschedule-options/",
        AppointmentRescheduleOptionsView.as_view(),
        name="appointment-reschedule-options",
    ),
    path(
        "<uuid:pk>/reschedule/",
        AppointmentRescheduleView.as_view(),
        name="appointment-reschedule",
    ),
    path(
        "<uuid:pk>/complete/",
        AppointmentCompleteView.as_view(),
        name="appointment-complete",
    ),
]
