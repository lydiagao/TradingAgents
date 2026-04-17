"""
§11.3 Usage tracker — daily + per-cycle call count monitoring.

ADR-2026-04-16: CLI subscription mode, no per-token billing.
Tracker monitors call counts to prevent runaway loops.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from tradingagents.memory.decision_log import DecisionLog

log = logging.getLogger(__name__)

DAILY_CALL_ALERT = int(os.getenv("DAILY_CALL_ALERT", "200"))
DAILY_CALL_HARD_STOP = int(os.getenv("DAILY_CALL_HARD_STOP", "400"))
PER_CYCLE_CALL_HARD_STOP = int(os.getenv("PER_CYCLE_CALL_HARD_STOP", "80"))
CLI_MAX_CONCURRENCY = int(os.getenv("CLI_MAX_CONCURRENCY", "4"))


class CostTracker:

    def __init__(self, decision_log: DecisionLog | None = None):
        self._log = decision_log or DecisionLog()
        self._cycle_calls: dict[str, int] = {}

    def track_call(
        self, model: str, input_tokens: int = 0, output_tokens: int = 0,
        wall_ms: int = 0, cycle_id: str = "",
    ) -> None:
        self._log.write_cost_log(
            cycle_id=cycle_id, model=model,
            input_tokens=input_tokens, output_tokens=output_tokens,
            wall_ms=wall_ms, cost_usd=0.0,
        )
        self._cycle_calls[cycle_id] = self._cycle_calls.get(cycle_id, 0) + 1

    def check_daily_calls(self) -> None:
        today_calls = self._log.count_today_calls()
        if today_calls > DAILY_CALL_HARD_STOP:
            raise RuntimeError(f"Daily CLI call hard stop hit: {today_calls}")
        if today_calls > DAILY_CALL_ALERT:
            log.warning("Daily CLI calls approaching limit: %d", today_calls)

    def check_per_cycle_calls(self, cycle_id: str) -> None:
        calls = self._cycle_calls.get(cycle_id, 0)
        if calls > PER_CYCLE_CALL_HARD_STOP:
            raise RuntimeError(f"Per-cycle call hard stop hit: {calls}")
