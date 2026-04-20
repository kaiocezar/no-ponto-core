"""URLs de serviços do prestador."""

from django.urls import path

from apps.services.views import (
    ProviderServiceActivateView,
    ProviderServiceDeactivateView,
    ProviderServiceDetailView,
    ProviderServiceListCreateView,
)

urlpatterns = [
    path("", ProviderServiceListCreateView.as_view(), name="provider-services"),
    path("<uuid:pk>/", ProviderServiceDetailView.as_view(), name="provider-service-detail"),
    path(
        "<uuid:pk>/activate/",
        ProviderServiceActivateView.as_view(),
        name="provider-service-activate",
    ),
    path(
        "<uuid:pk>/deactivate/",
        ProviderServiceDeactivateView.as_view(),
        name="provider-service-deactivate",
    ),
]
