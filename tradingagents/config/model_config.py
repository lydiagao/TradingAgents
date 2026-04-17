"""
Per-agent model configuration for the Quantum Trading Agent.

Runtime invocation path (ADR-2026-04-16, see SPEC §6):
    agent code
      -> build_cli_args(agent_name, ...)
      -> subprocess.run(["claude", "-p", ...], input=prompt, ...)

The `claude` CLI bills against the user's Claude Code subscription (not the
Anthropic API). There is no ANTHROPIC_API_KEY requirement.

CLI flag findings (pinned during P1-T5, verified in P1-T11):
  * No `--thinking-budget N` flag exists. The CLI uses `--effort <level>`
    with choices: low / medium / high / xhigh / max.
    We translate AGENT_MODEL_MAP["thinking_budget"] (token count,
    inherited from SPEC §6) into an --effort level via `_budget_to_effort`.
  * `--permission-mode bypassPermissions` keeps `-p` non-interactive
    (no tool-approval prompts during unattended runs).
  * `--tools ""` disables all built-in tools. Our agents receive all
    domain data through the prompt — they do NOT use CC's Read / Bash /
    Edit tools.
  * `--json-schema '<inline JSON>'` enables structured output validation.
"""

from __future__ import annotations

import json
from typing import Any

# ---------------------------------------------------------------------------
# AGENT_MODEL_MAP — SPEC §6
#
# Per-agent (model_id, thinking_budget_tokens). `thinking_budget` is a
# token-count shorthand inherited from the Anthropic SDK style; we translate
# it to the CLI's `--effort` level (see _budget_to_effort).
# ---------------------------------------------------------------------------
AGENT_MODEL_MAP: dict[str, dict[str, Any]] = {
    # Layer 3 — Market & flow analysts (Haiku for structured data, no thinking)
    "technical":           {"model": "claude-haiku-4-5-20251001", "thinking_budget": 0},
    "news":                {"model": "claude-sonnet-4-6",         "thinking_budget": 4000},
    "sentiment":           {"model": "claude-haiku-4-5-20251001", "thinking_budget": 0},
    "flow_technicals":     {"model": "claude-haiku-4-5-20251001", "thinking_budget": 0},

    # Layer 3 — Financial & business
    "fundamentals":        {"model": "claude-haiku-4-5-20251001", "thinking_budget": 0},
    "valuation_health":    {"model": "claude-sonnet-4-6",         "thinking_budget": 8000},
    "commercialization":   {"model": "claude-sonnet-4-6",         "thinking_budget": 8000},

    # Layer 3 — Domain specialized
    "quantum_tech_expert": {"model": "claude-opus-4-6",           "thinking_budget": 16000},
    "regulatory_policy":   {"model": "claude-sonnet-4-6",         "thinking_budget": 4000},

    # Layer 4 — Researchers
    "bull_researcher":     {"model": "claude-sonnet-4-6",         "thinking_budget": 8000},
    "bear_researcher":     {"model": "claude-sonnet-4-6",         "thinking_budget": 8000},

    # Layer 5 — Trader + Risk debate
    "trader":              {"model": "claude-sonnet-4-6",         "thinking_budget": 8000},
    "risky_analyst":       {"model": "claude-sonnet-4-6",         "thinking_budget": 8000},
    "neutral_analyst":     {"model": "claude-sonnet-4-6",         "thinking_budget": 8000},
    "safe_analyst":        {"model": "claude-sonnet-4-6",         "thinking_budget": 8000},

    # Layer 7 — Portfolio manager
    "portfolio_manager":   {"model": "claude-opus-4-6",           "thinking_budget": 16000},
}

# Model IDs allowed in AGENT_MODEL_MAP. Any other value is a typo / drift.
# SPEC revision note #3: "claude-opus-4-7" does NOT exist as a pinned model
# — the CLI's default is an alias that may resolve to 4.7, but we always pin
# explicit 4.6 IDs for reproducibility.
VALID_MODEL_IDS: frozenset[str] = frozenset({
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-6",
    "claude-opus-4-6",
})

# CLI --effort levels accepted by `claude -p` (see `claude -p --help`).
VALID_EFFORT_LEVELS: frozenset[str] = frozenset({"low", "medium", "high", "xhigh", "max"})


class UnknownAgentError(KeyError):
    """Raised when an agent name is not present in AGENT_MODEL_MAP."""


def get_model_config(agent_name: str) -> dict[str, Any]:
    """Return a copy of the model config dict for `agent_name`.

    Raises:
        UnknownAgentError: `agent_name` is not in AGENT_MODEL_MAP.
    """
    try:
        return dict(AGENT_MODEL_MAP[agent_name])
    except KeyError:
        raise UnknownAgentError(
            f"agent_name={agent_name!r} not in AGENT_MODEL_MAP; "
            f"valid keys: {sorted(AGENT_MODEL_MAP)}"
        ) from None


def _budget_to_effort(budget: int) -> str | None:
    """Map a thinking-budget token count to the CLI's --effort level.

    Mapping (ADR-2026-04-16; revisit after empirical calibration in P1-T11):
        0                    -> None (omit --effort; CLI default)
        1  .. 4000           -> "medium"
        4001 .. 8000         -> "high"
        8001 .. 16000        -> "xhigh"
        >16000               -> "max"
    """
    if budget <= 0:
        return None
    if budget <= 4000:
        return "medium"
    if budget <= 8000:
        return "high"
    if budget <= 16000:
        return "xhigh"
    return "max"


def build_cli_args(
    agent_name: str,
    *,
    schema: dict | None = None,
    allow_tools: bool = False,
    extra_args: list[str] | None = None,
) -> list[str]:
    """Build the `claude` CLI argv list for `agent_name`.

    The prompt itself is passed to `subprocess.run(..., input=<prompt>)`;
    this function only produces flags.

    Args:
        agent_name: Key in AGENT_MODEL_MAP.
        schema: Optional JSON Schema dict. When provided, emitted as
            `--json-schema <inline-json>` so the CLI validates output.
        allow_tools: If False (default), pass `--tools ""` to disable all
            built-in tools. Our agents read all domain data from the prompt;
            they should not read files / run bash / call MCP tools.
        extra_args: Any additional raw argv items to append (e.g. for tests).

    Returns:
        argv list ready for subprocess.run(argv, input=<prompt>, ...).

    Raises:
        UnknownAgentError: via `get_model_config`.
        ValueError: if the agent's model ID or derived effort level is not
            in the valid set (defensive check against drift).
    """
    cfg = get_model_config(agent_name)

    model = cfg["model"]
    if model not in VALID_MODEL_IDS:
        raise ValueError(
            f"agent {agent_name!r} has model={model!r} not in VALID_MODEL_IDS; "
            f"valid: {sorted(VALID_MODEL_IDS)}"
        )

    args: list[str] = [
        "claude", "-p",
        "--output-format", "json",
        "--model", model,
        "--permission-mode", "bypassPermissions",
    ]

    effort = _budget_to_effort(cfg["thinking_budget"])
    if effort is not None:
        if effort not in VALID_EFFORT_LEVELS:
            raise ValueError(
                f"_budget_to_effort returned {effort!r} not in VALID_EFFORT_LEVELS"
            )
        args += ["--effort", effort]

    if not allow_tools:
        # Disable all built-in tools. Empty string per `claude -p --help`.
        args += ["--tools", ""]

    if schema is not None:
        args += ["--json-schema", json.dumps(schema, separators=(",", ":"))]

    if extra_args:
        args += list(extra_args)

    return args
