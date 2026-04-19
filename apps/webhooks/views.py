"""Views de webhook do WhatsApp."""

from __future__ import annotations

import hashlib
import hmac
import json

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.webhooks.models import WhatsAppInboundMessage
from apps.webhooks.tasks import process_whatsapp_response


def verify_whatsapp_signature(request: HttpRequest) -> bool:
    header_signature = request.headers.get("X-Hub-Signature-256", "")
    if not header_signature.startswith("sha256="):
        return False
    payload = request.body
    expected_signature = hmac.new(
        settings.WHATSAPP_APP_SECRET.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(header_signature, f"sha256={expected_signature}")


def _extract_message_payload(raw_data: bytes) -> tuple[str, str, str, str, str]:
    data = json.loads(raw_data.decode("utf-8"))
    entry = data.get("entry", [{}])[0]
    change = entry.get("changes", [{}])[0]
    value = change.get("value", {})
    message = value.get("messages", [{}])[0]
    wamid = str(message.get("id", ""))
    from_phone = str(message.get("from", ""))
    message_type = str(message.get("type", ""))
    body = str(message.get("text", {}).get("body", ""))
    button_payload = str(message.get("button", {}).get("payload", ""))
    if not button_payload:
        button_payload = str(message.get("interactive", {}).get("button_reply", {}).get("id", ""))
    return wamid, from_phone, message_type, body, button_payload


class WhatsAppWebhookView(APIView):
    permission_classes = [AllowAny]

    def get(self, request: Request, *args: object, **kwargs: object) -> HttpResponse:
        mode = request.query_params.get("hub.mode")
        verify_token = request.query_params.get("hub.verify_token")
        challenge = request.query_params.get("hub.challenge", "")
        if mode == "subscribe" and verify_token == settings.WHATSAPP_VERIFY_TOKEN:
            return HttpResponse(challenge, status=200)
        return HttpResponse("forbidden", status=403)

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        django_request = request._request
        if not verify_whatsapp_signature(django_request):
            return Response({"detail": "invalid signature"}, status=status.HTTP_403_FORBIDDEN)

        try:
            wamid, from_phone, message_type, body, button_payload = _extract_message_payload(
                django_request.body
            )
        except (KeyError, IndexError, ValueError, json.JSONDecodeError):
            return Response({"detail": "ignored"}, status=status.HTTP_200_OK)

        if not wamid:
            return Response({"detail": "ignored"}, status=status.HTTP_200_OK)

        inbound, created = WhatsAppInboundMessage.objects.get_or_create(
            wamid=wamid,
            defaults={
                "from_phone": from_phone,
                "message_type": message_type,
                "body": body,
                "button_payload": button_payload,
            },
        )
        if created:
            process_whatsapp_response.delay(wamid)
        return Response({"status": "ok", "processed": inbound.processed}, status=status.HTTP_200_OK)
