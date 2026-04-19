"""Cliente WhatsApp Cloud API (Meta)."""

from __future__ import annotations

import httpx
from django.conf import settings


class MetaWhatsAppClient:
    """Implementacao real para envio de templates no WhatsApp Cloud API."""

    def __init__(self) -> None:
        self._url = f"https://graph.facebook.com/v19.0/{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"

    def send_template(
        self,
        to: str,
        template_name: str,
        variables: dict[str, str],
        buttons: list[str] | None = None,
    ) -> dict[str, str]:
        components: list[dict[str, object]] = []
        if variables:
            components.append(
                {
                    "type": "body",
                    "parameters": [{"type": "text", "text": value} for value in variables.values()],
                }
            )
        if buttons:
            for index, button_payload in enumerate(buttons):
                components.append(
                    {
                        "type": "button",
                        "sub_type": "quick_reply",
                        "index": str(index),
                        "parameters": [{"type": "payload", "payload": button_payload}],
                    }
                )

        payload: dict[str, object] = {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": "pt_BR"},
                "components": components,
            },
        }
        response = httpx.post(
            self._url,
            headers={
                "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=15.0,
        )
        response.raise_for_status()
        data = response.json()
        external_id = ""
        if isinstance(data.get("messages"), list) and data["messages"]:
            external_id = str(data["messages"][0].get("id", ""))
        return {"external_id": external_id, "provider": "meta"}
