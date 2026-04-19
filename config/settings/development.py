"""Configurações para ambiente de desenvolvimento local."""

from .base import *  # noqa: F403

DEBUG = True

# Permite qualquer origem em dev
CORS_ALLOW_ALL_ORIGINS = True

# Django Debug Toolbar (instalar manualmente se quiser: uv add django-debug-toolbar)
# INSTALLED_APPS += ["debug_toolbar"]
# MIDDLEWARE.insert(1, "debug_toolbar.middleware.DebugToolbarMiddleware")
# INTERNAL_IPS = ["127.0.0.1"]

# Emails no console em dev
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Exibe queries SQL no console em dev (desativar em produção)
LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"  # type: ignore[index]  # noqa: F405

# Rate limits mais altos em dev para não bloquear testes E2E
REST_FRAMEWORK = {
    **REST_FRAMEWORK,  # type: ignore[name-defined]  # noqa: F405
    "DEFAULT_THROTTLE_RATES": {
        "anon": "1000/hour",
        "user": "5000/hour",
        "otp_request": "100/hour",
        "register": "1000/hour",
    },
}

# Celery executa tasks de forma síncrona em dev (sem precisar do worker rodando)
# Comentar para testar com o worker real
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
WHATSAPP_BACKEND = "evolution"

# Storage local em dev (em vez de S3)
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
