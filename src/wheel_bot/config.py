from __future__ import annotations

import argparse
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class IBConnection:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 7
    timeout_sec: int = 30


@dataclass(frozen=True)
class OrderSettings:
    limit_vs_mid: float = 0.5
    wait_fill_sec: int = 30
    tif: str = "DAY"


@dataclass(frozen=True)
class BotConfig:
    ticker: str = "SPY"
    otm_percent: float = 0.03
    put_otm_percent: float | None = None
    call_otm_percent: float | None = None
    quantity: int = 1
    dte: int = 1
    strike_increment: float = 1.0
    ib: IBConnection = field(default_factory=IBConnection)
    order: OrderSettings = field(default_factory=OrderSettings)
    dry_run: bool = True
    state_path: str = "data/wheel_state.json"
    poll_seconds: int = 60

    @property
    def put_percent(self) -> float:
        return self.otm_percent if self.put_otm_percent is None else self.put_otm_percent

    @property
    def call_percent(self) -> float:
        return self.otm_percent if self.call_otm_percent is None else self.call_otm_percent

    def shares_per_cycle(self) -> int:
        return 100 * self.quantity


def _as_float_percent(value: Any) -> float:
    """Accept 0.03 or 3 (meaning 3%)."""
    number = float(value)
    if number > 1:
        return number / 100.0
    return number


def load_yaml(path: str | Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Config file {path} must be a mapping")
    return data


def config_from_mapping(data: dict[str, Any]) -> BotConfig:
    ib_raw = data.get("ib") or {}
    order_raw = data.get("order") or {}
    ticker = str(data.get("ticker", "SPY")).upper()
    return BotConfig(
        ticker=ticker,
        otm_percent=_as_float_percent(data.get("otm_percent", 0.03)),
        put_otm_percent=(
            _as_float_percent(data["put_otm_percent"])
            if data.get("put_otm_percent") is not None
            else None
        ),
        call_otm_percent=(
            _as_float_percent(data["call_otm_percent"])
            if data.get("call_otm_percent") is not None
            else None
        ),
        quantity=int(data.get("quantity", 1)),
        dte=int(data.get("dte", 1)),
        strike_increment=float(data.get("strike_increment", 1.0)),
        ib=IBConnection(
            host=str(ib_raw.get("host", "127.0.0.1")),
            port=int(ib_raw.get("port", 7497)),
            client_id=int(ib_raw.get("client_id", 7)),
            timeout_sec=int(ib_raw.get("timeout_sec", 30)),
        ),
        order=OrderSettings(
            limit_vs_mid=float(order_raw.get("limit_vs_mid", 0.5)),
            wait_fill_sec=int(order_raw.get("wait_fill_sec", 30)),
            tif=str(order_raw.get("tif", "DAY")),
        ),
        dry_run=bool(data.get("dry_run", True)),
        state_path=str(data.get("state_path", "data/wheel_state.json")),
        poll_seconds=int(data.get("poll_seconds", 60)),
    )


def apply_cli_overrides(config: BotConfig, args: argparse.Namespace) -> BotConfig:
    ticker = (args.ticker or config.ticker).upper()
    otm = (
        _as_float_percent(args.otm_percent)
        if args.otm_percent is not None
        else config.otm_percent
    )
    put_otm = (
        _as_float_percent(args.put_otm_percent)
        if args.put_otm_percent is not None
        else config.put_otm_percent
    )
    call_otm = (
        _as_float_percent(args.call_otm_percent)
        if args.call_otm_percent is not None
        else config.call_otm_percent
    )
    dry_run = config.dry_run if args.dry_run is None else args.dry_run
    ib = config.ib
    if args.host or args.port or args.client_id:
        ib = IBConnection(
            host=args.host or ib.host,
            port=args.port if args.port is not None else ib.port,
            client_id=args.client_id if args.client_id is not None else ib.client_id,
            timeout_sec=ib.timeout_sec,
        )
    return BotConfig(
        ticker=ticker,
        otm_percent=otm,
        put_otm_percent=put_otm,
        call_otm_percent=call_otm,
        quantity=args.quantity if args.quantity is not None else config.quantity,
        dte=args.dte if args.dte is not None else config.dte,
        strike_increment=config.strike_increment,
        ib=ib,
        order=config.order,
        dry_run=dry_run,
        state_path=args.state_path or config.state_path,
        poll_seconds=config.poll_seconds,
    )


def load_config(args: argparse.Namespace) -> BotConfig:
    if args.config:
        data = load_yaml(args.config)
    else:
        default = Path("config.yaml")
        data = load_yaml(default) if default.exists() else {}
    config = config_from_mapping(data)
    env_ticker = os.environ.get("WHEEL_TICKER")
    env_otm = os.environ.get("WHEEL_OTM_PERCENT")
    if env_ticker:
        config = BotConfig(**{**config.__dict__, "ticker": env_ticker.upper()})
    if env_otm:
        config = BotConfig(**{**config.__dict__, "otm_percent": _as_float_percent(env_otm)})
    return apply_cli_overrides(config, args)
