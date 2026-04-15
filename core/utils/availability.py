"""
Lógica de cálculo de slots disponíveis para agendamento.

Esta função é o núcleo do sistema — retorna os horários disponíveis
considerando: horário de funcionamento, bloqueios, agendamentos existentes
e as configurações de buffer, notice e advance do prestador.
"""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

from dateutil import rrule as rrulelib
from django.utils import timezone

if TYPE_CHECKING:
    from apps.providers.models import ProviderProfile, ScheduleBlock, WorkingHours

logger = logging.getLogger(__name__)

# Tipo para um slot de disponibilidade
type SlotList = list[datetime.datetime]


def get_available_slots(
    provider: ProviderProfile,
    service_duration: int,
    buffer_after: int,
    date: datetime.date,
    staff: object | None = None,
) -> SlotList:
    """
    Retorna lista de datetimes disponíveis para agendamento.

    Algoritmo:
    1. Obtém WorkingHours do profissional/estabelecimento para o weekday
    2. Gera slots fixos de service_duration em service_duration
    3. Subtrai ScheduleBlock que cobrem o período (incluindo recorrentes via RRULE)
    4. Subtrai Appointments confirmados/pendentes + buffer_after de cada um
    5. Remove slots que ultrapassariam o end_time do dia
    6. Remove slots no passado e dentro do min_notice_hours do prestador
    7. Remove slots além de max_advance_days
    """

    # 1. Obter horário de funcionamento para o dia da semana
    weekday = date.weekday()  # 0=Segunda … 6=Domingo

    # Prioridade: horário específico do profissional > horário do estabelecimento
    working_hours = _get_working_hours(provider, staff, weekday)
    if not working_hours:
        return []

    if not working_hours.is_active:
        return []

    # 2. Gerar slots fixos dentro do horário de funcionamento
    raw_slots = _generate_slots(
        date=date,
        start_time=working_hours.start_time,
        end_time=working_hours.end_time,
        duration_minutes=service_duration,
        timezone_str=provider.timezone,
    )

    if not raw_slots:
        return []

    # 3. Filtrar por bloqueios de agenda
    blocks = _get_blocks_for_day(provider, staff, date)
    available = _filter_by_blocks(raw_slots, blocks, service_duration)

    # 4. Filtrar por agendamentos existentes (com buffer)
    available = _filter_by_appointments(
        available, provider, staff, date, service_duration, buffer_after
    )

    # 5. Remover slots no passado e dentro do min_notice_hours
    now = timezone.now()
    min_notice_delta = datetime.timedelta(hours=provider.min_notice_hours)
    cutoff = now + min_notice_delta
    available = [slot for slot in available if slot > cutoff]

    # 6. Remover slots além de max_advance_days
    max_date = timezone.localdate() + datetime.timedelta(days=provider.max_advance_days)
    available = [slot for slot in available if slot.date() <= max_date]

    return available


def _get_working_hours(
    provider: ProviderProfile,
    staff: object | None,
    weekday: int,
) -> WorkingHours | None:
    """
    Retorna o horário de funcionamento mais específico para o dia.
    Profissional sobrescreve estabelecimento.
    """
    from apps.providers.models import WorkingHours

    if staff is not None:
        staff_hours = WorkingHours.objects.filter(
            staff=staff,
            weekday=weekday,
            is_active=True,
        ).first()
        if staff_hours:
            return staff_hours

    return WorkingHours.objects.filter(
        provider=provider,
        staff__isnull=True,
        weekday=weekday,
        is_active=True,
    ).first()


def _generate_slots(
    date: datetime.date,
    start_time: datetime.time,
    end_time: datetime.time,
    duration_minutes: int,
    timezone_str: str,
) -> SlotList:
    """
    Gera lista de datetime (timezone-aware) para cada slot do dia.
    Os horários são locais ao timezone do prestador.
    """
    import zoneinfo

    try:
        tz = zoneinfo.ZoneInfo(timezone_str)
    except Exception:
        tz = zoneinfo.ZoneInfo("America/Sao_Paulo")

    slots: SlotList = []
    current = datetime.datetime.combine(date, start_time, tzinfo=tz)
    end = datetime.datetime.combine(date, end_time, tzinfo=tz)
    delta = datetime.timedelta(minutes=duration_minutes)

    while current + delta <= end:
        slots.append(current)
        current += delta

    return slots


def _get_blocks_for_day(
    provider: ProviderProfile,
    staff: object | None,
    date: datetime.date,
) -> list[ScheduleBlock]:
    """
    Retorna bloqueios que afetam o dia, incluindo recorrentes (via RRULE).
    """
    from apps.providers.models import ScheduleBlock

    day_start = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.UTC)
    day_end = datetime.datetime.combine(date, datetime.time.max, tzinfo=datetime.UTC)

    # Bloqueios pontuais que interceptam o dia
    qs = ScheduleBlock.objects.filter(provider=provider)
    qs = qs.filter(staff=staff) if staff is not None else qs.filter(staff__isnull=True)

    active_blocks: list[ScheduleBlock] = []

    # Bloqueios não-recorrentes que sobrepõem o dia
    non_recurring = qs.filter(
        is_recurring=False,
        start_datetime__lt=day_end,
        end_datetime__gt=day_start,
    )
    active_blocks.extend(non_recurring)

    # Bloqueios recorrentes — expandir via RRULE e verificar ocorrências no dia
    recurring = qs.filter(is_recurring=True)
    for block in recurring:
        if _rrule_has_occurrence_on_day(block, date):
            active_blocks.append(block)

    return active_blocks


def _rrule_has_occurrence_on_day(block: ScheduleBlock, date: datetime.date) -> bool:
    """
    Verifica se um bloqueio recorrente tem ocorrência no dia especificado.
    Usa python-dateutil para processar RRULE RFC 5545.
    """
    if not block.recurrence_rule:
        return False

    try:
        duration = block.end_datetime - block.start_datetime
        rule = rrulelib.rrulestr(
            block.recurrence_rule,
            dtstart=block.start_datetime,
        )
        day_start = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.UTC)
        day_end = datetime.datetime.combine(date, datetime.time.max, tzinfo=datetime.UTC)

        # Ajustar busca para cobrir início das ocorrências que podem se estender ao dia
        search_start = day_start - duration
        occurrences = rule.between(search_start, day_end, inc=True)
        for occ in occurrences:
            occ_end = occ + duration
            if occ < day_end and occ_end > day_start:
                return True
    except Exception:
        logger.exception("Erro ao processar RRULE para bloco %s", block.pk)

    return False


def _filter_by_blocks(
    slots: SlotList,
    blocks: list[ScheduleBlock],
    duration_minutes: int,
) -> SlotList:
    """
    Remove slots que colidem com bloqueios de agenda.
    Um slot colide se: slot_start < block_end E slot_end > block_start.
    """
    if not blocks:
        return slots

    duration = datetime.timedelta(minutes=duration_minutes)
    available: SlotList = []

    for slot in slots:
        slot_end = slot + duration
        collides = any(
            slot < block.end_datetime and slot_end > block.start_datetime for block in blocks
        )
        if not collides:
            available.append(slot)

    return available


def _filter_by_appointments(
    slots: SlotList,
    provider: ProviderProfile,
    staff: object | None,
    date: datetime.date,
    duration_minutes: int,
    buffer_after: int,
) -> SlotList:
    """
    Remove slots que colidem com agendamentos existentes.
    Considera o buffer_after de cada serviço.

    Usa Appointment model se disponível — caso contrário, retorna slots sem filtro.
    """
    try:
        from apps.appointments.models import Appointment
    except ImportError:
        # App appointments ainda não implementado
        return slots

    day_start = datetime.datetime.combine(date, datetime.time.min, tzinfo=datetime.UTC)
    day_end = datetime.datetime.combine(date, datetime.time.max, tzinfo=datetime.UTC)

    appointments_qs = Appointment.objects.filter(
        provider=provider,
        start_datetime__lt=day_end,
        end_datetime__gt=day_start,
        status__in=["pending_confirmation", "confirmed"],
    )
    if staff is not None:
        appointments_qs = appointments_qs.filter(staff=staff)

    if not appointments_qs.exists():
        return slots

    duration = datetime.timedelta(minutes=duration_minutes)
    busy_periods: list[tuple[datetime.datetime, datetime.datetime]] = []

    for appt in appointments_qs:
        # Fim efetivo inclui buffer do serviço
        appt_end_with_buffer = appt.end_datetime + datetime.timedelta(
            minutes=getattr(appt, "buffer_after", 0)
        )
        busy_periods.append((appt.start_datetime, appt_end_with_buffer))

    available: SlotList = []
    for slot in slots:
        slot_end = slot + duration
        collides = any(
            slot < busy_end and slot_end > busy_start for busy_start, busy_end in busy_periods
        )
        if not collides:
            available.append(slot)

    return available
