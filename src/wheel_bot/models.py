from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from enum import Enum
from typing import Literal


class ActionKind(str, Enum):
    SELL_PUT = "SELL_PUT"
    SELL_CALL = "SELL_CALL"
    HOLD = "HOLD"


class Phase(str, Enum):
    FLAT = "FLAT"
    SHORT_PUT = "SHORT_PUT"
    LONG_SHARES = "LONG_SHARES"
    COVERED_CALL = "COVERED_CALL"


@dataclass(frozen=True)
class OptionLot:
    right: Literal["P", "C"]
    strike: float
    expiry: date
    quantity: int  # signed: short is negative
    con_id: int | None = None


@dataclass(frozen=True)
class Snapshot:
    ticker: str
    last_price: float
    previous_close: float
    shares: int
    cash: float
    short_puts: tuple[OptionLot, ...] = ()
    short_calls: tuple[OptionLot, ...] = ()
    listed_expiries: tuple[date, ...] = ()
    listed_strikes: tuple[float, ...] = ()


@dataclass(frozen=True)
class Decision:
    action: ActionKind
    phase: Phase
    reason: str
    strike: float | None = None
    expiry: date | None = None
    right: Literal["P", "C"] | None = None
    quantity: int = 1
    limit_price: float | None = None


@dataclass
class RunRecord:
    timestamp: str
    ticker: str
    action: str
    reason: str
    strike: float | None = None
    expiry: str | None = None
    dry_run: bool = True
    extra: dict = field(default_factory=dict)

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()
