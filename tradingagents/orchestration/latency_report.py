"""
§10A.7 Daily latency report — p50/p95 + red-zone breach list.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from tradingagents.memory.decision_log import DecisionLog, execution_log

log = logging.getLogger(__name__)


def generate_latency_report(
    decision_log: DecisionLog | None = None,
    days: int = 7,
) -> dict[str, Any]:
    """Generate latency statistics from the last N days of execution_log."""
    dl = decision_log or DecisionLog()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    with dl._engine.connect() as conn:
        rows = conn.execute(
            execution_log.select().where(
                execution_log.c.t3_decision_final > cutoff
            )
        ).fetchall()

    if not rows:
        return {"period_days": days, "count": 0, "message": "No execution data"}

    latencies = {
        "data_staleness_ms": [],
        "pipeline_duration_ms": [],
        "total_market_to_fill_ms": [],
    }

    for row in rows:
        r = row._mapping
        for key in latencies:
            val = r.get(key)
            if val is not None:
                latencies[key].append(val)

    report: dict[str, Any] = {"period_days": days, "count": len(rows)}
    for key, vals in latencies.items():
        if vals:
            vals_sorted = sorted(vals)
            report[f"{key}_p50"] = vals_sorted[len(vals_sorted) // 2]
            report[f"{key}_p95"] = vals_sorted[int(len(vals_sorted) * 0.95)]
        else:
            report[f"{key}_p50"] = None
            report[f"{key}_p95"] = None

    return report
