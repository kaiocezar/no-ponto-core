"""URLs do app webhooks."""

from django.urls import path

from apps.webhooks.views import WhatsAppWebhookView

urlpatterns = [
    path("whatsapp/", WhatsAppWebhookView.as_view(), name="whatsapp-webhook"),
]
