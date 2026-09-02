from datetime import date

from wheel_bot.bot import WheelBot
from wheel_bot.broker import Broker
from wheel_bot.config import BotConfig
from wheel_bot.models import ActionKind, Snapshot


class FakeBroker(Broker):
    def __init__(self, snapshot: Snapshot) -> None:
        self._snapshot = snapshot
        self.orders: list[dict] = []
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def snapshot(self, ticker: str) -> Snapshot:
        return self._snapshot

    def sell_option(self, ticker, right, strike, expiry, quantity, *, dry_run):
        order = {
            "ticker": ticker,
            "right": right,
            "strike": strike,
            "expiry": expiry,
            "quantity": quantity,
            "dry_run": dry_run,
        }
        self.orders.append(order)
        return order


def test_bot_sells_put_when_flat(tmp_path):
    today = date(2026, 9, 2)
    snap = Snapshot(
        ticker="SPY",
        last_price=500.0,
        previous_close=500.0,
        shares=0,
        cash=80_000.0,
        listed_expiries=(today, date(2026, 9, 3)),
        listed_strikes=tuple(float(x) for x in range(450, 550)),
    )
    cfg = BotConfig(
        ticker="SPY",
        otm_percent=0.03,
        dte=1,
        dry_run=True,
        state_path=str(tmp_path / "state.json"),
    )
    broker = FakeBroker(snap)
    bot = WheelBot(cfg, broker)
    decision = bot.run_once(today=today)
    assert decision.action == ActionKind.SELL_PUT
    assert broker.orders and broker.orders[0]["strike"] == 485.0
    assert (tmp_path / "state.json").exists()


def test_bot_sells_call_when_assigned(tmp_path):
    today = date(2026, 9, 3)
    snap = Snapshot(
        ticker="SPY",
        last_price=495.0,
        previous_close=500.0,
        shares=100,
        cash=20_000.0,
        listed_expiries=(today, date(2026, 9, 4)),
        listed_strikes=tuple(float(x) for x in range(450, 550)),
    )
    cfg = BotConfig(state_path=str(tmp_path / "state.json"), dry_run=True)
    broker = FakeBroker(snap)
    decision = WheelBot(cfg, broker).run_once(today=today)
    assert decision.action == ActionKind.SELL_CALL
    assert broker.orders[0]["right"] == "C"
    assert broker.orders[0]["strike"] == 515.0
