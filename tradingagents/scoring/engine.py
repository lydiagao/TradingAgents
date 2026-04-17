"""
§9.1-9.3 Stage-weighted scoring engine.

Detects company maturity stage, applies dimension weights, computes composite score.
§4.10: data_incomplete dimensions have their weight × 0.5.
"""

from __future__ import annotations

from typing import Any

STAGE_WEIGHTS: dict[str, dict[str, float]] = {
    "pre_revenue": {
        "financial_health": 0.40, "tech": 0.30, "commercialization": 0.05,
        "strategic_actions": 0.10, "regulatory": 0.10,
        "macro_rotation": 0.03, "technicals_flow": 0.02,
    },
    "early_revenue": {
        "financial_health": 0.25, "tech": 0.25, "commercialization": 0.25,
        "strategic_actions": 0.10, "regulatory": 0.08,
        "macro_rotation": 0.04, "technicals_flow": 0.03,
    },
    "scaling": {
        "financial_health": 0.15, "tech": 0.15, "commercialization": 0.30,
        "strategic_actions": 0.15, "regulatory": 0.08,
        "macro_rotation": 0.10, "technicals_flow": 0.07,
    },
    "established": {
        "financial_health": 0.20, "tech": 0.10, "commercialization": 0.20,
        "strategic_actions": 0.10, "regulatory": 0.10,
        "macro_rotation": 0.15, "technicals_flow": 0.15,
    },
}


def detect_stage(ticker: str, financials: dict) -> str:
    """Detect company maturity stage per §9.1."""
    ttm_revenue = financials.get("ttm_revenue_usd", 0) or 0
    revenue_growth_yoy = financials.get("revenue_growth_yoy", 0) or 0

    if ttm_revenue < 1_000_000:
        return "pre_revenue"
    elif ttm_revenue < 50_000_000:
        return "early_revenue"
    elif revenue_growth_yoy > 0.5:
        return "scaling"
    else:
        return "established"


def compute_score(
    ticker: str,
    agent_outputs: dict[str, Any],
    financials: dict,
    data_incomplete_agents: list[str] | None = None,
) -> dict[str, Any]:
    """Compute stage-weighted composite score per §9.3.

    §4.10: data_incomplete dimensions have weight × 0.5.
    """
    stage = detect_stage(ticker, financials)
    weights = dict(STAGE_WEIGHTS[stage])
    data_incomplete_agents = data_incomplete_agents or []

    # Map dimensions to agent output fields
    dimension_to_agent = {
        "financial_health": ("valuation_health", "financial_health_score"),
        "tech": ("quantum_tech_expert", "tech_score"),
        "commercialization": ("commercialization", "commercialization_score"),
        "strategic_actions": ("news", "strategic_score"),
        "regulatory": ("regulatory_policy", "policy_score"),
        "macro_rotation": ("sentiment", "macro_score"),
        "technicals_flow": ("flow_technicals", "flow_score"),
    }

    raw_scores: dict[str, float] = {}
    degraded_dimensions: list[str] = []

    for dim, (agent_name, field) in dimension_to_agent.items():
        agent_data = agent_outputs.get(agent_name)
        if agent_data is None or agent_name in data_incomplete_agents:
            raw_scores[dim] = 50  # neutral fallback
            weights[dim] *= 0.5  # §4.10 confidence discount
            degraded_dimensions.append(dim)
        else:
            raw_scores[dim] = max(0, min(100, agent_data.get(field, 50)))

    # Renormalize weights after any degradation
    total_weight = sum(weights.values())
    if total_weight > 0:
        weights = {k: v / total_weight for k, v in weights.items()}

    weighted_score = sum(raw_scores[k] * weights[k] for k in weights)

    return {
        "ticker": ticker,
        "stage": stage,
        "weighted_score": round(weighted_score, 2),
        "dimension_scores": raw_scores,
        "weights_applied": {k: round(v, 4) for k, v in weights.items()},
        "degraded_dimensions": degraded_dimensions,
    }
