"""URLs de serviços do prestador."""

from django.urls import path

from apps.services.views import ProviderServiceDetailView, ProviderServiceListCreateView

urlpatterns = [
    path("", ProviderServiceListCreateView.as_view(), name="provider-services"),
    path("<uuid:pk>/", ProviderServiceDetailView.as_view(), name="provider-service-detail"),
]
