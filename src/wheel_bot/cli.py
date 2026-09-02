from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, timedelta

from wheel_bot.config import BotConfig, load_config
from wheel_bot.models import OptionLot, Snapshot
from wheel_bot.strategy import decide

log = logging.getLogger("wheel_bot")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Sell cash-secured puts and, if assigned, sell covered calls "
            "via the Interactive Brokers API (the options wheel)."
        )
    )
    parser.add_argument("--config", help="Path to YAML config (default: ./config.yaml if present)")
    parser.add_argument("--ticker", help="Underlying symbol (default SPY)")
    parser.add_argument(
        "--otm-percent",
        type=float,
        help="OTM percent for both legs. 3 or 0.03 both mean 3%%.",
    )
    parser.add_argument("--put-otm-percent", type=float, help="Override put OTM percent")
    parser.add_argument("--call-otm-percent", type=float, help="Override call OTM percent")
    parser.add_argument("--quantity", type=int, help="Option contracts per cycle")
    parser.add_argument("--dte", type=int, help="Target days to expiry (default 1)")
    parser.add_argument("--host", help="IB API host")
    parser.add_argument("--port", type=int, help="IB API port (7497 paper TWS)")
    parser.add_argument("--client-id", type=int, dest="client_id")
    parser.add_argument("--state-path", help="JSON state file path")
    dry = parser.add_mutually_exclusive_group()
    dry.add_argument(
        "--dry-run",
        dest="dry_run",
        action="store_true",
        default=None,
        help="Log intended orders without sending (default from config)",
    )
    dry.add_argument(
        "--live",
        dest="dry_run",
        action="store_false",
        help="Send orders to IB",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Evaluate once and exit (for cron). Default is a polling loop.",
    )
    parser.add_argument(
        "--simulate",
        action="store_true",
        help="Print the wheel decision from fake prices/positions; no IB connection.",
    )
    parser.add_argument("--price", type=float, default=500.0, help="Simulate last price")
    parser.add_argument("--previous-close", type=float, dest="previous_close")
    parser.add_argument(
        "--assigned",
        action="store_true",
        help="Simulate being assigned on the put (long 100 shares per contract)",
    )
    parser.add_argument(
        "--short-put",
        action="store_true",
        help="Simulate an already-open short put",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def _configure_logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )


def _simulated_snapshot(config: BotConfig, args: argparse.Namespace) -> Snapshot:
    last = args.price
    prev = args.previous_close if args.previous_close is not None else last
    today = date.today()
    expiries = tuple(today + timedelta(days=d) for d in range(0, 14))
    increment = config.strike_increment
    lo = int((last * 0.9) / increment) * increment
    hi = int((last * 1.1) / increment) * increment
    strikes = tuple(round(s, 4) for s in _frange(lo, hi, increment))
    shares = config.shares_per_cycle() if args.assigned else 0
    puts = ()
    if args.short_put:
        puts = (
            OptionLot(
                right="P",
                strike=round(last * (1 - config.put_percent), 0),
                expiry=today + timedelta(days=config.dte),
                quantity=-config.quantity,
            ),
        )
    return Snapshot(
        ticker=config.ticker,
        last_price=last,
        previous_close=prev,
        shares=shares,
        cash=1_000_000.0,
        short_puts=puts,
        listed_expiries=expiries,
        listed_strikes=strikes,
    )


def _frange(start: float, stop: float, step: float) -> list[float]:
    values = []
    x = start
    while x <= stop + 1e-9:
        values.append(x)
        x += step
    return values


def run_simulate(config: BotConfig, args: argparse.Namespace) -> int:
    snapshot = _simulated_snapshot(config, args)
    decision = decide(snapshot, config, date.today())
    print(f"ticker          {config.ticker}")
    print(f"otm_percent     {config.otm_percent:.2%}  (put={config.put_percent:.2%} call={config.call_percent:.2%})")
    print(f"last            {snapshot.last_price:.2f}")
    print(f"previous_close  {snapshot.previous_close:.2f}")
    print(f"shares          {snapshot.shares}")
    print(f"phase           {decision.phase.value}")
    print(f"action          {decision.action.value}")
    print(f"right           {decision.right}")
    print(f"strike          {decision.strike}")
    print(f"expiry          {decision.expiry}")
    print(f"reason          {decision.reason}")
    return 0


def run_live(config: BotConfig, once: bool) -> int:
    from wheel_bot.bot import WheelBot
    from wheel_bot.ib_broker import IBBroker

    broker = IBBroker(config)
    bot = WheelBot(config, broker)
    try:
        broker.connect()
        while True:
            bot.run_once()
            if once:
                return 0
            time.sleep(max(config.poll_seconds, 5))
    except KeyboardInterrupt:
        log.info("stopped")
        return 0
    finally:
        broker.disconnect()


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    config = load_config(args)
    log.info(
        "wheel bot ticker=%s otm=%.2f%% put=%.2f%% call=%.2f%% dry_run=%s",
        config.ticker,
        config.otm_percent * 100,
        config.put_percent * 100,
        config.call_percent * 100,
        config.dry_run,
    )
    if args.simulate:
        return run_simulate(config, args)
    return run_live(config, once=args.once)


if __name__ == "__main__":
    sys.exit(main())
