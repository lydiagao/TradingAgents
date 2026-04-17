"""
Inter-agent schema contracts per SPEC §8.5.

Every agent that produces structured JSON validates its output against the
corresponding Pydantic model here. Validation failures are caught and surfaced
as `data_incomplete: True` (per §4.10) rather than raising into the graph.

9 agent output schemas:
  - 5 novel quantum agents: QuantumTech, Commercialization, ValuationHealth,
    Regulatory, FlowTechnicals
  - 2 modified traditional agents: News (+ strategic_score), Sentiment (+ macro_score)
  - 2 traditional stubs: Technical, Fundamentals (minimal until Phase 3 rewrite)
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Novel quantum agents (§7.1 — §7.5)
# ---------------------------------------------------------------------------

class QuantumTechOutput(BaseModel):
    """§7.1 Quantum Tech Expert output."""
    tech_score: int = Field(ge=0, le=100)
    position_vs_peers: Literal["leader", "competitive", "laggard"]
    roadmap_credibility: Literal["high", "medium", "low"]
    key_risks: list[str]
    time_to_advantage: str
    reasoning: str


class CommercializationOutput(BaseModel):
    """§7.2 Commercialization Analyst output.

    Hard rule: TTM revenue < $1M → commercialization_score capped at 30.
    """
    commercialization_score: int = Field(ge=0, le=100)
    score_delta_this_cycle: int = Field(ge=-10, le=10)
    dimensions: dict[str, int]
    recent_signals: list[dict]
    reasoning: str


class ValuationHealthOutput(BaseModel):
    """§7.3 Valuation & Financial Health output.

    Hard rules: runway < 4Q → score ≤ 40; going-concern → score ≤ 20.
    """
    financial_health_score: int = Field(ge=0, le=100)
    valuation_tier: Literal["cheap", "fair", "rich", "bubble"]
    runway_quarters: int
    dilution_probability_12m: float = Field(ge=0.0, le=1.0)
    red_flags: list[str]
    reasoning: str


class RegulatoryPolicyOutput(BaseModel):
    """§7.4 Regulatory & Policy Analyst output."""
    policy_score: int = Field(ge=0, le=100)
    tailwinds: list[str]
    headwinds: list[str]
    pending_catalysts: list[dict]
    reasoning: str


class FlowTechnicalsOutput(BaseModel):
    """§7.5 Flow & Technicals Analyst output."""
    flow_score: int = Field(ge=0, le=100)
    positioning_bias: Literal["bullish", "neutral", "bearish"]
    squeeze_risk: Literal["high", "medium", "low"]
    key_observations: list[str]


# ---------------------------------------------------------------------------
# Modified traditional agents (§7.6, Session 0a hardening)
# ---------------------------------------------------------------------------

class NewsOutput(BaseModel):
    """§7.6 News Analyst output — includes strategic_score (0-100, 50=neutral).

    strategic_score is read by the Scoring Engine (§9.3).
    """
    headline_summary: str
    strategic_score: int = Field(ge=0, le=100)
    recent_events: list[dict]
    reasoning: str


class SentimentOutput(BaseModel):
    """§7.6 Sentiment Analyst output — includes macro_score (0-100, 50=neutral).

    macro_score is read by the Scoring Engine (§9.3).
    """
    sentiment_bias: Literal["bullish", "neutral", "bearish"]
    macro_score: int = Field(ge=0, le=100)
    retail_heat: Literal["high", "medium", "low"]
    reasoning: str


# ---------------------------------------------------------------------------
# Traditional agent stubs (§7.6 — minimal until Phase 3 rewrite)
# ---------------------------------------------------------------------------

class TechnicalOutput(BaseModel):
    """Technical Analyst output stub. Will be expanded in Phase 3 §7.6."""
    trend: Literal["bullish", "neutral", "bearish"]
    support_level: float
    resistance_level: float
    indicators_summary: str
    reasoning: str


class FundamentalsOutput(BaseModel):
    """Fundamentals Analyst output stub. Phase 3 adds RPO, cash runway, qubit count."""
    revenue_growth_yoy: float
    pe_ratio: float | None = None
    key_metrics: dict[str, float]
    reasoning: str


# ---------------------------------------------------------------------------
# Convenience exports
# ---------------------------------------------------------------------------

ALL_SCHEMAS: dict[str, type[BaseModel]] = {
    "quantum_tech_expert": QuantumTechOutput,
    "commercialization": CommercializationOutput,
    "valuation_health": ValuationHealthOutput,
    "regulatory_policy": RegulatoryPolicyOutput,
    "flow_technicals": FlowTechnicalsOutput,
    "news": NewsOutput,
    "sentiment": SentimentOutput,
    "technical": TechnicalOutput,
    "fundamentals": FundamentalsOutput,
}
