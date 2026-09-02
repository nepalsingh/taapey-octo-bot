from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from wheel_bot.models import Decision, RunRecord


def load_state(path: str | Path) -> dict[str, Any]:
    file = Path(path)
    if not file.exists():
        return {"runs": []}
    return json.loads(file.read_text(encoding="utf-8"))


def append_run(path: str | Path, record: RunRecord) -> None:
    file = Path(path)
    file.parent.mkdir(parents=True, exist_ok=True)
    state = load_state(file)
    runs = state.setdefault("runs", [])
    payload = {
        "timestamp": record.timestamp,
        "ticker": record.ticker,
        "action": record.action,
        "reason": record.reason,
        "strike": record.strike,
        "expiry": record.expiry,
        "dry_run": record.dry_run,
        "extra": record.extra,
    }
    runs.append(payload)
    state["last"] = payload
    file.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def record_from_decision(
    ticker: str, decision: Decision, *, dry_run: bool, extra: dict | None = None
) -> RunRecord:
    return RunRecord(
        timestamp=RunRecord.now_iso(),
        ticker=ticker,
        action=decision.action.value,
        reason=decision.reason,
        strike=decision.strike,
        expiry=decision.expiry.isoformat() if decision.expiry else None,
        dry_run=dry_run,
        extra=extra or {},
    )
