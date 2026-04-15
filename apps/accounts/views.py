"""Views de autenticação e cadastro."""

from rest_framework import status
from rest_framework.generics import CreateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from apps.accounts.serializers import ProviderRegisterSerializer


class RegisterProviderView(CreateAPIView):
    """
    POST /api/v1/accounts/register/

    Cadastra um novo prestador de serviço e retorna tokens JWT.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "register"
    serializer_class = ProviderRegisterSerializer

    def create(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.save()
        return Response(data, status=status.HTTP_201_CREATED)
