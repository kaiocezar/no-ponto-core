"""URLs de prestadores de serviço."""

from django.urls import include, path

from apps.appointments.provider_views import (
    ProviderAppointmentCancelView,
    ProviderAppointmentCompleteView,
    ProviderAppointmentConfirmView,
    ProviderAppointmentDetailView,
    ProviderAppointmentListCreateView,
    ProviderAppointmentNoShowView,
)
from apps.providers.scheduling_views import (
    ProviderAvailabilityView,
    ScheduleBlockDetailView,
    ScheduleBlockListCreateView,
    WorkingHoursBulkView,
    WorkingHoursDetailView,
    WorkingHoursListCreateView,
)
from apps.providers.views import (
    ProviderMeView,
    ProviderPublishView,
    ProviderUnpublishView,
    PublicProviderProfileView,
)

urlpatterns = [
    path("me/", ProviderMeView.as_view(), name="provider-me"),
    path(
        "me/appointments/",
        ProviderAppointmentListCreateView.as_view(),
        name="provider-appointments",
    ),
    path(
        "me/appointments/<uuid:pk>/",
        ProviderAppointmentDetailView.as_view(),
        name="provider-appointment-detail",
    ),
    path(
        "me/appointments/<uuid:pk>/confirm/",
        ProviderAppointmentConfirmView.as_view(),
        name="provider-appointment-confirm",
    ),
    path(
        "me/appointments/<uuid:pk>/complete/",
        ProviderAppointmentCompleteView.as_view(),
        name="provider-appointment-complete",
    ),
    path(
        "me/appointments/<uuid:pk>/no-show/",
        ProviderAppointmentNoShowView.as_view(),
        name="provider-appointment-no-show",
    ),
    path(
        "me/appointments/<uuid:pk>/cancel/",
        ProviderAppointmentCancelView.as_view(),
        name="provider-appointment-cancel",
    ),
    path("me/services/", include("apps.services.urls")),
    path("me/publish/", ProviderPublishView.as_view(), name="provider-publish"),
    path("me/unpublish/", ProviderUnpublishView.as_view(), name="provider-unpublish"),
    # Working Hours
    path("me/working-hours/", WorkingHoursListCreateView.as_view(), name="provider-working-hours"),
    path(
        "me/working-hours/bulk/", WorkingHoursBulkView.as_view(), name="provider-working-hours-bulk"
    ),
    path(
        "me/working-hours/<uuid:pk>/",
        WorkingHoursDetailView.as_view(),
        name="provider-working-hours-detail",
    ),
    # Schedule Blocks
    path("me/blocks/", ScheduleBlockListCreateView.as_view(), name="provider-schedule-blocks"),
    path(
        "me/blocks/<uuid:pk>/",
        ScheduleBlockDetailView.as_view(),
        name="provider-schedule-block-detail",
    ),
    # Public availability
    path(
        "<slug:slug>/availability/",
        ProviderAvailabilityView.as_view(),
        name="provider-availability",
    ),
    # /:slug deve ser a última para não conflitar com as anteriores
    path("<slug:slug>/", PublicProviderProfileView.as_view(), name="provider-public"),
]
