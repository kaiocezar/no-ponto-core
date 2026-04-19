"""Testes de autenticação OTP e perfil de cliente."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from django.contrib.auth.hashers import check_password, make_password
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.models import OTPCode
from apps.accounts.services import generate_otp, verify_otp
from apps.accounts.tasks import cleanup_expired_otps, send_whatsapp_otp
from apps.appointments.tests.factories import AppointmentFactory
from core.exceptions import (
    OTPExpiredError,
    OTPInvalidError,
    OTPMaxAttemptsError,
    RateLimitExceededError,
)


@pytest.mark.django_db
class TestOTPServices:
    def test_generate_otp_invalidates_previous_and_hashes(self) -> None:
        OTPCode.objects.create(
            identifier="+5511999990000",
            code=make_password("123456"),
            purpose=OTPCode.Purpose.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        phone, code = generate_otp("+5511999990000")

        assert phone == "+5511999990000"
        latest = OTPCode.objects.order_by("-created_at").first()
        assert latest is not None
        assert check_password(code, latest.code)
        assert OTPCode.objects.filter(identifier=phone, is_used=True).count() == 1

    def test_verify_otp_success_links_orphan_appointments(self) -> None:
        phone = "+5511988887777"
        OTPCode.objects.create(
            identifier=phone,
            code=make_password("123456"),
            purpose=OTPCode.Purpose.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=10),
        )
        orphan = AppointmentFactory(client_phone=phone, client=None)

        result = verify_otp(phone=phone, code="123456")

        assert result["is_new_user"] is True
        orphan.refresh_from_db()
        assert orphan.client_id == result["user"].id

    def test_verify_otp_wrong_code_increments_attempts(self) -> None:
        phone = "+5511999991111"
        otp = OTPCode.objects.create(
            identifier=phone,
            code=make_password("123456"),
            purpose=OTPCode.Purpose.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        with pytest.raises(OTPInvalidError):
            verify_otp(phone=phone, code="000000")

        otp.refresh_from_db()
        assert otp.attempts == 1

    def test_generate_otp_rate_limit(self) -> None:
        phone = "+5511911111111"
        for _ in range(5):
            OTPCode.objects.create(
                identifier=phone,
                code=make_password("123456"),
                purpose=OTPCode.Purpose.LOGIN,
                expires_at=timezone.now() + timedelta(minutes=10),
            )

        with pytest.raises(RateLimitExceededError):
            generate_otp(phone)

    def test_generate_otp_normalizes_e164(self) -> None:
        phone, _code = generate_otp("+55 11 98888-7777")
        assert phone == "+5511988887777"

    def test_verify_otp_expired_code(self) -> None:
        phone = "+5511977776666"
        otp = OTPCode.objects.create(
            identifier=phone,
            code=make_password("123456"),
            purpose=OTPCode.Purpose.LOGIN,
            expires_at=timezone.now() - timedelta(minutes=1),
        )

        with pytest.raises(OTPExpiredError):
            verify_otp(phone=phone, code="123456")

        otp.refresh_from_db()
        assert otp.is_used is True

    def test_verify_otp_max_attempts(self) -> None:
        phone = "+5511966665555"
        OTPCode.objects.create(
            identifier=phone,
            code=make_password("123456"),
            purpose=OTPCode.Purpose.LOGIN,
            attempts=5,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        with pytest.raises(OTPMaxAttemptsError):
            verify_otp(phone=phone, code="123456")

    def test_verify_otp_missing_active_code(self) -> None:
        with pytest.raises(OTPExpiredError):
            verify_otp(phone="+5511991231234", code="123456")


@pytest.mark.django_db
class TestOTPEndpoints:
    def test_request_otp_success(
        self, monkeypatch: pytest.MonkeyPatch, api_client: APIClient
    ) -> None:
        monkeypatch.setattr("apps.accounts.tasks.send_whatsapp_otp.delay", lambda *_args: None)

        response = api_client.post(
            "/api/v1/accounts/request-otp/",
            {"phone": "+5511999992222"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["otp_sent"] is True

    def test_request_otp_invalid_phone(self, api_client: APIClient) -> None:
        response = api_client.post(
            "/api/v1/accounts/request-otp/",
            {"phone": "99999-9999"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_request_otp_rate_limit(self, api_client: APIClient) -> None:
        phone = "+5511999992223"
        for _ in range(5):
            OTPCode.objects.create(
                identifier=phone,
                code=make_password("111111"),
                purpose=OTPCode.Purpose.LOGIN,
                expires_at=timezone.now() + timedelta(minutes=10),
            )

        response = api_client.post("/api/v1/accounts/request-otp/", {"phone": phone}, format="json")
        assert response.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    def test_verify_otp_returns_tokens_and_is_new_user(self, api_client: APIClient) -> None:
        phone = "+5511999993333"
        OTPCode.objects.create(
            identifier=phone,
            code=make_password("654321"),
            purpose=OTPCode.Purpose.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = api_client.post(
            "/api/v1/accounts/verify-otp/",
            {"phone": phone, "code": "654321"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["access"]
        assert response.data["refresh"]
        assert response.data["is_new_user"] is True

    def test_verify_otp_existing_user_returns_is_new_user_false(
        self, api_client: APIClient
    ) -> None:
        phone = "+5511999993334"
        from apps.accounts.models import User

        User.objects.create(
            phone_number=phone,
            role=User.Role.CLIENT,
            auth_provider=User.AuthProvider.WHATSAPP_OTP,
            phone_verified=True,
        )
        OTPCode.objects.create(
            identifier=phone,
            code=make_password("654321"),
            purpose=OTPCode.Purpose.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = api_client.post(
            "/api/v1/accounts/verify-otp/",
            {"phone": phone, "code": "654321"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_new_user"] is False

    def test_verify_otp_wrong_code_returns_error(self, api_client: APIClient) -> None:
        phone = "+5511999993335"
        OTPCode.objects.create(
            identifier=phone,
            code=make_password("654321"),
            purpose=OTPCode.Purpose.LOGIN,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        response = api_client.post(
            "/api/v1/accounts/verify-otp/",
            {"phone": phone, "code": "000000"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_complete_profile_and_me_patch(self, authenticated_client_api: APIClient) -> None:
        complete_response = authenticated_client_api.post(
            "/api/v1/accounts/complete-profile/",
            {"full_name": "Cliente Completo"},
            format="json",
        )
        assert complete_response.status_code == status.HTTP_200_OK

        patch_response = authenticated_client_api.patch(
            "/api/v1/accounts/me/",
            {"birth_date": "1990-05-15"},
            format="json",
        )
        assert patch_response.status_code == status.HTTP_200_OK
        assert patch_response.data["birth_date"] == "1990-05-15"


@pytest.mark.django_db
def test_cleanup_expired_otps() -> None:
    OTPCode.objects.create(
        identifier="+5511999994444",
        code=make_password("111111"),
        purpose=OTPCode.Purpose.LOGIN,
        expires_at=timezone.now() - timedelta(days=2),
    )
    recent = OTPCode.objects.create(
        identifier="+5511999995555",
        code=make_password("222222"),
        purpose=OTPCode.Purpose.LOGIN,
        expires_at=timezone.now() - timedelta(hours=1),
    )

    cleanup_expired_otps()

    assert OTPCode.objects.filter(pk=recent.pk).exists()


@pytest.mark.django_db
class TestWhatsAppTasks:
    def test_send_whatsapp_otp_retries_on_failure(self, monkeypatch: pytest.MonkeyPatch) -> None:
        mock_client = MagicMock()
        mock_client.send_template.side_effect = RuntimeError("whatsapp offline")
        retry_mock = MagicMock(side_effect=RuntimeError("retry"))
        monkeypatch.setattr("apps.accounts.tasks.get_whatsapp_client", lambda: mock_client)
        monkeypatch.setattr(send_whatsapp_otp.request, "retries", 0, raising=False)
        monkeypatch.setattr(send_whatsapp_otp, "retry", retry_mock)

        with pytest.raises(RuntimeError, match="retry"):
            send_whatsapp_otp.run("+5511999996666", "123456")

        retry_mock.assert_called_once()
        assert retry_mock.call_args.kwargs["countdown"] == 30

    def test_send_whatsapp_otp_fallback_sms_after_retries(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        mock_client = MagicMock()
        mock_client.send_template.side_effect = RuntimeError("still failing")
        sms_delay_mock = MagicMock()
        monkeypatch.setattr("apps.accounts.tasks.get_whatsapp_client", lambda: mock_client)
        monkeypatch.setattr(send_whatsapp_otp.request, "retries", 2, raising=False)
        monkeypatch.setattr("apps.accounts.tasks.send_sms_otp.delay", sms_delay_mock)

        send_whatsapp_otp.run("+5511999997777", "123456")

        sms_delay_mock.assert_called_once_with("+5511999997777", "123456")
