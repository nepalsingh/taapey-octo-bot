from __future__ import annotations

from wheel_bot.config import BotConfig
from wheel_bot.models import ActionKind, Decision, Phase, Snapshot
from wheel_bot.strikes import call_target_strike, pick_expiry, put_target_strike


def classify_phase(snapshot: Snapshot, config: BotConfig) -> Phase:
    needed = config.shares_per_cycle()
    if snapshot.short_calls:
        return Phase.COVERED_CALL
    if snapshot.short_puts:
        return Phase.SHORT_PUT
    if snapshot.shares >= needed:
        return Phase.LONG_SHARES
    return Phase.FLAT


def nearest_listed_strike(target: float, listed: tuple[float, ...], *, prefer: str) -> float:
    if not listed:
        return target
    if prefer == "down":
        below = [s for s in listed if s <= target + 1e-9]
        if below:
            return max(below)
    elif prefer == "up":
        above = [s for s in listed if s >= target - 1e-9]
        if above:
            return min(above)
    return min(listed, key=lambda s: abs(s - target))


def decide(snapshot: Snapshot, config: BotConfig, today) -> Decision:
    """Wheel rules:

    * No shares and no short options → sell a put ~otm% below the current price.
    * Assigned (long shares the next session) → sell a covered call ~otm% above previous close.
    * Put expired worthless → sell a new put at ~otm% below the current price.
    * Open short option already working → hold.
    """
    phase = classify_phase(snapshot, config)
    qty = config.quantity

    if phase in (Phase.SHORT_PUT, Phase.COVERED_CALL):
        open_lot = (snapshot.short_puts or snapshot.short_calls)[0]
        return Decision(
            action=ActionKind.HOLD,
            phase=phase,
            reason=(
                f"open short {open_lot.right} {open_lot.strike} exp {open_lot.expiry}; "
                "wait for expiry or assignment"
            ),
            strike=open_lot.strike,
            expiry=open_lot.expiry,
            right=open_lot.right,
            quantity=qty,
        )

    if not snapshot.listed_expiries:
        return Decision(
            action=ActionKind.HOLD,
            phase=phase,
            reason="no option expiries available",
            quantity=qty,
        )

    expiry = pick_expiry(list(snapshot.listed_expiries), today, config.dte)

    if phase == Phase.LONG_SHARES:
        raw = call_target_strike(
            snapshot.previous_close, config.call_percent, config.strike_increment
        )
        strike = nearest_listed_strike(raw, snapshot.listed_strikes, prefer="up")
        return Decision(
            action=ActionKind.SELL_CALL,
            phase=phase,
            reason=(
                f"assigned / long {snapshot.shares} shares; sell covered call "
                f"{config.call_percent:.2%} above previous close {snapshot.previous_close:.2f}"
            ),
            strike=strike,
            expiry=expiry,
            right="C",
            quantity=qty,
        )

    # FLAT: cash-secured put (initial entry or put expired worthless)
    raw = put_target_strike(snapshot.last_price, config.put_percent, config.strike_increment)
    strike = nearest_listed_strike(raw, snapshot.listed_strikes, prefer="down")
    collateral = strike * 100 * qty
    if snapshot.cash + 1e-6 < collateral:
        return Decision(
            action=ActionKind.HOLD,
            phase=phase,
            reason=(
                f"not enough cash for cash-secured put: need ~{collateral:.0f}, "
                f"have {snapshot.cash:.0f}"
            ),
            strike=strike,
            expiry=expiry,
            right="P",
            quantity=qty,
        )
    return Decision(
        action=ActionKind.SELL_PUT,
        phase=phase,
        reason=(
            f"flat / put expired worthless; sell put {config.put_percent:.2%} "
            f"below last {snapshot.last_price:.2f}"
        ),
        strike=strike,
        expiry=expiry,
        right="P",
        quantity=qty,
    )
