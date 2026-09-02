from __future__ import annotations

import math
from datetime import date, datetime, timedelta


def round_strike(price: float, increment: float, *, direction: str) -> float:
    """Snap a raw strike to the option increment.

    direction 'down' is used for puts (at or below target).
    direction 'up' is used for calls (at or above target).
    """
    if increment <= 0:
        raise ValueError("strike increment must be positive")
    if direction == "down":
        snapped = math.floor(price / increment + 1e-9) * increment
    elif direction == "up":
        snapped = math.ceil(price / increment - 1e-9) * increment
    else:
        raise ValueError(f"unknown direction {direction}")
    return round(snapped, 8)


def put_target_strike(spot: float, otm_percent: float, increment: float) -> float:
    raw = spot * (1.0 - otm_percent)
    strike = round_strike(raw, increment, direction="down")
    if strike <= 0:
        raise ValueError(f"computed put strike {strike} from spot {spot}")
    return strike


def call_target_strike(previous_close: float, otm_percent: float, increment: float) -> float:
    raw = previous_close * (1.0 + otm_percent)
    strike = round_strike(raw, increment, direction="up")
    if strike <= 0:
        raise ValueError(f"computed call strike {strike} from close {previous_close}")
    return strike


def pick_expiry(expiries: list[date], as_of: date, dte: int) -> date:
    """Choose the listed expiry on or after as_of + dte calendar days."""
    if not expiries:
        raise ValueError("empty option expiry list")
    target = as_of + timedelta(days=max(dte, 0))
    future = sorted(e for e in expiries if e >= target)
    if future:
        return future[0]
    later_or_same = sorted(e for e in expiries if e >= as_of)
    if later_or_same:
        return later_or_same[0]
    raise ValueError(f"no expiry on or after {as_of}")


def parse_ib_expiry(value: str) -> date:
    return datetime.strptime(value, "%Y%m%d").date()
