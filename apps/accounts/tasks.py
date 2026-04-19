"""Tasks Celery para autenticação OTP."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.utils import timezone

from apps.accounts.models import OTPCode
from apps.notifications.whatsapp import get_whatsapp_client
from celery import shared_task

logger = logging.getLogger(__name__)


@shared_task(bind=True, ignore_result=True, max_retries=2)
def send_whatsapp_otp(self, phone: str, code: str) -> None:  # type: ignore[override]
    """Envia OTP por WhatsApp e aciona fallback SMS quando retries esgotarem."""
    try:
        get_whatsapp_client().send_template(
            to=phone,
            template_name="otp_login",
            variables={"otp_code": code},
        )
    except Exception as exc:
        if self.request.retries >= self.max_retries:
            logger.warning("Falha envio OTP WhatsApp para %s; acionando fallback SMS", phone)
            send_sms_otp.delay(phone, code)
            return
        raise self.retry(exc=exc, countdown=30) from exc


@shared_task(ignore_result=True)
def send_sms_otp(phone: str, code: str) -> None:
    """Stub de envio SMS para MVP."""
    logger.warning("SMS OTP stub: phone=%s code=%s", phone, code)


@shared_task(ignore_result=True)
def cleanup_expired_otps() -> None:
    """Remove OTPs expirados há mais de 24 horas."""
    cutoff = timezone.now() - timedelta(hours=24)
    OTPCode.objects.filter(expires_at__lt=cutoff).delete()
