from __future__ import annotations

import logging
from datetime import date

from wheel_bot.broker import Broker
from wheel_bot.config import BotConfig
from wheel_bot.models import Decision
from wheel_bot.state import append_run, record_from_decision
from wheel_bot.strategy import decide

log = logging.getLogger(__name__)


class WheelBot:
    def __init__(self, config: BotConfig, broker: Broker) -> None:
        self.config = config
        self.broker = broker

    def run_once(self, today: date | None = None) -> Decision:
        today = today or date.today()
        snapshot = self.broker.snapshot(self.config.ticker)
        decision = decide(snapshot, self.config, today)
        log.info(
            "phase=%s action=%s strike=%s expiry=%s :: %s",
            decision.phase.value,
            decision.action.value,
            decision.strike,
            decision.expiry,
            decision.reason,
        )
        extra: dict = {
            "last_price": snapshot.last_price,
            "previous_close": snapshot.previous_close,
            "shares": snapshot.shares,
            "cash": snapshot.cash,
            "phase": decision.phase.value,
        }
        if decision.action.value in ("SELL_PUT", "SELL_CALL"):
            assert decision.expiry is not None and decision.strike is not None
            extra["order"] = self.broker.sell_option(
                self.config.ticker,
                decision.right or "P",
                decision.strike,
                decision.expiry,
                decision.quantity,
                dry_run=self.config.dry_run,
            )
        append_run(
            self.config.state_path,
            record_from_decision(
                self.config.ticker,
                decision,
                dry_run=self.config.dry_run,
                extra=extra,
            ),
        )
        return decision
