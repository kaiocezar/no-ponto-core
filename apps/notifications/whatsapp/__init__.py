"""Factory de cliente WhatsApp."""

from __future__ import annotations

from django.conf import settings

from apps.notifications.whatsapp.base import WhatsAppClient
from apps.notifications.whatsapp.evolution import EvolutionWhatsAppClient
from apps.notifications.whatsapp.meta import MetaWhatsAppClient


def get_whatsapp_client() -> WhatsAppClient:
    if settings.WHATSAPP_BACKEND == "evolution":
        return EvolutionWhatsAppClient()
    return MetaWhatsAppClient()
