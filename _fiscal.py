"""
Datafast — deterministic fiscal engine.

Datafast/Oppwa requires string amounts ("12.50") and enforces:
  amount == subtotal_iva0 + subtotal_gravado + valor_iva + valor_ice

Violation causes error 100.400.500.
"""

from __future__ import annotations

import os
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum

_TWO = Decimal("0.01")


class TipoMonto(str, Enum):
    SUBTOTAL = "subtotal"
    TOTAL_CON_IVA = "total_con_iva"


def _iva_rate() -> Decimal:
    raw = os.environ.get("IVA_EC_PERCENTAGE", "0.15")
    try:
        rate = Decimal(raw)
        if not (Decimal(0) < rate <= Decimal(1)):
            raise ValueError()
        return rate
    except Exception:
        raise ValueError(f"IVA_EC_PERCENTAGE inválido: {raw!r}.")


def _r2(v: Decimal) -> Decimal:
    return v.quantize(_TWO, rounding=ROUND_HALF_UP)


def calcular_strings_fiscales(monto: float, tipo: TipoMonto) -> tuple[str, str, str]:
    """Return (amount_str, subtotal_gravado_str, valor_iva_str) as "0.00" strings.

    Examples:
        calcular_strings_fiscales(30.0, SUBTOTAL)      → ("34.50", "30.00", "4.50")
        calcular_strings_fiscales(30.0, TOTAL_CON_IVA) → ("30.00", "26.09", "3.91")
    """
    if monto <= 0:
        raise ValueError(f"monto debe ser > 0. Recibido: {monto}")
    rate = _iva_rate()
    d = Decimal(str(monto))
    if tipo == TipoMonto.TOTAL_CON_IVA:
        total = _r2(d)
        subtotal = _r2(d / (1 + rate))
        iva = _r2(total - subtotal)
    else:
        subtotal = _r2(d)
        iva = _r2(d * rate)
        total = _r2(subtotal + iva)
    return str(total), str(subtotal), str(iva)
