"""Models de prestadores de serviço."""

import uuid

from django.core.exceptions import ValidationError
from django.db import models
from django.utils.text import slugify


class Staff(models.Model):
    ROLE_CHOICES = [
        ("owner", "Proprietário"),
        ("manager", "Gerente"),
        ("practitioner", "Profissional"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        "providers.ProviderProfile",
        on_delete=models.CASCADE,
        related_name="staff_members",
    )
    user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="staff_roles",
    )
    invite_email = models.EmailField(null=True, blank=True)
    invite_token = models.UUIDField(null=True, blank=True)
    invite_expires_at = models.DateTimeField(null=True, blank=True)
    name = models.CharField(max_length=200)
    avatar_url = models.URLField(max_length=500, null=True, blank=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default="practitioner")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "providers_staff"
        verbose_name = "Membro da Equipe"
        verbose_name_plural = "Membros da Equipe"
        indexes = [
            models.Index(fields=["provider", "is_active"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["invite_token"],
                condition=models.Q(invite_token__isnull=False),
                name="staff_invite_token_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(user__isnull=False) | models.Q(invite_email__isnull=False),
                name="staff_must_have_user_or_email",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.name} ({self.provider})"


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
    address_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    address_lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

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
    average_rating = models.DecimalField(max_digits=3, decimal_places=2, null=True, blank=True)
    total_reviews = models.PositiveIntegerField(default=0)
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

    def save(self, *args: object, **kwargs: object) -> None:
        slug_changed = False
        if not self.slug:
            if self.business_name:
                self.slug = self.generate_unique_slug(self.business_name)
            else:
                # Slug temporário baseado em UUID para perfis sem business_name ainda
                import uuid as _uuid

                self.slug = f"perfil-{str(_uuid.uuid4())[:8]}"
            slug_changed = True
        elif self.business_name and self.slug.startswith("perfil-"):
            # Slug temporário presente — regera com o business_name atual
            self.slug = self.generate_unique_slug(self.business_name)
            slug_changed = True

        # Garante que slug é persistido mesmo quando update_fields está presente
        if slug_changed and "update_fields" in kwargs:
            update_fields = list(kwargs["update_fields"])  # type: ignore[arg-type]
            if "slug" not in update_fields:
                update_fields.append("slug")
            kwargs["update_fields"] = update_fields

        super().save(*args, **kwargs)

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
        "providers.Staff",
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
        return f"{self.get_weekday_display()} {self.start_time}-{self.end_time}"


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
        "providers.Staff",
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


class ServiceStaff(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    service = models.ForeignKey(
        "services.Service",
        on_delete=models.CASCADE,
        related_name="service_staff",
    )
    staff = models.ForeignKey(
        Staff,
        on_delete=models.CASCADE,
        related_name="service_assignments",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "providers_service_staff"
        unique_together = [("service", "staff")]
        verbose_name = "Serviço por Profissional"
        verbose_name_plural = "Serviços por Profissional"

    def __str__(self) -> str:
        return f"{self.staff} → {self.service}"


class ClientNote(models.Model):
    """Nota interna sobre cliente, visivel apenas ao prestador dono."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    provider = models.ForeignKey(
        ProviderProfile,
        on_delete=models.CASCADE,
        related_name="client_notes",
    )
    client_phone = models.CharField(max_length=32, db_index=True)
    client_user = models.ForeignKey(
        "accounts.User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="provider_client_notes",
    )
    note = models.TextField()
    created_by = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="created_client_notes",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "providers_client_note"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "client_phone", "-created_at"]),
        ]

    def __str__(self) -> str:
        return f"Nota {self.client_phone} ({self.provider_id})"
