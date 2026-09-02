# taapey-octo-bot

Python options **wheel** bot for [Interactive Brokers](https://www.interactivebrokers.com/) (TWS / IB Gateway via `ib_insync`).

## Strategy

Configurable ticker (default **SPY**) and OTM percent (default **3%**):

1. **Sell a cash-secured put** with strike ≈ `current price × (1 − otm_percent)` and collect the premium.
2. **If assigned** (shares show up the next session): **sell a covered call** with strike ≈ `previous close × (1 + otm_percent)`.
3. **If the put expires worthless**: sell a new put, again ~`otm_percent` below the current price.

While a short put or short call is still open, the bot holds.

`--dte` (default `1`) picks the first listed expiry on or after today + DTE, which matches “assigned the next day” for near-dated SPY options.

## Configure ticker and percent

| Source | Example |
| --- | --- |
| CLI | `--ticker SPY --otm-percent 3` |
| YAML | `ticker: SPY` and `otm_percent: 0.03` (see `config.example.yaml`) |
| Env | `WHEEL_TICKER=SPY` `WHEEL_OTM_PERCENT=3` |
| Per-leg | `--put-otm-percent 3 --call-otm-percent 3` or YAML `put_otm_percent` / `call_otm_percent` |

`3` and `0.03` both mean 3%.

## Setup

1. Install [TWS](https://www.interactivebrokers.com/en/trading/tws.php) or IB Gateway. Enable **API → Enable ActiveX and Socket Clients**. Paper port is typically **7497** (TWS) or **4002** (Gateway).
2. Python 3.10+:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Copy `config.example.yaml` to `config.yaml` and set `ticker`, `otm_percent`, host/port, and `dry_run`.

## Run

Dry-run against IB (no orders sent; `dry_run: true` in the example config):

```bash
python -m wheel_bot --config config.yaml --once
```

Simulate the decision with fake prices (no TWS required):

```bash
python -m wheel_bot --simulate --ticker SPY --otm-percent 3 --price 500
python -m wheel_bot --simulate --assigned --previous-close 500 --price 490
```

Live orders (paper or funded account — you are responsible for fills, margin, and assignment):

```bash
python -m wheel_bot --config config.yaml --live --once
```

Leave off `--once` to poll every `poll_seconds`. A cron job with `--once` after the cash open is the usual pattern so assignment is visible.

## Tests

```bash
pip install -r requirements.txt
python -m pytest
```

## Safety

- Default is **dry_run**. `--live` transmits limit sell orders.
- Cash-secured puts require roughly `strike × 100 × quantity` of cash; the bot will hold if cash is short.
- Covered calls are only sold when the account already holds at least `100 × quantity` shares.
- This is not investment advice. Options can be assigned early, and IB paper/live behavior differs.
