"""
§9.3 Per-dimension score normalization. Clamps all raw scores to 0-100.
"""

from __future__ import annotations


def clamp_score(value: float | int | None, default: float = 50.0) -> float:
    """Clamp a score to [0, 100]. None → default."""
    if value is None:
        return default
    return max(0.0, min(100.0, float(value)))


def normalize_dimension_scores(raw: dict[str, float | int | None]) -> dict[str, float]:
    """Clamp all dimension scores to [0, 100]."""
    return {k: clamp_score(v) for k, v in raw.items()}
