"""Views de autenticação e cadastro."""

from django.db import transaction
from rest_framework import status
from rest_framework.generics import CreateAPIView, GenericAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import (
    ClientMeSerializer,
    CompleteProfileSerializer,
    ProviderRegisterSerializer,
    RequestOTPSerializer,
    VerifyOTPSerializer,
)
from apps.accounts.services import generate_otp, verify_otp
from core.permissions import IsClientUser


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


class RequestOTPView(GenericAPIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "otp_request"
    serializer_class = RequestOTPSerializer

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        phone, code = generate_otp(serializer.validated_data["phone"])
        from apps.accounts.tasks import send_whatsapp_otp

        send_whatsapp_otp.delay(phone, code)
        return Response({"otp_sent": True}, status=status.HTTP_200_OK)


class VerifyOTPView(GenericAPIView):
    permission_classes = [AllowAny]
    serializer_class = VerifyOTPSerializer

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            result = verify_otp(
                phone=serializer.validated_data["phone"],
                code=serializer.validated_data["code"],
            )
        refresh = RefreshToken.for_user(result["user"])
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "is_new_user": result["is_new_user"],
            },
            status=status.HTTP_200_OK,
        )


class CompleteProfileView(GenericAPIView):
    permission_classes = [IsClientUser]
    serializer_class = CompleteProfileSerializer

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        request.user.full_name = serializer.validated_data["full_name"].strip()
        request.user.save(update_fields=["full_name"])
        return Response({"full_name": request.user.full_name}, status=status.HTTP_200_OK)


class ClientMeView(UpdateAPIView):
    permission_classes = [IsClientUser]
    serializer_class = ClientMeSerializer
    http_method_names = ["patch"]

    def get_object(self) -> object:
        return self.request.user

    def patch(self, request: Request, *args: object, **kwargs: object) -> Response:
        return self.partial_update(request, *args, **kwargs)
