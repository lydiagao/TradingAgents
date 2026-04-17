"""
Graceful degradation helper per SPEC §4.10.

Three criticality tiers:
  CRITICAL  — pipeline halts for the affected ticker (e.g. moomoo quote)
  IMPORTANT — agent marks data_incomplete=True, scoring weight × 0.5
  OPTIONAL  — silently skip, log at DEBUG

Usage:
    result = fetch_with_policy("sec_edgar_10q", fetch_10q, tier="important")
    if not result.ok:
        state["data_incomplete"] = True
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger(__name__)

VALID_TIERS = frozenset({"critical", "important", "optional"})


@dataclass
class FetchResult:
    """Outcome of a data-source fetch attempt."""
    ok: bool
    data: dict | list | None
    source: str
    tier: str
    error: str | None = None
    retries_used: int = 0


class CriticalSourceFailure(RuntimeError):
    """Raised when a CRITICAL-tier source fails after all retries.

    Callers should halt the pipeline for the affected ticker.
    """

    def __init__(self, source: str, error: str):
        self.source = source
        super().__init__(f"CRITICAL source '{source}' failed: {error}")


def fetch_with_policy(
    source_name: str,
    fetcher: Callable[[], Any],
    tier: str,
    retries: int = 2,
    backoff_base: float = 1.0,
) -> FetchResult:
    """Call `fetcher()` with retry + exponential backoff, then apply tier policy.

    Args:
        source_name: Human-readable source identifier (for logging + FetchResult.source).
        fetcher: Zero-arg callable that returns data on success or raises on failure.
        tier: One of 'critical', 'important', 'optional'.
        retries: Max retry count (0 = no retries, just one attempt).
        backoff_base: Seconds for first backoff; doubles each retry.

    Returns:
        FetchResult with ok=True and data on success, or ok=False on failure.

    Raises:
        CriticalSourceFailure: If tier='critical' and all attempts fail.
        ValueError: If tier is not valid.
    """
    tier = tier.lower()
    if tier not in VALID_TIERS:
        raise ValueError(f"Invalid tier={tier!r}; must be one of {sorted(VALID_TIERS)}")

    last_error: str | None = None
    for attempt in range(1 + retries):
        try:
            data = fetcher()
            return FetchResult(
                ok=True, data=data, source=source_name, tier=tier,
                retries_used=attempt,
            )
        except Exception as e:
            last_error = f"{type(e).__name__}: {e}"
            if attempt < retries:
                wait = backoff_base * (2 ** attempt)
                log.debug(
                    "fetch_with_policy(%s, tier=%s): attempt %d/%d failed (%s), "
                    "retrying in %.1fs",
                    source_name, tier, attempt + 1, 1 + retries, last_error, wait,
                )
                time.sleep(wait)

    # All attempts exhausted.
    log.warning(
        "fetch_with_policy(%s, tier=%s): all %d attempts failed: %s",
        source_name, tier, 1 + retries, last_error,
    )

    if tier == "critical":
        raise CriticalSourceFailure(source_name, last_error or "unknown error")

    if tier == "optional":
        log.debug("Optional source '%s' failed — silently skipping.", source_name)

    # For 'important': caller reads result.ok == False and acts accordingly.
    return FetchResult(
        ok=False, data=None, source=source_name, tier=tier,
        error=last_error, retries_used=retries,
    )
