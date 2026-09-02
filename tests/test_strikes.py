from datetime import date

import pytest

from wheel_bot.strikes import (
    call_target_strike,
    parse_ib_expiry,
    pick_expiry,
    put_target_strike,
    round_strike,
)


def test_put_strike_three_percent_below_spot():
    # 500 * 0.97 = 485, already on a $1 increment
    assert put_target_strike(500.0, 0.03, 1.0) == 485.0


def test_put_strike_rounds_down():
    # 501 * 0.97 = 485.97 → 485
    assert put_target_strike(501.0, 0.03, 1.0) == 485.0


def test_call_strike_three_percent_above_previous_close():
    # 500 * 1.03 = 515
    assert call_target_strike(500.0, 0.03, 1.0) == 515.0


def test_call_strike_rounds_up():
    # 500.4 * 1.03 = 515.412 → 516
    assert call_target_strike(500.4, 0.03, 1.0) == 516.0


def test_round_strike_rejects_bad_direction():
    with pytest.raises(ValueError):
        round_strike(10, 1, direction="sideways")


def test_pick_expiry_honors_dte():
    as_of = date(2026, 9, 2)
    expiries = [date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 4), date(2026, 9, 11)]
    assert pick_expiry(expiries, as_of, dte=1) == date(2026, 9, 3)
    assert pick_expiry(expiries, as_of, dte=0) == date(2026, 9, 2)


def test_pick_expiry_falls_back_when_target_missing():
    as_of = date(2026, 9, 2)
    expiries = [date(2026, 9, 11), date(2026, 9, 18)]
    assert pick_expiry(expiries, as_of, dte=1) == date(2026, 9, 11)


def test_parse_ib_expiry():
    assert parse_ib_expiry("20260904") == date(2026, 9, 4)
