"""
P2-T4: Assert every MoomooClient method's return dict carries _source == "moomoo".

These tests hit the LIVE OpenD instance. Skip if OpenD is unavailable.
"""

from __future__ import annotations

import socket

import pytest

from tradingagents.dataflows.moomoo_client import MoomooClient


def _opend_available() -> bool:
    try:
        s = socket.create_connection(("127.0.0.1", 11111), timeout=2)
        s.close()
        return True
    except (OSError, ConnectionRefusedError):
        return False


pytestmark = pytest.mark.skipif(
    not _opend_available(),
    reason="OpenD not running at localhost:11111",
)


@pytest.fixture(scope="module")
def client():
    c = MoomooClient()
    yield c
    c.close()


class TestSourceTag:
    """Every return dict must have _source == 'moomoo'."""

    def test_get_realtime_quote(self, client: MoomooClient):
        result = client.get_realtime_quote("NVDA")
        assert result["_source"] == "moomoo"
        assert "ts_exchange" in result
        assert "ts_received" in result
        assert isinstance(result["price"], float)

    def test_get_session_state(self, client: MoomooClient):
        state = client.get_session_state("NVDA")
        assert state in ("pre_market", "regular", "after_hours", "closed")

    def test_get_historical_klines(self, client: MoomooClient):
        klines = client.get_historical_klines("NVDA", "1d", start="2026-04-14", end="2026-04-14")
        assert len(klines) >= 1
        for bar in klines:
            assert bar["_source"] == "moomoo"
            assert "ts_received" in bar

    def test_get_realtime_quote_ionq(self, client: MoomooClient):
        """Test another ticker from our universe."""
        result = client.get_realtime_quote("IONQ")
        assert result["_source"] == "moomoo"
        assert result["ticker"] == "IONQ"
