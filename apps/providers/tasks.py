"""Tasks Celery para o app providers."""

from __future__ import annotations

import logging

from decouple import config

from celery import shared_task

logger = logging.getLogger(__name__)

FRONTEND_URL: str = config("FRONTEND_URL", default="http://localhost:5173")  # type: ignore[assignment]


@shared_task(ignore_result=True)
def send_staff_invite_email(staff_id: str) -> None:
    """
    Envia e-mail de convite para um novo membro da equipe.

    Em desenvolvimento usa EMAIL_BACKEND=console — nenhum e-mail real é enviado.
    O link de aceite aponta para {FRONTEND_URL}/convite?token={token}.
    """
    from apps.providers.models import Staff  # import tardio

    try:
        staff = Staff.objects.select_related("provider").get(pk=staff_id)
    except Staff.DoesNotExist:
        logger.warning("send_staff_invite_email: Staff %s não encontrado", staff_id)
        return

    if not staff.invite_email or not staff.invite_token:
        logger.warning("send_staff_invite_email: Staff %s sem email ou token de convite", staff_id)
        return

    from django.core.mail import send_mail

    invite_link = f"{FRONTEND_URL}/convite?token={staff.invite_token}"
    provider_name = staff.provider.business_name or str(staff.provider)

    subject = f"Você foi convidado para se juntar a {provider_name}"
    message = (
        f"Olá, {staff.name}!\n\n"
        f"Você foi convidado por {provider_name} para participar como "
        f"membro da equipe na plataforma Pontual.\n\n"
        f"Acesse o link abaixo para aceitar o convite:\n{invite_link}\n\n"
        f"Este convite expira em 7 dias.\n\n"
        f"Equipe Pontual"
    )

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=None,  # usa DEFAULT_FROM_EMAIL das settings
            recipient_list=[staff.invite_email],
            fail_silently=False,
        )
    except Exception:
        logger.exception("Falha ao enviar e-mail de convite para %s", staff.invite_email)
