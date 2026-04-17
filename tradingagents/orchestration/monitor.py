"""
§11 Monitor — single-command health dump.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tradingagents.memory.decision_log import DecisionLog
from tradingagents.risk.kill_switch import KILL_FILE
from tradingagents.orchestration.latency_report import generate_latency_report


def health_dump(decision_log: DecisionLog | None = None) -> dict[str, Any]:
    """Single-command health check: latest decision, cost, kill switch, latency."""
    dl = decision_log or DecisionLog()

    # Latest decision
    latest = None
    with dl._engine.connect() as conn:
        from tradingagents.memory.decision_log import decisions
        row = conn.execute(
            decisions.select().order_by(decisions.c.id.desc()).limit(1)
        ).fetchone()
        if row:
            latest = dict(row._mapping)

    # Kill switch
    kill_active = KILL_FILE.exists()

    # Latency
    latency = generate_latency_report(dl, days=7)

    # Today's calls
    today_calls = dl.count_today_calls()

    return {
        "latest_decision": latest,
        "kill_switch_active": kill_active,
        "today_cli_calls": today_calls,
        "latency_7d": latency,
    }
