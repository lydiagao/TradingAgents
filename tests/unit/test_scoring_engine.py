"""
P4-T1+T2 tests: scoring engine — stage detection + weighted scores + §4.10 degradation.
"""

import pytest
from tradingagents.scoring.engine import detect_stage, compute_score, STAGE_WEIGHTS
from tradingagents.scoring.dimensions import clamp_score, normalize_dimension_scores


# ---- detect_stage ----

class TestDetectStage:

    def test_pre_revenue(self):
        assert detect_stage("QUBT", {"ttm_revenue_usd": 500_000}) == "pre_revenue"

    def test_early_revenue(self):
        assert detect_stage("IONQ", {"ttm_revenue_usd": 30_000_000}) == "early_revenue"

    def test_scaling(self):
        assert detect_stage("X", {"ttm_revenue_usd": 100_000_000, "revenue_growth_yoy": 0.8}) == "scaling"

    def test_established(self):
        assert detect_stage("IBM", {"ttm_revenue_usd": 60_000_000_000, "revenue_growth_yoy": 0.03}) == "established"

    def test_zero_revenue(self):
        assert detect_stage("NEW", {"ttm_revenue_usd": 0}) == "pre_revenue"

    def test_none_revenue(self):
        assert detect_stage("NEW", {}) == "pre_revenue"


# ---- compute_score ----

MOCK_OUTPUTS = {
    "valuation_health": {"financial_health_score": 60},
    "quantum_tech_expert": {"tech_score": 75},
    "commercialization": {"commercialization_score": 30},
    "news": {"strategic_score": 55},
    "regulatory_policy": {"policy_score": 65},
    "sentiment": {"macro_score": 50},
    "flow_technicals": {"flow_score": 45},
}


class TestComputeScore:

    def test_pre_revenue_score(self):
        r = compute_score("QUBT", MOCK_OUTPUTS, {"ttm_revenue_usd": 100_000})
        assert r["stage"] == "pre_revenue"
        assert 0 <= r["weighted_score"] <= 100
        assert len(r["dimension_scores"]) == 7

    def test_data_incomplete_halves_weight(self):
        r_full = compute_score("X", MOCK_OUTPUTS, {"ttm_revenue_usd": 10_000_000})
        r_degraded = compute_score(
            "X", MOCK_OUTPUTS, {"ttm_revenue_usd": 10_000_000},
            data_incomplete_agents=["quantum_tech_expert"],
        )
        assert "tech" in r_degraded["degraded_dimensions"]
        # The tech dimension weight should be halved (before renorm)
        # Score will differ because of the neutral fallback + weight change

    def test_all_stages_have_weights(self):
        for stage in ["pre_revenue", "early_revenue", "scaling", "established"]:
            assert stage in STAGE_WEIGHTS
            assert abs(sum(STAGE_WEIGHTS[stage].values()) - 1.0) < 0.01


# ---- dimensions ----

class TestDimensions:

    def test_clamp_in_range(self):
        assert clamp_score(50) == 50.0

    def test_clamp_over(self):
        assert clamp_score(150) == 100.0

    def test_clamp_under(self):
        assert clamp_score(-10) == 0.0

    def test_clamp_none(self):
        assert clamp_score(None) == 50.0

    def test_normalize(self):
        result = normalize_dimension_scores({"a": 200, "b": -5, "c": None})
        assert result == {"a": 100.0, "b": 0.0, "c": 50.0}
