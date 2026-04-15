"""URLs de prestadores de serviço."""

from django.urls import path

from apps.providers.views import (
    ProviderMeView,
    ProviderPublishView,
    ProviderUnpublishView,
    PublicProviderProfileView,
)

urlpatterns = [
    path("me/", ProviderMeView.as_view(), name="provider-me"),
    path("me/publish/", ProviderPublishView.as_view(), name="provider-publish"),
    path("me/unpublish/", ProviderUnpublishView.as_view(), name="provider-unpublish"),
    path("<slug:slug>/", PublicProviderProfileView.as_view(), name="provider-public"),
]
