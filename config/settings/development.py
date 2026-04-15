"""Configurações para ambiente de desenvolvimento local."""

from .base import *  # noqa: F401, F403

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
LOGGING["loggers"]["django.db.backends"]["level"] = "DEBUG"  # type: ignore[index]

# Celery executa tasks de forma síncrona em dev (sem precisar do worker rodando)
# Comentar para testar com o worker real
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Storage local em dev (em vez de S3)
DEFAULT_FILE_STORAGE = "django.core.files.storage.FileSystemStorage"
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"
