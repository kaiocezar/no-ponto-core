"""Normalização de telefone para agendamento público e lookup."""

from __future__ import annotations


def normalize_phone_for_match(phone: str) -> str:
    """
    Comparação consistente: dígitos com prefixo 55 quando o número não traz DDI.
    Ex.: (11) 99999-9999 e +5511999999999 resultam no mesmo valor.
    """
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("55") and len(digits) >= 12:
        return digits
    return f"55{digits}"
