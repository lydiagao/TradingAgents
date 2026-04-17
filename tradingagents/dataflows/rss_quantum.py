"""
§4.1 Quantum-domain RSS feeds. Tier: IMPORTANT.

4 feeds, polled on demand. Deduplicates by URL hash.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Any

import feedparser

from .retry import fetch_with_policy

log = logging.getLogger(__name__)

FEEDS = [
    ("quantum_insider", "https://thequantuminsider.com/feed/"),
    ("quantum_computing_report", "https://quantumcomputingreport.com/feed/"),
    ("hpcwire_quantum", "https://www.hpcwire.com/category/quantum-computing/feed/"),
    ("quantum_zeitgeist", "https://quantumzeitgeist.com/feed/"),
]


def _parse_feed(name: str, url: str) -> list[dict[str, Any]]:
    feed = feedparser.parse(url)
    if feed.bozo and not feed.entries:
        raise ConnectionError(f"RSS feed '{name}' failed: {feed.bozo_exception}")
    entries = []
    for e in feed.entries:
        published = ""
        if hasattr(e, "published_parsed") and e.published_parsed:
            published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc).isoformat()
        entries.append({
            "title": getattr(e, "title", ""),
            "link": getattr(e, "link", ""),
            "published_at": published,
            "source": name,
            "summary": getattr(e, "summary", "")[:500],
            "url_hash": hashlib.md5(getattr(e, "link", "").encode()).hexdigest(),
        })
    return entries


def fetch_single_feed(name: str, url: str) -> list[dict[str, Any]]:
    """Fetch one feed with retry policy (tier=important)."""
    result = fetch_with_policy(
        source_name=f"rss_{name}",
        fetcher=lambda: _parse_feed(name, url),
        tier="important",
        retries=1,
        backoff_base=2.0,
    )
    return result.data if result.ok else []


def fetch_all_feeds() -> list[dict[str, Any]]:
    """Fetch all 4 feeds, deduplicate by URL hash. Tolerates 1-2 feed failures."""
    all_entries: list[dict[str, Any]] = []
    seen_hashes: set[str] = set()

    for name, url in FEEDS:
        entries = fetch_single_feed(name, url)
        for entry in entries:
            h = entry.get("url_hash", "")
            if h not in seen_hashes:
                seen_hashes.add(h)
                all_entries.append(entry)

    log.info("RSS: fetched %d unique entries from %d feeds", len(all_entries), len(FEEDS))
    return all_entries
