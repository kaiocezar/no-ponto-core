"""
Configurações base compartilhadas entre todos os ambientes.
Não usar diretamente — extender em development.py ou production.py.
"""

from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── Segurança ─────────────────────────────────────────────────────────────────
SECRET_KEY: str = config("DJANGO_SECRET_KEY")
DEBUG: bool = config("DJANGO_DEBUG", default=False, cast=bool)
ALLOWED_HOSTS: list[str] = config("DJANGO_ALLOWED_HOSTS", default="localhost", cast=Csv())

# ── Aplicações ────────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "django_filters",
    "django_celery_beat",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.providers",
    "apps.services",
    "apps.appointments",
    "apps.notifications",
    "apps.reviews",
    "apps.webhooks",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── Middleware ────────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # CORS antes de CommonMiddleware
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

# ── Templates ─────────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ── Banco de dados ────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="agendador"),
        "USER": config("POSTGRES_USER", default="agendador"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="agendador_dev"),
        "HOST": config("POSTGRES_HOST", default="localhost"),
        "PORT": config("POSTGRES_PORT", default="5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {
            "connect_timeout": 10,
        },
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Autenticação ──────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",  # mais seguro que bcrypt
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",  # fallback
]

# ── Internacionalização ───────────────────────────────────────────────────────
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# ── Arquivos estáticos ────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ── Django REST Framework ─────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "core.pagination.CursorPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
        "rest_framework.parsers.MultiPartParser",
    ],
    "EXCEPTION_HANDLER": "core.exceptions.custom_exception_handler",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "100/hour",
        "user": "1000/hour",
        "otp_request": "5/10min",
        "register": "10/hour",
    },
}

# ── JWT ───────────────────────────────────────────────────────────────────────
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=config("JWT_ACCESS_TOKEN_LIFETIME_MINUTES", default=15, cast=int)
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=config("JWT_REFRESH_TOKEN_LIFETIME_DAYS", default=30, cast=int)
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": True,
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# ── CORS ──────────────────────────────────────────────────────────────────────
CORS_ALLOWED_ORIGINS: list[str] = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "origin",
    "x-hub-signature-256",  # Webhook WhatsApp
]

# ── Celery ────────────────────────────────────────────────────────────────────
_redis_password = config("REDIS_PASSWORD", default="redis_dev")
_redis_host = config("REDIS_HOST", default="localhost")
_redis_port = config("REDIS_PORT", default="6379")
REDIS_URL = f"redis://:{_redis_password}@{_redis_host}:{_redis_port}/0"

CELERY_BROKER_URL = REDIS_URL
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutos
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60

CELERY_TASK_ROUTES = {
    "apps.notifications.tasks.send_whatsapp_*": {"queue": "high_priority"},
    "apps.accounts.tasks.send_*_otp": {"queue": "high_priority"},
    "apps.notifications.tasks.send_*_reminder*": {"queue": "notifications"},
    "apps.appointments.tasks.*": {"queue": "default"},
}

# ── Cache (Redis) ──────────────────────────────────────────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": REDIS_URL,
    }
}

# ── Sessões ────────────────────────────────────────────────────────────────────
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ── WhatsApp ──────────────────────────────────────────────────────────────────
WHATSAPP_PHONE_NUMBER_ID: str = config("WHATSAPP_PHONE_NUMBER_ID", default="")
WHATSAPP_ACCESS_TOKEN: str = config("WHATSAPP_ACCESS_TOKEN", default="")
WHATSAPP_APP_SECRET: str = config("WHATSAPP_APP_SECRET", default="")
WHATSAPP_VERIFY_TOKEN: str = config("WHATSAPP_VERIFY_TOKEN", default="dev-whatsapp-verify-token")
WHATSAPP_BACKEND: str = config("WHATSAPP_BACKEND", default="meta")
EVOLUTION_API_URL: str = config("EVOLUTION_API_URL", default="http://localhost:8080")

# ── URLs externas ─────────────────────────────────────────────────────────────
FRONTEND_URL: str = config("FRONTEND_URL", default="http://localhost:5173")

# ── Logging (structlog) ───────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
    },
}
