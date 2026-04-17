"""
Unit tests for tradingagents.config.model_config (P1-T10).

Covers:
  * All 16 agent keys present and return valid config
  * Every model ID is in VALID_MODEL_IDS
  * build_cli_args produces correct argv for each effort level
  * _budget_to_effort mapping (boundary + interior values)
  * UnknownAgentError on missing key
  * VALID_MODEL_IDS prevents drift
"""

import json
import pytest

from tradingagents.config.model_config import (
    AGENT_MODEL_MAP,
    VALID_MODEL_IDS,
    VALID_EFFORT_LEVELS,
    UnknownAgentError,
    get_model_config,
    build_cli_args,
    _budget_to_effort,
)

# -------------------------------------------------------------------
# § Expected agent keys (SPEC §6 — 16 agents)
# -------------------------------------------------------------------
EXPECTED_AGENT_KEYS = sorted([
    "technical", "news", "sentiment", "flow_technicals",
    "fundamentals", "valuation_health", "commercialization",
    "quantum_tech_expert", "regulatory_policy",
    "bull_researcher", "bear_researcher",
    "trader", "risky_analyst", "neutral_analyst", "safe_analyst",
    "portfolio_manager",
])


class TestAgentModelMap:

    def test_has_exactly_16_keys(self):
        assert len(AGENT_MODEL_MAP) == 16

    def test_all_expected_keys_present(self):
        assert sorted(AGENT_MODEL_MAP.keys()) == EXPECTED_AGENT_KEYS

    @pytest.mark.parametrize("agent", EXPECTED_AGENT_KEYS)
    def test_each_agent_has_model_and_thinking_budget(self, agent):
        cfg = AGENT_MODEL_MAP[agent]
        assert "model" in cfg
        assert "thinking_budget" in cfg
        assert isinstance(cfg["model"], str)
        assert isinstance(cfg["thinking_budget"], int)

    @pytest.mark.parametrize("agent", EXPECTED_AGENT_KEYS)
    def test_model_id_in_valid_set(self, agent):
        model = AGENT_MODEL_MAP[agent]["model"]
        assert model in VALID_MODEL_IDS, (
            f"agent={agent!r} has model={model!r} not in VALID_MODEL_IDS"
        )

    def test_no_opus_4_7(self):
        """SPEC revision note #3: claude-opus-4-7 does NOT exist."""
        for agent, cfg in AGENT_MODEL_MAP.items():
            assert "4-7" not in cfg["model"], (
                f"agent={agent!r} uses {cfg['model']!r} which contains '4-7'"
            )


class TestGetModelConfig:

    def test_returns_copy(self):
        cfg = get_model_config("technical")
        cfg["model"] = "mutated"
        assert AGENT_MODEL_MAP["technical"]["model"] != "mutated"

    def test_raises_unknown_agent_error(self):
        with pytest.raises(UnknownAgentError):
            get_model_config("nonexistent_agent_xyz")


class TestBudgetToEffort:

    @pytest.mark.parametrize("budget,expected", [
        (0, None),
        (-1, None),
        (1, "medium"),
        (4000, "medium"),
        (4001, "high"),
        (8000, "high"),
        (8001, "xhigh"),
        (16000, "xhigh"),
        (16001, "max"),
        (100000, "max"),
    ])
    def test_mapping(self, budget, expected):
        assert _budget_to_effort(budget) == expected

    def test_all_returned_values_valid(self):
        for agent, cfg in AGENT_MODEL_MAP.items():
            effort = _budget_to_effort(cfg["thinking_budget"])
            if effort is not None:
                assert effort in VALID_EFFORT_LEVELS, (
                    f"agent={agent!r} effort={effort!r}"
                )


class TestBuildCliArgs:

    def test_basic_structure(self):
        args = build_cli_args("technical")
        assert args[0] == "claude"
        assert "-p" in args
        assert "--output-format" in args
        assert "json" in args

    def test_model_in_args(self):
        args = build_cli_args("quantum_tech_expert")
        idx = args.index("--model")
        assert args[idx + 1] == "claude-opus-4-6"

    def test_effort_present_for_nonzero_budget(self):
        args = build_cli_args("quantum_tech_expert")
        assert "--effort" in args
        idx = args.index("--effort")
        assert args[idx + 1] == "xhigh"

    def test_effort_absent_for_zero_budget(self):
        args = build_cli_args("technical")
        assert "--effort" not in args

    def test_tools_disabled_by_default(self):
        args = build_cli_args("technical")
        assert "--tools" in args
        idx = args.index("--tools")
        assert args[idx + 1] == ""

    def test_tools_enabled(self):
        args = build_cli_args("technical", allow_tools=True)
        assert "--tools" not in args

    def test_schema_included(self):
        schema = {"type": "object", "properties": {"x": {"type": "number"}}}
        args = build_cli_args("news", schema=schema)
        assert "--json-schema" in args
        idx = args.index("--json-schema")
        parsed = json.loads(args[idx + 1])
        assert parsed == schema

    def test_schema_not_included_when_none(self):
        args = build_cli_args("news")
        assert "--json-schema" not in args

    def test_permission_mode(self):
        args = build_cli_args("technical")
        idx = args.index("--permission-mode")
        assert args[idx + 1] == "bypassPermissions"

    def test_extra_args(self):
        args = build_cli_args("technical", extra_args=["--verbose"])
        assert "--verbose" in args

    @pytest.mark.parametrize("agent", EXPECTED_AGENT_KEYS)
    def test_all_agents_produce_valid_args(self, agent):
        """Every agent key produces a well-formed argv without error."""
        args = build_cli_args(agent)
        assert isinstance(args, list)
        assert len(args) >= 6
        assert args[0] == "claude"

    def test_invalid_agent_raises(self):
        with pytest.raises(UnknownAgentError):
            build_cli_args("nonexistent_agent_xyz")
