"""Models de prestadores de serviço."""

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class ServiceCategory(models.Model):
    """Categoria de serviço (ex: Saúde, Beleza, Consultoria)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    icon = models.CharField(max_length=50, blank=True)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]
        db_table = "providers_service_category"
        verbose_name = "Categoria de Serviço"
        verbose_name_plural = "Categorias de Serviço"

    def __str__(self) -> str:
        return self.name


class ProviderProfile(models.Model):
    """Perfil público de um prestador de serviço."""

    RESERVED_SLUGS: frozenset[str] = frozenset(
        {"api", "admin", "www", "app", "painel", "login", "cadastro"}
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="provider_profile",
    )
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    business_name = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    specialty = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(
        ServiceCategory,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="providers",
    )
    logo_url = models.URLField(max_length=500, null=True, blank=True)
    cover_url = models.URLField(max_length=500, null=True, blank=True)

    # Endereço
    address_street = models.CharField(max_length=200, blank=True)
    address_city = models.CharField(max_length=200, blank=True)
    address_state = models.CharField(max_length=200, blank=True)
    address_zip = models.CharField(max_length=10, blank=True)
    address_lat = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )
    address_lng = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True
    )

    # Configurações de agendamento
    timezone = models.CharField(max_length=50, default="America/Sao_Paulo")
    default_appointment_duration = models.PositiveSmallIntegerField(default=60)
    default_buffer_time = models.PositiveSmallIntegerField(default=0)
    max_advance_days = models.PositiveSmallIntegerField(default=60)
    min_notice_hours = models.PositiveSmallIntegerField(default=2)

    # Contato / redes sociais
    whatsapp_number = models.CharField(max_length=20, blank=True)
    instagram_handle = models.CharField(max_length=100, blank=True)
    website_url = models.URLField(max_length=500, null=True, blank=True)

    is_published = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "providers_provider_profile"
        verbose_name = "Perfil de Prestador"
        verbose_name_plural = "Perfis de Prestadores"
        indexes = [
            models.Index(fields=["is_published", "slug"]),
        ]

    def __str__(self) -> str:
        return self.business_name or str(self.user)

    @classmethod
    def generate_unique_slug(
        cls,
        business_name: str,
        check_reserved_only: bool = False,
    ) -> str:
        """
        Gera um slug único a partir do nome do negócio.

        Levanta ValidationError se o slug for reservado.
        Se check_reserved_only=True, apenas verifica reservadas (sem consultar o banco).
        Adiciona sufixo numérico em caso de colisão no banco.
        """
        base_slug = slugify(business_name)

        if not base_slug:
            raise ValidationError("O nome do negócio não pode gerar um slug vazio.")

        if base_slug in cls.RESERVED_SLUGS:
            raise ValidationError(
                f'O nome "{business_name}" não é permitido pois gera um slug reservado.'
            )

        if check_reserved_only:
            return base_slug

        candidate = base_slug
        counter = 2
        while cls.objects.filter(slug=candidate).exists():
            candidate = f"{base_slug}-{counter}"
            counter += 1

        return candidate

    def save(self, *args: object, **kwargs: object) -> None:
        if not self.slug and self.business_name:
            self.slug = self.generate_unique_slug(self.business_name)
        super().save(*args, **kwargs)


class WorkingHours(models.Model):
    """Horário de funcionamento de um prestador ou profissional."""

    WEEKDAY_CHOICES = [
        (0, "Segunda-feira"),
        (1, "Terça-feira"),
        (2, "Quarta-feira"),
        (3, "Quinta-feira"),
        (4, "Sexta-feira"),
        (5, "Sábado"),
        (6, "Domingo"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        ProviderProfile,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="working_hours",
    )
    staff = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="working_hours",
    )
    weekday = models.SmallIntegerField(choices=WEEKDAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "providers_working_hours"
        verbose_name = "Horário de Funcionamento"
        verbose_name_plural = "Horários de Funcionamento"
        indexes = [
            models.Index(fields=["provider", "weekday", "is_active"]),
            models.Index(fields=["staff", "weekday", "is_active"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(start_time__lt=models.F("end_time")),
                name="working_hours_start_before_end",
            )
        ]

    def __str__(self) -> str:
        return f"{self.get_weekday_display()} {self.start_time}–{self.end_time}"


class ScheduleBlock(models.Model):
    """Bloqueio de agenda — período em que o prestador/profissional não atende."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        ProviderProfile,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="schedule_blocks",
    )
    staff = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="schedule_blocks",
    )
    start_datetime = models.DateTimeField()
    end_datetime = models.DateTimeField()
    reason = models.CharField(max_length=500, blank=True)
    is_recurring = models.BooleanField(default=False)
    recurrence_rule = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "providers_schedule_block"
        verbose_name = "Bloqueio de Agenda"
        verbose_name_plural = "Bloqueios de Agenda"
        indexes = [
            models.Index(fields=["provider", "start_datetime", "end_datetime"]),
            models.Index(fields=["staff", "start_datetime", "end_datetime"]),
        ]

    def __str__(self) -> str:
        return f"Bloqueio {self.start_datetime} → {self.end_datetime}"
