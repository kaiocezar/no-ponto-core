"""Abstracao de cliente WhatsApp."""

from __future__ import annotations

from typing import Protocol


class WhatsAppClient(Protocol):
    def send_template(
        self,
        to: str,
        template_name: str,
        variables: dict[str, str],
        buttons: list[str] | None = None,
    ) -> dict[str, str]: ...
