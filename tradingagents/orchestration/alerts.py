"""
§11.4 Alerts — Gmail via MCP (configured by user).

For now, logs alerts. Gmail MCP integration to be configured in Phase 6 ops.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def alert_decision(decision: dict[str, Any]) -> None:
    """Send decision summary after each cycle."""
    log.info(
        "ALERT [decision] %s → %s (confidence: %s)",
        decision.get("ticker"), decision.get("action"), decision.get("confidence"),
    )


def alert_error(ticker: str, error: Exception) -> None:
    """Critical error — immediate notification."""
    log.error("ALERT [error] %s: %s", ticker, error)


def alert_cost(call_count: int) -> None:
    """Call count threshold breached."""
    log.warning("ALERT [cost] Daily CLI calls at %d", call_count)
