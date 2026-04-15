"""URL configuration raiz do projeto."""

from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static

from apps.providers.views import ServiceCategoryListView

api_v1_patterns = [
    path("accounts/", include("apps.accounts.urls")),
    path("providers/", include("apps.providers.urls")),
    path("categories/", ServiceCategoryListView.as_view(), name="categories"),
    path("services/", include("apps.services.urls")),
    path("appointments/", include("apps.appointments.urls")),
    path("reviews/", include("apps.reviews.urls")),
    path("webhooks/", include("apps.webhooks.urls")),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include(api_v1_patterns)),
    path("api/health/", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
