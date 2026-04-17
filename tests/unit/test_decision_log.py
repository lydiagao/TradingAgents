"""
P2-T17 test: decision log SQLite round-trip.
"""

from __future__ import annotations

import tempfile
import os

import pytest

from tradingagents.memory.decision_log import DecisionLog


@pytest.fixture
def log():
    tmpfile = tempfile.mktemp(suffix=".db")
    dl = DecisionLog(db_path=tmpfile)
    yield dl
    os.unlink(tmpfile)


class TestDecisionLog:

    def test_write_and_read_decision(self, log: DecisionLog):
        did = log.write_decision(
            ticker="IONQ", action="buy", size_pct=2.5,
            rationale="Strong tech score", final_score=72.0,
            execution_status="paper",
        )
        assert did >= 1
        row = log.get_decision(did)
        assert row is not None
        assert row["ticker"] == "IONQ"
        assert row["action"] == "buy"
        assert row["final_score"] == 72.0

    def test_write_execution_log(self, log: DecisionLog):
        did = log.write_decision(ticker="NVDA", action="hold", execution_status="hold_no_action")
        log.write_execution_log(
            decision_id=did, ticker="NVDA", environment="paper", status="skipped_hold",
            t0_market_tick="2026-04-16T14:00:00.123Z",
            t1_data_fetched="2026-04-16T14:00:00.456Z",
            t2_pipeline_start="2026-04-16T14:00:01.000Z",
            t3_decision_final="2026-04-16T14:00:05.000Z",
            t4_order_submitted=None, t5_order_filled=None,
            data_staleness_ms=333, pipeline_duration_ms=4000,
        )
        exec_row = log.get_execution_log(did)
        assert exec_row is not None
        assert exec_row["status"] == "skipped_hold"
        assert exec_row["t4_order_submitted"] is None
        assert exec_row["data_staleness_ms"] == 333

    def test_write_cost_log(self, log: DecisionLog):
        log.write_cost_log(
            cycle_id="cycle_001", model="claude-sonnet-4-6",
            input_tokens=5000, output_tokens=1000, wall_ms=2500, cost_usd=0.0,
        )
        count = log.count_today_calls()
        assert count >= 1

    def test_nonexistent_decision_returns_none(self, log: DecisionLog):
        assert log.get_decision(9999) is None
