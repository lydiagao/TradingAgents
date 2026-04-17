"""
P2-T7 test: Pydantic schema validation for all 9 agent outputs.

Per SPEC §8.5:
  - Golden JSON fixture per agent validates.
  - Mutated fixtures (missing key, out-of-range value, wrong enum literal)
    fail validation with a clear error.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from tradingagents.memory.schemas import (
    ALL_SCHEMAS,
    QuantumTechOutput,
    CommercializationOutput,
    ValuationHealthOutput,
    RegulatoryPolicyOutput,
    FlowTechnicalsOutput,
    NewsOutput,
    SentimentOutput,
    TechnicalOutput,
    FundamentalsOutput,
)


# ---------------------------------------------------------------------------
# Golden fixtures — one valid example per schema
# ---------------------------------------------------------------------------
GOLDEN_FIXTURES: dict[str, dict] = {
    "quantum_tech_expert": {
        "tech_score": 72,
        "position_vs_peers": "competitive",
        "roadmap_credibility": "medium",
        "key_risks": ["decoherence wall", "manufacturing yield"],
        "time_to_advantage": "3-5 years",
        "reasoning": "IonQ's trapped-ion approach shows strong gate fidelity...",
    },
    "commercialization": {
        "commercialization_score": 28,
        "score_delta_this_cycle": -2,
        "dimensions": {"revenue": 10, "contracts": 35, "partnerships": 40},
        "recent_signals": [{"type": "MOU", "impact_weight": 0.3}],
        "reasoning": "Pre-revenue company with mostly MOUs...",
    },
    "valuation_health": {
        "financial_health_score": 45,
        "valuation_tier": "rich",
        "runway_quarters": 6,
        "dilution_probability_12m": 0.35,
        "red_flags": ["high burn rate"],
        "reasoning": "Cash runway of 6 quarters...",
    },
    "regulatory_policy": {
        "policy_score": 65,
        "tailwinds": ["DARPA QBI Stage B award to IonQ"],
        "headwinds": ["NIST PQC timeline uncertainty"],
        "pending_catalysts": [{"event": "DOE quantum allocation", "date": "2026-Q3"}],
        "reasoning": "Moderate policy tailwinds from DARPA...",
    },
    "flow_technicals": {
        "flow_score": 55,
        "positioning_bias": "neutral",
        "squeeze_risk": "low",
        "key_observations": ["IV rank 45th percentile", "Volume declining"],
    },
    "news": {
        "headline_summary": "IonQ announces new partnership with BMW",
        "strategic_score": 62,
        "recent_events": [{"headline": "IonQ-BMW deal", "source": "quantum_insider"}],
        "reasoning": "Partnership is a demand signal...",
    },
    "sentiment": {
        "sentiment_bias": "bullish",
        "macro_score": 58,
        "retail_heat": "medium",
        "reasoning": "Reddit quantum community moderately positive...",
    },
    "technical": {
        "trend": "bullish",
        "support_level": 42.50,
        "resistance_level": 48.00,
        "indicators_summary": "RSI 58, above 50 SMA, MACD bullish cross",
        "reasoning": "Price above key moving averages...",
    },
    "fundamentals": {
        "revenue_growth_yoy": 0.85,
        "pe_ratio": None,
        "key_metrics": {"cash": 450_000_000, "rpo": 25_000_000},
        "reasoning": "85% YoY revenue growth but still pre-profit...",
    },
}


class TestAllSchemasPresent:

    def test_nine_schemas(self):
        assert len(ALL_SCHEMAS) == 9

    def test_golden_fixtures_cover_all(self):
        assert set(GOLDEN_FIXTURES.keys()) == set(ALL_SCHEMAS.keys())


class TestGoldenFixtures:
    """Every golden fixture must validate without error."""

    @pytest.mark.parametrize("agent_name", sorted(GOLDEN_FIXTURES))
    def test_golden_validates(self, agent_name: str):
        schema_cls = ALL_SCHEMAS[agent_name]
        obj = schema_cls.model_validate(GOLDEN_FIXTURES[agent_name])
        assert obj is not None


class TestMissingKey:
    """Removing a required field must raise ValidationError."""

    @pytest.mark.parametrize("agent_name,key_to_remove", [
        ("quantum_tech_expert", "tech_score"),
        ("commercialization", "commercialization_score"),
        ("valuation_health", "runway_quarters"),
        ("regulatory_policy", "policy_score"),
        ("flow_technicals", "flow_score"),
        ("news", "strategic_score"),
        ("sentiment", "macro_score"),
        ("technical", "trend"),
        ("fundamentals", "revenue_growth_yoy"),
    ])
    def test_missing_key_fails(self, agent_name: str, key_to_remove: str):
        fixture = dict(GOLDEN_FIXTURES[agent_name])
        del fixture[key_to_remove]
        with pytest.raises(ValidationError):
            ALL_SCHEMAS[agent_name].model_validate(fixture)


class TestOutOfRange:
    """Out-of-range integers/floats must raise ValidationError."""

    @pytest.mark.parametrize("agent_name,field,bad_value", [
        ("quantum_tech_expert", "tech_score", 150),
        ("quantum_tech_expert", "tech_score", -1),
        ("commercialization", "commercialization_score", 101),
        ("commercialization", "score_delta_this_cycle", 15),
        ("valuation_health", "financial_health_score", -5),
        ("valuation_health", "dilution_probability_12m", 1.5),
        ("news", "strategic_score", 200),
        ("sentiment", "macro_score", -10),
        ("flow_technicals", "flow_score", 999),
    ])
    def test_out_of_range_fails(self, agent_name: str, field: str, bad_value):
        fixture = dict(GOLDEN_FIXTURES[agent_name])
        fixture[field] = bad_value
        with pytest.raises(ValidationError):
            ALL_SCHEMAS[agent_name].model_validate(fixture)


class TestWrongEnum:
    """Wrong Literal enum values must raise ValidationError."""

    @pytest.mark.parametrize("agent_name,field,bad_value", [
        ("quantum_tech_expert", "position_vs_peers", "unknown"),
        ("quantum_tech_expert", "roadmap_credibility", "very_high"),
        ("valuation_health", "valuation_tier", "expensive"),
        ("flow_technicals", "positioning_bias", "sideways"),
        ("flow_technicals", "squeeze_risk", "extreme"),
        ("sentiment", "sentiment_bias", "mixed"),
        ("sentiment", "retail_heat", "extreme"),
        ("technical", "trend", "sideways"),
    ])
    def test_wrong_enum_fails(self, agent_name: str, field: str, bad_value: str):
        fixture = dict(GOLDEN_FIXTURES[agent_name])
        fixture[field] = bad_value
        with pytest.raises(ValidationError):
            ALL_SCHEMAS[agent_name].model_validate(fixture)
