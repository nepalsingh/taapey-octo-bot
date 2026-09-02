from __future__ import annotations

import logging
import math
from datetime import date
from typing import Any

from wheel_bot.broker import Broker
from wheel_bot.config import BotConfig
from wheel_bot.models import OptionLot, Snapshot
from wheel_bot.strikes import parse_ib_expiry

log = logging.getLogger(__name__)


class IBBroker(Broker):
    """Thin wrapper around ib_insync. Requires TWS or IB Gateway with API enabled."""

    def __init__(self, config: BotConfig, ib: Any | None = None) -> None:
        self.config = config
        self._ib = ib
        self._stock = None

    @property
    def ib(self):
        if self._ib is None:
            from ib_insync import IB

            self._ib = IB()
        return self._ib

    def connect(self) -> None:
        ib = self.ib
        if ib.isConnected():
            return
        settings = self.config.ib
        log.info(
            "connecting to IB %s:%s clientId=%s",
            settings.host,
            settings.port,
            settings.client_id,
        )
        ib.connect(
            settings.host,
            settings.port,
            clientId=settings.client_id,
            timeout=settings.timeout_sec,
        )

    def disconnect(self) -> None:
        if self._ib is not None and self._ib.isConnected():
            self._ib.disconnect()

    def _qualify_stock(self, ticker: str):
        from ib_insync import Stock

        stock = Stock(ticker, "SMART", "USD")
        qualified = self.ib.qualifyContracts(stock)
        if not qualified:
            raise RuntimeError(f"could not qualify stock {ticker}")
        self._stock = qualified[0]
        return self._stock

    def _market_prices(self, stock) -> tuple[float, float]:
        bars = self.ib.reqHistoricalData(
            stock,
            endDateTime="",
            durationStr="5 D",
            barSizeSetting="1 day",
            whatToShow="TRADES",
            useRTH=True,
            formatDate=1,
        )
        if not bars:
            ticker = self.ib.reqMktData(stock, "", False, False)
            self.ib.sleep(2)
            last = ticker.last or ticker.close or ticker.marketPrice()
            self.ib.cancelMktData(stock)
            if last is None or (isinstance(last, float) and math.isnan(last)):
                raise RuntimeError(f"no price available for {stock.symbol}")
            return float(last), float(last)
        last = float(bars[-1].close)
        prev = float(bars[-2].close) if len(bars) >= 2 else last
        return last, prev

    def _option_params(self, stock) -> tuple[list[date], list[float]]:
        chains = self.ib.reqSecDefOptParams(
            stock.symbol, "", stock.secType, stock.conId
        )
        smart = [c for c in chains if c.exchange == "SMART"] or chains
        if not smart:
            raise RuntimeError(f"no option chain for {stock.symbol}")
        chain = max(smart, key=lambda c: len(c.expirations) + len(c.strikes))
        expiries = sorted(parse_ib_expiry(e) for e in chain.expirations)
        strikes = sorted(float(s) for s in chain.strikes)
        return expiries, strikes

    def _positions_for(self, ticker: str) -> tuple[int, list[OptionLot], list[OptionLot]]:
        shares = 0
        puts: list[OptionLot] = []
        calls: list[OptionLot] = []
        for pos in self.ib.positions():
            contract = pos.contract
            if contract.symbol != ticker:
                continue
            qty = int(pos.position)
            if contract.secType == "STK":
                shares += qty
            elif contract.secType == "OPT" and qty < 0:
                lot = OptionLot(
                    right=contract.right,  # type: ignore[arg-type]
                    strike=float(contract.strike),
                    expiry=parse_ib_expiry(contract.lastTradeDateOrContractMonth),
                    quantity=qty,
                    con_id=contract.conId,
                )
                if contract.right == "P":
                    puts.append(lot)
                elif contract.right == "C":
                    calls.append(lot)
        return shares, puts, calls

    def _cash(self) -> float:
        values = {}
        for av in self.ib.accountValues():
            if av.currency in ("USD", ""):
                values[av.tag] = av.value
        for key in ("AvailableFunds", "TotalCashValue", "NetLiquidation"):
            raw = values.get(key)
            if raw not in (None, ""):
                try:
                    return float(raw)
                except ValueError:
                    continue
        return 0.0

    def snapshot(self, ticker: str) -> Snapshot:
        stock = self._qualify_stock(ticker)
        last, prev = self._market_prices(stock)
        expiries, strikes = self._option_params(stock)
        shares, puts, calls = self._positions_for(ticker)
        cash = self._cash()
        return Snapshot(
            ticker=ticker,
            last_price=last,
            previous_close=prev,
            shares=shares,
            cash=cash,
            short_puts=tuple(puts),
            short_calls=tuple(calls),
            listed_expiries=tuple(expiries),
            listed_strikes=tuple(strikes),
        )

    def _qualify_option(self, ticker: str, right: str, strike: float, expiry: date):
        from ib_insync import Option

        contract = Option(
            ticker,
            expiry.strftime("%Y%m%d"),
            strike,
            right,
            "SMART",
            tradingClass=ticker,
            currency="USD",
            multiplier="100",
        )
        qualified = self.ib.qualifyContracts(contract)
        if not qualified:
            raise RuntimeError(
                f"could not qualify {ticker} {expiry} {strike}{right}"
            )
        return qualified[0]

    def _limit_price(self, contract) -> float:
        ticker = self.ib.reqMktData(contract, "", False, False)
        self.ib.sleep(2)
        bid = ticker.bid
        ask = ticker.ask
        self.ib.cancelMktData(contract)

        def valid(value) -> bool:
            return value is not None and not (isinstance(value, float) and math.isnan(value)) and value > 0

        mix = self.config.order.limit_vs_mid
        if valid(bid) and valid(ask):
            mid = (bid + ask) / 2.0
            # Seller: blend bid → mid (higher mix = more premium, harder fill)
            price = bid + mix * (mid - bid)
        elif valid(bid):
            price = bid
        elif valid(ask):
            price = ask
        else:
            raise RuntimeError("no bid/ask for option; cannot set a limit")
        # Option prices are typically two decimals
        return max(round(price, 2), 0.01)

    def sell_option(
        self,
        ticker: str,
        right: str,
        strike: float,
        expiry: date,
        quantity: int,
        *,
        dry_run: bool,
    ) -> dict:
        contract = self._qualify_option(ticker, right, strike, expiry)
        limit = self._limit_price(contract)
        from ib_insync import LimitOrder

        order = LimitOrder(
            "SELL",
            quantity,
            limit,
            tif=self.config.order.tif,
            transmit=not dry_run,
        )
        result: dict[str, Any] = {
            "symbol": ticker,
            "right": right,
            "strike": strike,
            "expiry": expiry.isoformat(),
            "quantity": quantity,
            "limit": limit,
            "dry_run": dry_run,
            "con_id": contract.conId,
        }
        if dry_run:
            log.info("DRY RUN would SELL %s %s %s %s @ %s", quantity, ticker, expiry, strike, limit)
            result["status"] = "dry_run"
            return result

        trade = self.ib.placeOrder(contract, order)
        self.ib.sleep(min(self.config.order.wait_fill_sec, 5))
        # Give the order time to work without blocking forever
        waited = 5
        while not trade.isDone() and waited < self.config.order.wait_fill_sec:
            self.ib.sleep(1)
            waited += 1
        result["status"] = trade.orderStatus.status
        result["filled"] = trade.orderStatus.filled
        result["avg_fill"] = trade.orderStatus.avgFillPrice
        log.info(
            "SELL %s %s %s %s status=%s filled=%s avg=%s",
            quantity,
            ticker,
            expiry,
            strike,
            result["status"],
            result["filled"],
            result["avg_fill"],
        )
        return result
