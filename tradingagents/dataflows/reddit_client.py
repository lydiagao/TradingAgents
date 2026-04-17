"""
§4.5 Reddit client via PRAW (OAuth required). Tier: IMPORTANT.

No unauthenticated fallback — missing creds raise clearly at call time.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from .retry import fetch_with_policy

log = logging.getLogger(__name__)

SUBREDDITS = ["QuantumComputing", "wallstreetbets", "stocks", "investing"]


def _get_reddit():
    """Lazy import + construct PRAW Reddit instance."""
    import praw

    client_id = os.getenv("REDDIT_CLIENT_ID", "")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
    user_agent = os.getenv("REDDIT_USER_AGENT", "QuantumTradingAgent/0.1")

    if not client_id or not client_secret:
        raise EnvironmentError(
            "REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET must be set. "
            "Register at https://www.reddit.com/prefs/apps (free)."
        )

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent,
    )


def _fetch_subreddit(subreddit_name: str, limit: int = 50) -> list[dict[str, Any]]:
    reddit = _get_reddit()
    submissions = []
    for sub in reddit.subreddit(subreddit_name).new(limit=limit):
        submissions.append({
            "title": sub.title,
            "url": f"https://reddit.com{sub.permalink}",
            "score": sub.score,
            "num_comments": sub.num_comments,
            "created_utc": sub.created_utc,
            "subreddit": subreddit_name,
            "source": f"reddit_{subreddit_name}",
            "selftext": (sub.selftext or "")[:300],
        })
    return submissions


def fetch_quantum_reddit(limit: int = 50) -> list[dict[str, Any]]:
    """Fetch from r/QuantumComputing. Tier=important."""
    result = fetch_with_policy(
        "reddit_QuantumComputing",
        lambda: _fetch_subreddit("QuantumComputing", limit),
        tier="important", retries=1, backoff_base=2.0,
    )
    return result.data if result.ok else []


def fetch_all_subreddits(limit: int = 25) -> list[dict[str, Any]]:
    """Fetch from all tracked subreddits."""
    all_posts: list[dict[str, Any]] = []
    for sub_name in SUBREDDITS:
        result = fetch_with_policy(
            f"reddit_{sub_name}",
            lambda name=sub_name: _fetch_subreddit(name, limit),
            tier="important", retries=1, backoff_base=2.0,
        )
        if result.ok:
            all_posts.extend(result.data or [])
    return all_posts
