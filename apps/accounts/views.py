"""Views de autenticação e cadastro."""

from __future__ import annotations

from django.db import models, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.generics import CreateAPIView, GenericAPIView, ListAPIView, UpdateAPIView
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken

from apps.accounts.serializers import (
    ClientMeSerializer,
    CompleteProfileSerializer,
    MyAppointmentSerializer,
    ProviderRegisterSerializer,
    RequestOTPSerializer,
    VerifyOTPSerializer,
)
from apps.appointments.models import Appointment
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


class ValidateInviteView(GenericAPIView):
    """
    GET /api/v1/accounts/accept-invite/?token=

    Valida o token de convite sem consumi-lo.
    Retorna dados do convite (nome, email, provider) ou 404/410.
    Sem autenticação.
    """

    permission_classes = [AllowAny]

    def get(self, request: Request, *args: object, **kwargs: object) -> Response:
        from apps.providers.models import Staff

        token = request.query_params.get("token", "").strip()
        if not token:
            return Response(
                {"detail": "Parâmetro token é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            import uuid

            staff = Staff.objects.select_related("provider", "user").get(
                invite_token=uuid.UUID(token)
            )
        except (Staff.DoesNotExist, ValueError):
            return Response(
                {"detail": "Convite não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if staff.user is not None:
            return Response(
                {"detail": "Este convite já foi aceito."},
                status=status.HTTP_410_GONE,
            )

        if staff.invite_expires_at and timezone.now() > staff.invite_expires_at:
            return Response(
                {"detail": "Este convite expirou. Solicite um novo ao administrador."},
                status=status.HTTP_410_GONE,
            )

        return Response(
            {
                "staff_id": str(staff.pk),
                "name": staff.name,
                "invite_email": staff.invite_email,
                "role": staff.role,
                "provider_name": staff.provider.business_name or str(staff.provider),
            }
        )


class AcceptInviteView(GenericAPIView):
    """
    POST /api/v1/accounts/accept-invite/

    Aceita o convite de Staff:
    - Se o usuário está autenticado via JWT, vincula o Staff ao usuário existente.
    - Caso contrário, cria um novo User com email/senha informados e vincula.

    Body: { token, full_name (opcional), password (opcional) }
    """

    permission_classes = [AllowAny]

    def post(self, request: Request, *args: object, **kwargs: object) -> Response:
        import uuid as _uuid

        from apps.accounts.models import User
        from apps.providers.models import Staff

        token_str = (request.data.get("token") or "").strip()
        if not token_str:
            return Response(
                {"detail": "Campo token é obrigatório."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            staff = Staff.objects.select_related("provider", "user").get(
                invite_token=_uuid.UUID(token_str)
            )
        except (Staff.DoesNotExist, ValueError):
            return Response(
                {"detail": "Convite não encontrado."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if staff.user is not None:
            return Response(
                {"detail": "Este convite já foi aceito."},
                status=status.HTTP_410_GONE,
            )

        if staff.invite_expires_at and timezone.now() > staff.invite_expires_at:
            return Response(
                {"detail": "Este convite expirou."},
                status=status.HTTP_410_GONE,
            )

        with transaction.atomic():
            # Usuário autenticado — vincula ao Staff existente
            if request.user and request.user.is_authenticated:
                user = request.user
            else:
                # Novo usuário — exige full_name e password
                full_name = (request.data.get("full_name") or "").strip()
                password = request.data.get("password", "")
                if not full_name:
                    return Response(
                        {"detail": "Informe full_name para criar sua conta."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                if not password or len(str(password)) < 8:
                    return Response(
                        {"detail": "A senha deve ter ao menos 8 caracteres."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )
                # Verifica se já existe conta com esse email
                email = staff.invite_email
                existing = User.objects.filter(email=email).first() if email else None
                if existing:
                    # Vincula ao User existente sem alterar senha
                    user = existing
                else:
                    user = User.objects.create_user(
                        email=email,
                        password=str(password),
                        full_name=full_name,
                        role=User.Role.STAFF,
                        auth_provider=User.AuthProvider.EMAIL,
                    )

            staff.user = user
            staff.invite_token = None
            staff.invite_expires_at = None
            staff.save(update_fields=["user", "invite_token", "invite_expires_at", "updated_at"])

        refresh: RefreshToken = RefreshToken.for_user(user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "staff_id": str(staff.pk),
                "provider_name": staff.provider.business_name or str(staff.provider),
            },
            status=status.HTTP_200_OK,
        )


class MyAppointmentsView(ListAPIView):
    permission_classes = [IsClientUser]
    serializer_class = MyAppointmentSerializer

    def get_queryset(self):  # type: ignore[no-untyped-def]
        status_filter = self.request.query_params.get("status", "upcoming")
        now = timezone.now()
        qs = (
            Appointment.objects.filter(client=self.request.user)
            .select_related("service", "provider", "review")
            .order_by("start_datetime")
        )
        if status_filter == "past":
            return qs.filter(
                models.Q(start_datetime__lt=now)
                | models.Q(
                    status__in=[
                        Appointment.Status.COMPLETED,
                        Appointment.Status.CANCELLED,
                        Appointment.Status.NO_SHOW,
                    ]
                )
            ).order_by("-start_datetime")
        return qs.filter(start_datetime__gte=now).exclude(
            status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW]
        )
