"""
§4.4 NewsAPI.org client with 100/day rate budget. Tier: IMPORTANT.

Budget: 100 req/day free tier. Over-budget → FetchResult(ok=False).
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import requests

from .retry import fetch_with_policy

log = logging.getLogger(__name__)

NEWSAPI_BASE = "https://newsapi.org/v2/everything"
DAILY_BUDGET = 100


class _DailyBudget:
    """Simple in-memory daily call counter. Resets at midnight UTC."""

    def __init__(self, limit: int = DAILY_BUDGET):
        self.limit = limit
        self._count = 0
        self._day: int = 0  # day-of-year

    def _check_reset(self):
        today = time.gmtime().tm_yday
        if today != self._day:
            self._count = 0
            self._day = today

    def try_consume(self) -> bool:
        self._check_reset()
        if self._count >= self.limit:
            return False
        self._count += 1
        return True

    @property
    def remaining(self) -> int:
        self._check_reset()
        return max(0, self.limit - self._count)


_budget = _DailyBudget()


def _fetch_news(query: str) -> list[dict[str, Any]]:
    api_key = os.getenv("NEWSAPI_KEY", "")
    if not api_key:
        raise EnvironmentError("NEWSAPI_KEY not set in environment")

    if not _budget.try_consume():
        raise RuntimeError(f"NewsAPI daily budget exhausted ({DAILY_BUDGET}/day)")

    resp = requests.get(
        NEWSAPI_BASE,
        params={"q": query, "sortBy": "publishedAt", "apiKey": api_key, "pageSize": 10},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    articles = data.get("articles", [])
    return [
        {
            "title": a.get("title", ""),
            "url": a.get("url", ""),
            "published_at": a.get("publishedAt", ""),
            "source": f"newsapi_{a.get('source', {}).get('name', 'unknown')}",
            "description": (a.get("description") or "")[:300],
        }
        for a in articles
    ]


def fetch_news(query: str) -> list[dict[str, Any]]:
    """Fetch news for query. Tier=important per §4.10."""
    result = fetch_with_policy(
        f"newsapi_{query}", lambda: _fetch_news(query),
        tier="important", retries=1, backoff_base=2.0,
    )
    return result.data if result.ok else []


def budget_remaining() -> int:
    return _budget.remaining
