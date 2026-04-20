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
from apps.providers.staff_views import (
    PublicProviderStaffView,
    StaffDetailView,
    StaffListCreateView,
    StaffResendInviteView,
)
from apps.providers.views import (
    ClientAppointmentHistoryView,
    ClientListView,
    ClientNoteView,
    DashboardView,
    ProviderMeView,
    ProviderPublishView,
    ProviderUnpublishView,
    PublicProviderProfileView,
)
from apps.reviews.views import (
    ProviderReviewListView,
    PublicReviewListView,
    PublicReviewSummaryView,
    ReviewReplyView,
    ReviewToggleVisibilityView,
)
from apps.services.views import PublicProviderServicesView

urlpatterns = [
    path("me/", ProviderMeView.as_view(), name="provider-me"),
    path("me/dashboard/", DashboardView.as_view(), name="provider-dashboard"),
    path("me/clients/", ClientListView.as_view(), name="provider-clients"),
    path(
        "me/clients/<str:phone>/appointments/",
        ClientAppointmentHistoryView.as_view(),
        name="provider-client-appointments",
    ),
    path("me/clients/<str:phone>/notes/", ClientNoteView.as_view(), name="provider-client-notes"),
    path("me/reviews/", ProviderReviewListView.as_view(), name="provider-reviews"),
    path(
        "me/reviews/<uuid:pk>/reply/",
        ReviewReplyView.as_view(),
        name="provider-review-reply",
    ),
    path(
        "me/reviews/<uuid:pk>/toggle-visibility/",
        ReviewToggleVisibilityView.as_view(),
        name="provider-review-toggle-visibility",
    ),
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
    # Staff
    path("me/staff/", StaffListCreateView.as_view(), name="provider-staff"),
    path("me/staff/<uuid:pk>/", StaffDetailView.as_view(), name="provider-staff-detail"),
    path(
        "me/staff/<uuid:pk>/resend-invite/",
        StaffResendInviteView.as_view(),
        name="provider-staff-resend-invite",
    ),
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
    # Public — rotas antes do catch-all <slug>
    path(
        "<slug:slug>/availability/",
        ProviderAvailabilityView.as_view(),
        name="provider-availability",
    ),
    path(
        "<slug:slug>/services/",
        PublicProviderServicesView.as_view(),
        name="provider-public-services",
    ),
    path(
        "<slug:slug>/staff/",
        PublicProviderStaffView.as_view(),
        name="provider-public-staff",
    ),
    path("<slug:slug>/reviews/", PublicReviewListView.as_view(), name="provider-public-reviews"),
    path(
        "<slug:slug>/reviews/summary/",
        PublicReviewSummaryView.as_view(),
        name="provider-public-reviews-summary",
    ),
    # /:slug deve ser a última para não conflitar com as anteriores
    path("<slug:slug>/", PublicProviderProfileView.as_view(), name="provider-public"),
]
