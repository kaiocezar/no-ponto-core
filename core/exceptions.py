"""Handler de exceções customizado para a API."""

from typing import Any

from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import exception_handler


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    """
    Handler customizado que formata todas as respostas de erro no padrão:

    {
        "error": {
            "code": "SLOT_NOT_AVAILABLE",
            "message": "O horário selecionado não está disponível.",
            "details": {...}
        }
    }
    """
    # Converte Http404 do Django para NotFound do DRF
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()

    response = exception_handler(exc, context)

    if response is not None:
        error_code = _get_error_code(exc)
        message = _get_message(exc, response)
        details = _get_details(response)

        response.data = {
            "error": {
                "code": error_code,
                "message": message,
                **({"details": details} if details else {}),
            }
        }

    return response


def _get_error_code(exc: Exception) -> str:
    if isinstance(exc, SlotNotAvailableError):
        return "slot_not_available"
    if isinstance(exc, ServiceUnavailableError):
        return "service_unavailable"
    if hasattr(exc, "default_code"):
        return str(exc.default_code).upper()  # type: ignore[union-attr]
    if isinstance(exc, exceptions.NotFound):
        return "NOT_FOUND"
    if isinstance(exc, exceptions.PermissionDenied):
        return "PERMISSION_DENIED"
    if isinstance(exc, exceptions.AuthenticationFailed):
        return "AUTHENTICATION_FAILED"
    if isinstance(exc, exceptions.ValidationError):
        return "VALIDATION_ERROR"
    return "SERVER_ERROR"


def _get_message(exc: Exception, response: Response) -> str:
    if isinstance(exc, exceptions.ValidationError):
        return "Dados inválidos. Verifique os campos e tente novamente."
    if isinstance(response.data, dict) and "detail" in response.data:
        return str(response.data["detail"])
    return "Ocorreu um erro. Tente novamente."


def _get_details(response: Response) -> dict[str, Any] | None:
    data = response.data
    if isinstance(data, dict) and "detail" not in data and "error" not in data:
        return data
    return None


# ── Exceções de negócio customizadas ─────────────────────────────────────────


class SlotNotAvailableError(exceptions.APIException):
    status_code = status.HTTP_409_CONFLICT
    default_code = "slot_not_available"
    default_detail = "O horário selecionado não está mais disponível."


class ServiceUnavailableError(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "service_unavailable"
    default_detail = "Serviço indisponível para agendamento."


class OTPExpiredError(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "OTP_EXPIRED"
    default_detail = "O código expirou. Solicite um novo código."


class OTPInvalidError(exceptions.APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "OTP_INVALID"
    default_detail = "Código inválido."


class OTPMaxAttemptsError(exceptions.APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "OTP_MAX_ATTEMPTS"
    default_detail = "Muitas tentativas. Solicite um novo código."


class RateLimitExceededError(exceptions.APIException):
    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    default_code = "RATE_LIMIT_EXCEEDED"
    default_detail = "Muitas requisições. Aguarde e tente novamente."
