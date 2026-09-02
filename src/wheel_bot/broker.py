from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date

from wheel_bot.models import Snapshot


class Broker(ABC):
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    @abstractmethod
    def snapshot(self, ticker: str) -> Snapshot: ...

    @abstractmethod
    def sell_option(
        self,
        ticker: str,
        right: str,
        strike: float,
        expiry: date,
        quantity: int,
        *,
        dry_run: bool,
    ) -> dict: ...
