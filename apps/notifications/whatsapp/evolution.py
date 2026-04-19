"""Cliente WhatsApp para Evolution API em desenvolvimento."""

from __future__ import annotations

import httpx
from django.conf import settings


class EvolutionWhatsAppClient:
    """Converte templates em texto simples para facilitar testes locais."""

    def send_template(
        self,
        to: str,
        template_name: str,
        variables: dict[str, str],
        buttons: list[str] | None = None,
    ) -> dict[str, str]:
        text_parts = [f"template={template_name}"]
        for key, value in variables.items():
            text_parts.append(f"{key}: {value}")
        if buttons:
            text_parts.append(f"buttons: {', '.join(buttons)}")

        response = httpx.post(
            f"{settings.EVOLUTION_API_URL.rstrip('/')}/message/sendText",
            json={"number": to, "text": " | ".join(text_parts)},
            timeout=10.0,
        )
        response.raise_for_status()
        data = response.json()
        external_id = str(data.get("key", {}).get("id", ""))
        return {"external_id": external_id, "provider": "evolution"}
