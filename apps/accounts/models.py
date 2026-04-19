"""Models de usuário e autenticação."""

import uuid

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager["User"]):
    def create_user(
        self,
        email: str | None = None,
        phone_number: str | None = None,
        password: str | None = None,
        **extra_fields: object,
    ) -> "User":
        if not email and not phone_number:
            raise ValueError("Usuário deve ter email ou telefone.")
        if email:
            email = self.normalize_email(email)
        user = self.model(email=email, phone_number=phone_number, **extra_fields)
        if password:
            user.set_password(password)
        else:
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_superuser(self, email: str, password: str, **extra_fields: object) -> "User":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", User.Role.ADMIN)
        return self.create_user(email=email, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CLIENT = "client", "Cliente"
        PROVIDER = "provider", "Prestador"
        ADMIN = "admin", "Administrador"
        STAFF = "staff", "Colaborador"

    class AuthProvider(models.TextChoices):
        EMAIL = "email", "Email"
        GOOGLE = "google", "Google"
        APPLE = "apple", "Apple"
        WHATSAPP_OTP = "whatsapp_otp", "WhatsApp OTP"
        PHONE_OTP = "phone_otp", "SMS OTP"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, null=True, blank=True)
    phone_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    phone_verified = models.BooleanField(default=False)
    email_verified = models.BooleanField(default=False)
    full_name = models.CharField(max_length=200, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    avatar_url = models.URLField(max_length=500, null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLIENT)
    auth_provider = models.CharField(
        max_length=20, choices=AuthProvider.choices, default=AuthProvider.EMAIL
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)  # Soft delete (LGPD)
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    objects: UserManager = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        db_table = "accounts_user"
        verbose_name = "Usuário"
        verbose_name_plural = "Usuários"
        indexes = [
            models.Index(fields=["phone_number"]),
            models.Index(fields=["role"]),
        ]

    def __str__(self) -> str:
        return self.full_name or self.email or self.phone_number or str(self.id)

    def anonymize(self) -> None:
        """Anonimiza dados pessoais (LGPD — direito ao esquecimento)."""
        self.email = None
        self.phone_number = None
        self.full_name = f"Usuário deletado {self.id}"
        self.avatar_url = None
        self.is_deleted = True
        self.is_active = False
        self.save()


class OTPCode(models.Model):
    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"
        SIGNUP = "signup", "Cadastro"
        PHONE_VERIFY = "phone_verify", "Verificação de telefone"
        EMAIL_VERIFY = "email_verify", "Verificação de email"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    identifier = models.CharField(max_length=255)  # phone ou email
    code = models.CharField(max_length=255)  # hash argon2 — nunca texto claro
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    is_used = models.BooleanField(default=False)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "accounts_otp_code"
        verbose_name = "Código OTP"
        verbose_name_plural = "Códigos OTP"
        indexes = [
            models.Index(fields=["identifier", "is_used", "expires_at"]),
        ]

    def __str__(self) -> str:
        return f"OTP {self.purpose} para {self.identifier}"

    @property
    def is_expired(self) -> bool:
        return timezone.now() > self.expires_at
