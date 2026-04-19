"""Testes para extração de payload do webhook WhatsApp."""

from __future__ import annotations

import json

from apps.webhooks.views import _extract_message_payload


def _build_payload(message: dict[str, object]) -> bytes:
    return json.dumps(
        {
            "entry": [
                {
                    "changes": [
                        {
                            "value": {
                                "messages": [message],
                            },
                        },
                    ],
                },
            ],
        },
    ).encode("utf-8")


def test_extract_message_payload_uses_list_reply_id() -> None:
    raw = _build_payload(
        {
            "id": "wamid-1",
            "from": "5511999990001",
            "type": "interactive",
            "interactive": {"list_reply": {"id": "RESCHEDULED_abc_2026-10-01T10:00:00Z"}},
        },
    )

    _, _, _, _, button_payload = _extract_message_payload(raw)
    assert button_payload == "RESCHEDULED_abc_2026-10-01T10:00:00Z"


def test_extract_message_payload_fallbacks_to_list_reply_row_id() -> None:
    raw = _build_payload(
        {
            "id": "wamid-2",
            "from": "5511999990002",
            "type": "interactive",
            "interactive": {"list_reply": {"row_id": "RESCHEDULED_def_2026-10-01T11:00:00Z"}},
        },
    )

    _, _, _, _, button_payload = _extract_message_payload(raw)
    assert button_payload == "RESCHEDULED_def_2026-10-01T11:00:00Z"
