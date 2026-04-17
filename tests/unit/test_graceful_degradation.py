"""
P2-T6 test: graceful degradation per SPEC §4.10.

Covers all 3 tiers:
  - CRITICAL: raises CriticalSourceFailure
  - IMPORTANT: returns FetchResult(ok=False), no raise
  - OPTIONAL: returns FetchResult(ok=False), silent skip
  - Success path: returns FetchResult(ok=True)
  - Retry behavior: exponential backoff, correct retry count
"""

from __future__ import annotations

import pytest

from tradingagents.dataflows.retry import (
    FetchResult,
    CriticalSourceFailure,
    fetch_with_policy,
)


def _always_fail():
    raise ConnectionError("simulated failure")


def _always_succeed():
    return {"price": 42.0, "_source": "test"}


class _FailNTimes:
    """Callable that fails N times then succeeds."""
    def __init__(self, n: int):
        self._n = n
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.calls <= self._n:
            raise ConnectionError(f"fail #{self.calls}")
        return {"ok": True}


class TestSuccess:

    def test_returns_data(self):
        r = fetch_with_policy("test_src", _always_succeed, tier="important")
        assert r.ok is True
        assert r.data == {"price": 42.0, "_source": "test"}
        assert r.source == "test_src"
        assert r.tier == "important"
        assert r.retries_used == 0

    def test_retries_then_succeeds(self):
        f = _FailNTimes(2)
        r = fetch_with_policy("flaky", f, tier="important", retries=3, backoff_base=0.01)
        assert r.ok is True
        assert f.calls == 3  # 2 fails + 1 success
        assert r.retries_used == 2


class TestCriticalTier:

    def test_raises_on_failure(self):
        with pytest.raises(CriticalSourceFailure, match="moomoo_quote"):
            fetch_with_policy("moomoo_quote", _always_fail, tier="critical",
                              retries=1, backoff_base=0.01)

    def test_success_does_not_raise(self):
        r = fetch_with_policy("moomoo_quote", _always_succeed, tier="critical")
        assert r.ok is True


class TestImportantTier:

    def test_returns_not_ok_on_failure(self):
        r = fetch_with_policy("sec_edgar", _always_fail, tier="important",
                              retries=1, backoff_base=0.01)
        assert r.ok is False
        assert r.data is None
        assert "ConnectionError" in r.error
        assert r.tier == "important"

    def test_retries_used(self):
        r = fetch_with_policy("newsapi", _always_fail, tier="important",
                              retries=2, backoff_base=0.01)
        assert r.retries_used == 2


class TestOptionalTier:

    def test_returns_not_ok_silently(self):
        r = fetch_with_policy("arxiv", _always_fail, tier="optional",
                              retries=0, backoff_base=0.01)
        assert r.ok is False
        assert r.tier == "optional"


class TestValidation:

    def test_invalid_tier_raises_value_error(self):
        with pytest.raises(ValueError, match="Invalid tier"):
            fetch_with_policy("x", _always_succeed, tier="nonexistent")

    def test_tier_case_insensitive(self):
        r = fetch_with_policy("x", _always_succeed, tier="CRITICAL")
        assert r.ok is True
        assert r.tier == "critical"
