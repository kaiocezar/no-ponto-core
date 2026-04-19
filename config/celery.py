"""Configuração do Celery."""

import os

from celery.schedules import crontab

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.development")

app = Celery("agendador")

# Carrega configurações do Django settings (prefixo CELERY_)
app.config_from_object("django.conf:settings", namespace="CELERY")

# Descobre tasks automaticamente em todos os apps instalados
app.autodiscover_tasks()


# ── Tarefas periódicas (Celery Beat) ──────────────────────────────────────────
app.conf.beat_schedule = {
    # Envia lembretes 24h antes — verifica a cada hora
    "send-24h-reminders": {
        "task": "apps.appointments.tasks.send_24h_reminders",
        "schedule": crontab(minute=0),
    },
    # Envia lembretes 1h antes — verifica a cada 15 minutos
    "send-1h-reminders": {
        "task": "apps.appointments.tasks.send_1h_reminders",
        "schedule": crontab(minute="*/15"),
    },
    # Auto-confirma agendamentos pendentes há mais de 24h
    "auto-confirm-pending-appointments": {
        "task": "apps.appointments.tasks.auto_confirm_pending_appointments",
        "schedule": crontab(minute="*/30"),
    },
    # Marca como no-show agendamentos passados não finalizados
    "mark-no-shows": {
        "task": "apps.appointments.tasks.mark_no_shows",
        "schedule": crontab(minute="*/30"),
    },
    # Envia solicitações de avaliação — verifica a cada hora
    "send-review-requests": {
        "task": "apps.notifications.tasks.send_pending_review_requests",
        "schedule": crontab(minute=0),
    },
    # Remove OTPs expirados — diário às 3h da manhã
    "cleanup-expired-otps": {
        "task": "apps.accounts.tasks.cleanup_expired_otps",
        "schedule": crontab(hour=3, minute=0),
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self) -> None:  # type: ignore[override]
    """Task de debug para verificar se o Celery está funcionando."""
    print(f"Request: {self.request!r}")  # noqa: T201
