"""Health check endpoint."""

from django.db import connection
from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from django.urls import path


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([])
def health_check(request: Request) -> Response:
    """
    Verifica a saúde do sistema: banco de dados e Redis.
    Usado por load balancers e monitoramento.
    """
    checks: dict[str, str] = {}

    # Banco de dados
    try:
        connection.ensure_connection()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    # Redis / Cache
    try:
        cache.set("health_check", "ok", timeout=5)
        result = cache.get("health_check")
        checks["cache"] = "ok" if result == "ok" else "error"
    except Exception:
        checks["cache"] = "error"

    status_code = 200 if all(v == "ok" for v in checks.values()) else 503

    return Response({"status": "healthy" if status_code == 200 else "unhealthy", **checks}, status=status_code)


urlpatterns = [
    path("", health_check, name="health-check"),
]
