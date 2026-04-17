"""
dataflows — live decision surface (lazy client accessor) per SPEC §4.8.2.

**CRITICAL**: importing this module does NOT open a moomoo connection.
Only calling the public API functions (get_realtime_quote, etc.) triggers
the lazy singleton instantiation.

Decision-path code imports these wrappers:
    from tradingagents.dataflows import get_realtime_quote
    quote = get_realtime_quote("NVDA")

Historical/analysis namespace (yfinance) lives in a separate submodule
and must be imported explicitly:
    from tradingagents.dataflows import historical
    ohlc = historical.get_backtest_ohlc("NVDA")

Guardrail: test_no_yfinance_on_hot_path.py (P2-T5) ensures yfinance
is never imported under agents/ risk/ scoring/ orchestration/ execution/.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .moomoo_client import MoomooClient

_client: Optional["MoomooClient"] = None


def get_client() -> "MoomooClient":
    """Lazy singleton accessor. Raises MoomooConnectionError if OpenD is unreachable."""
    global _client
    if _client is None:
        from .moomoo_client import MoomooClient
        _client = MoomooClient()
    return _client


def reset_client() -> None:
    """Close and reset the singleton (useful for tests)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


# ---- Public live-decision API (thin wrappers) ----------------------------
# Decision code imports THESE, not the client directly.

def get_realtime_quote(ticker: str) -> dict:
    return get_client().get_realtime_quote(ticker)


def get_live_options_chain(ticker: str, expiration: str | None = None) -> dict:
    return get_client().get_live_options_chain(ticker, expiration)


def get_order_book(ticker: str, depth: int = 10) -> dict:
    return get_client().get_order_book(ticker, depth)


def get_session_state(ticker: str) -> str:
    return get_client().get_session_state(ticker)
