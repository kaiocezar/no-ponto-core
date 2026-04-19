"""Serviços de autenticação OTP para clientes."""

from __future__ import annotations

import secrets
from datetime import timedelta
from typing import TypedDict

import phonenumbers
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import OTPCode, User
from apps.appointments.models import Appointment
from core.exceptions import (
    OTPExpiredError,
    OTPInvalidError,
    OTPMaxAttemptsError,
    RateLimitExceededError,
)

OTP_TTL_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
OTP_RATE_LIMIT_WINDOW_MINUTES = 10
OTP_RATE_LIMIT_MAX_REQUESTS = 5


class OTPVerifyResult(TypedDict):
    user: User
    is_new_user: bool


def normalize_phone_e164(phone: str) -> str:
    """Valida e retorna telefone em formato E.164."""
    try:
        parsed = phonenumbers.parse(phone, None)
    except phonenumbers.NumberParseException as exc:
        raise OTPInvalidError(detail="Telefone inválido. Use formato E.164.") from exc
    if not phonenumbers.is_valid_number(parsed):
        raise OTPInvalidError(detail="Telefone inválido. Use formato E.164.")
    return phonenumbers.format_number(parsed, phonenumbers.PhoneNumberFormat.E164)


def generate_otp(phone: str, purpose: str = OTPCode.Purpose.LOGIN) -> tuple[str, str]:
    """Gera OTP para telefone em E.164, com rate-limit e invalidação prévia."""
    phone_e164 = normalize_phone_e164(phone)
    threshold = timezone.now() - timedelta(minutes=OTP_RATE_LIMIT_WINDOW_MINUTES)
    recent_count = OTPCode.objects.filter(identifier=phone_e164, created_at__gte=threshold).count()
    if recent_count >= OTP_RATE_LIMIT_MAX_REQUESTS:
        raise RateLimitExceededError(detail="Muitas tentativas. Aguarde 10 minutos.")

    OTPCode.objects.filter(identifier=phone_e164, is_used=False).update(is_used=True)

    raw_code = f"{secrets.randbelow(1_000_000):06d}"
    OTPCode.objects.create(
        identifier=phone_e164,
        code=make_password(raw_code),
        purpose=purpose,
        expires_at=timezone.now() + timedelta(minutes=OTP_TTL_MINUTES),
    )
    return phone_e164, raw_code


def verify_otp(phone: str, code: str) -> OTPVerifyResult:
    """Verifica OTP, cria/login usuário cliente e vincula agendamentos órfãos."""
    phone_e164 = normalize_phone_e164(phone)
    otp = (
        OTPCode.objects.filter(identifier=phone_e164, is_used=False).order_by("-created_at").first()
    )
    if otp is None:
        raise OTPExpiredError(detail="Código expirado. Solicite um novo.")
    if otp.attempts >= OTP_MAX_ATTEMPTS:
        raise OTPMaxAttemptsError(detail="Máximo de tentativas excedido.")
    if otp.expires_at < timezone.now():
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        raise OTPExpiredError(detail="Código expirado. Solicite um novo.")
    if not check_password(code, otp.code):
        otp.attempts += 1
        otp.save(update_fields=["attempts"])
        raise OTPInvalidError(detail="Código inválido.")

    with transaction.atomic():
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        user, created = User.objects.get_or_create(
            phone_number=phone_e164,
            defaults={
                "role": User.Role.CLIENT,
                "auth_provider": User.AuthProvider.WHATSAPP_OTP,
                "phone_verified": True,
            },
        )
        if not created:
            update_fields: list[str] = []
            if not user.phone_verified:
                user.phone_verified = True
                update_fields.append("phone_verified")
            user.last_login_at = timezone.now()
            update_fields.append("last_login_at")
            user.save(update_fields=update_fields)
        else:
            user.last_login_at = timezone.now()
            user.save(update_fields=["last_login_at"])

        Appointment.objects.filter(client_phone=phone_e164, client__isnull=True).update(client=user)

    return {"user": user, "is_new_user": created}
