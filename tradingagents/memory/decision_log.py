"""
§8.4 Decision log — SQLite persistence for decisions, execution, outcomes, cost.

All timestamps are UTC ISO8601 with 'Z' suffix.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import sqlalchemy as sa
from sqlalchemy import create_engine, MetaData, Table, Column, Integer, Text, Float

log = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.getenv(
    "QUANTUM_AGENT_DB",
    str(Path.home() / ".tradingagents" / "decision_log.db"),
)

metadata = MetaData()

decisions = Table(
    "decisions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("ticker", Text, nullable=False),
    Column("timestamp", Text, nullable=False),
    Column("action", Text, nullable=False),
    Column("size_pct", Float),
    Column("rationale", Text),
    Column("bull_thesis", Text),
    Column("bear_thesis", Text),
    Column("final_score", Float),
    Column("cost_usd", Float),
    Column("model_calls_json", Text),
    Column("execution_status", Text),
    Column("block_reason", Text),
)

execution_log = Table(
    "execution_log", metadata,
    Column("decision_id", Integer, primary_key=True),
    Column("ticker", Text, nullable=False),
    Column("environment", Text, nullable=False),
    Column("status", Text, nullable=False),
    # Six raw timestamps (UTC ISO8601 with ms)
    Column("t0_market_tick", Text),
    Column("t1_data_fetched", Text),
    Column("t2_pipeline_start", Text),
    Column("t3_decision_final", Text),
    Column("t4_order_submitted", Text),
    Column("t5_order_filled", Text),
    # Six derived latencies (ms)
    Column("data_staleness_ms", Integer),
    Column("pipeline_duration_ms", Integer),
    Column("submission_latency_ms", Integer),
    Column("fill_latency_ms", Integer),
    Column("total_decision_to_fill_ms", Integer),
    Column("total_market_to_fill_ms", Integer),
    # Pricing
    Column("price_at_fetch", Float),
    Column("price_at_submit", Float),
    Column("fill_price", Float),
    Column("slippage_bps", Float),
    # Order details
    Column("moomoo_order_id", Text),
    Column("order_qty", Integer),
    Column("fill_qty", Integer),
)

outcomes = Table(
    "outcomes", metadata,
    Column("decision_id", Integer, primary_key=True),
    Column("entry_price", Float),
    Column("exit_price", Float),
    Column("pnl_pct", Float),
    Column("hold_days", Integer),
)

cost_log = Table(
    "cost_log", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("timestamp", Text, nullable=False),
    Column("cycle_id", Text),
    Column("model", Text),
    Column("input_tokens", Integer),
    Column("output_tokens", Integer),
    Column("wall_ms", Integer),
    Column("cost_usd", Float),
)


class DecisionLog:
    """SQLite-backed decision log."""

    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._engine = create_engine(f"sqlite:///{db_path}")
        metadata.create_all(self._engine)

    def write_decision(self, **kwargs) -> int:
        """Insert a decision row. Returns the new decision ID."""
        if "timestamp" not in kwargs:
            kwargs["timestamp"] = datetime.now(timezone.utc).isoformat()
        with self._engine.begin() as conn:
            result = conn.execute(decisions.insert().values(**kwargs))
            return result.inserted_primary_key[0]

    def write_execution_log(self, **kwargs) -> None:
        """Insert an execution_log row."""
        with self._engine.begin() as conn:
            conn.execute(execution_log.insert().values(**kwargs))

    def write_outcome(self, **kwargs) -> None:
        with self._engine.begin() as conn:
            conn.execute(outcomes.insert().values(**kwargs))

    def write_cost_log(self, **kwargs) -> None:
        if "timestamp" not in kwargs:
            kwargs["timestamp"] = datetime.now(timezone.utc).isoformat()
        with self._engine.begin() as conn:
            conn.execute(cost_log.insert().values(**kwargs))

    def get_decision(self, decision_id: int) -> dict | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                decisions.select().where(decisions.c.id == decision_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def get_execution_log(self, decision_id: int) -> dict | None:
        with self._engine.connect() as conn:
            row = conn.execute(
                execution_log.select().where(execution_log.c.decision_id == decision_id)
            ).fetchone()
            return dict(row._mapping) if row else None

    def count_today_calls(self) -> int:
        """Count cost_log entries for today (UTC)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        with self._engine.connect() as conn:
            result = conn.execute(
                sa.select(sa.func.count()).select_from(cost_log).where(
                    cost_log.c.timestamp.like(f"{today}%")
                )
            ).scalar()
            return result or 0
