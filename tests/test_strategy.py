from datetime import date

from wheel_bot.config import BotConfig
from wheel_bot.models import OptionLot, Snapshot
from wheel_bot.strategy import classify_phase, decide
from wheel_bot.models import ActionKind, Phase


def _snap(**kwargs) -> Snapshot:
    today = date(2026, 9, 2)
    base = dict(
        ticker="SPY",
        last_price=500.0,
        previous_close=498.0,
        shares=0,
        cash=100_000.0,
        listed_expiries=(today, date(2026, 9, 3), date(2026, 9, 4)),
        listed_strikes=tuple(float(x) for x in range(200, 700)),
    )
    base.update(kwargs)
    return Snapshot(**base)


def test_flat_account_sells_put_three_percent_otm():
    cfg = BotConfig(ticker="SPY", otm_percent=0.03, dte=1)
    decision = decide(_snap(), cfg, date(2026, 9, 2))
    assert decision.action == ActionKind.SELL_PUT
    assert decision.right == "P"
    assert decision.strike == 485.0  # 500 * 0.97
    assert decision.expiry == date(2026, 9, 3)
    assert decision.phase == Phase.FLAT


def test_assigned_next_day_sells_covered_call_above_previous_close():
    cfg = BotConfig(ticker="SPY", otm_percent=0.03, dte=1)
    snap = _snap(shares=100, last_price=490.0, previous_close=500.0)
    decision = decide(snap, cfg, date(2026, 9, 3))
    assert classify_phase(snap, cfg) == Phase.LONG_SHARES
    assert decision.action == ActionKind.SELL_CALL
    assert decision.right == "C"
    assert decision.strike == 515.0  # 500 * 1.03
    assert "assigned" in decision.reason


def test_open_short_put_holds():
    cfg = BotConfig()
    snap = _snap(
        short_puts=(
            OptionLot(right="P", strike=485.0, expiry=date(2026, 9, 3), quantity=-1),
        )
    )
    decision = decide(snap, cfg, date(2026, 9, 2))
    assert decision.action == ActionKind.HOLD
    assert decision.phase == Phase.SHORT_PUT


def test_expired_worthless_sells_put_again():
    cfg = BotConfig(otm_percent=0.03)
    # After expiry: no short put, no shares
    snap = _snap(last_price=510.0, shares=0)
    decision = decide(snap, cfg, date(2026, 9, 4))
    assert decision.action == ActionKind.SELL_PUT
    assert decision.strike == 494.0  # 510 * 0.97 = 494.7 → 494 down


def test_hold_when_insufficient_cash_for_csp():
    cfg = BotConfig(otm_percent=0.03, quantity=1)
    snap = _snap(cash=100.0)
    decision = decide(snap, cfg, date(2026, 9, 2))
    assert decision.action == ActionKind.HOLD
    assert "not enough cash" in decision.reason


def test_ticker_and_percent_are_configurable():
    cfg = BotConfig(ticker="QQQ", otm_percent=0.05, dte=1)
    snap = _snap(ticker="QQQ", last_price=400.0)
    decision = decide(snap, cfg, date(2026, 9, 2))
    assert decision.strike == 380.0  # 400 * 0.95
    cfg2 = BotConfig(ticker="QQQ", otm_percent=0.05, call_otm_percent=0.10)
    assigned = _snap(ticker="QQQ", shares=100, previous_close=400.0)
    call = decide(assigned, cfg2, date(2026, 9, 2))
    assert call.action == ActionKind.SELL_CALL
    assert call.strike == 440.0  # 400 * 1.10
