"""
§10A.4 Paper executor — handles order submission in SIMULATE mode.

5 status branches:
  "skipped_hold"  — action=="hold"
  "filled"        — full fill
  "partial"       — partial fill
  "rejected"      — moomoo returned rejection
  "timeout"       — wait_for_fill hit timeout; do NOT retry
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from tradingagents.dataflows.moomoo_client import MoomooClient

log = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def execute_paper(
    decision: dict[str, Any],
    client: MoomooClient,
    timeout_sec: int = 10,
) -> dict[str, Any]:
    """Execute a paper order based on the pipeline decision.

    Args:
        decision: PM decision dict with action, ticker, etc.
        client: MoomooClient instance (connected to OpenD).
        timeout_sec: wait_for_fill timeout.

    Returns:
        Execution result dict with status, timestamps T4/T5, fill details.
    """
    action = decision.get("action", "hold")
    ticker = decision.get("ticker", "")

    if action == "hold":
        return {
            "ticker": ticker,
            "status": "skipped_hold",
            "t4_order_submitted": None,
            "t5_order_filled": None,
            "fill_price": None,
            "fill_qty": 0,
            "moomoo_order_id": None,
        }

    side = "BUY" if action == "buy" else "SELL"
    qty = decision.get("qty", 1)

    # T4: order submission
    t4 = _utc_now()
    try:
        order_result = client.place_order(
            ticker=ticker,
            side=side,
            qty=qty,
            order_type="NORMAL",
            trd_env="SIMULATE",
        )
    except Exception as e:
        log.error("Paper order failed for %s: %s", ticker, e)
        return {
            "ticker": ticker,
            "status": "rejected",
            "t4_order_submitted": t4,
            "t5_order_filled": None,
            "fill_price": None,
            "fill_qty": 0,
            "error": str(e),
            "moomoo_order_id": None,
        }

    order_id = order_result.get("order_id", "")

    # Wait for fill
    try:
        fill_result = client.wait_for_fill(
            order_id=order_id,
            timeout_sec=timeout_sec,
            trd_env="SIMULATE",
        )
    except Exception as e:
        log.error("wait_for_fill failed for %s: %s", order_id, e)
        return {
            "ticker": ticker,
            "status": "timeout",
            "t4_order_submitted": t4,
            "t5_order_filled": None,
            "fill_price": None,
            "fill_qty": 0,
            "moomoo_order_id": order_id,
        }

    t5 = fill_result.get("ts_filled")
    status = fill_result.get("status", "timeout")

    return {
        "ticker": ticker,
        "status": status,
        "t4_order_submitted": t4,
        "t5_order_filled": t5,
        "fill_price": fill_result.get("fill_price"),
        "fill_qty": fill_result.get("fill_qty", 0),
        "moomoo_order_id": order_id,
    }
