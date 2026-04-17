"""
LangGraph node helper: `run_claude(agent_name, prompt, schema=None)`.

Per ADR-2026-04-16 (SPEC §6), each agent in the Quantum Trading Agent
pipeline invokes the `claude` CLI as a subprocess. This module is the
single entry point for that invocation.

Design notes:
  * We do NOT emulate `langchain_anthropic.ChatAnthropic.bind_tools(...)`.
    Upstream TradingAgents agents use `llm.bind_tools(...)` for market-data
    fetches; our Quantum agents (Phase 3+) instead fetch data in Python
    BEFORE calling `run_claude`, then pass the data as part of the prompt.
  * This keeps the CLI invocation simple (`--tools ""`) and deterministic.
  * For Phase 1 baseline (P1-T11), this means upstream's tool-bound agents
    cannot be swapped in place. See TASKS.md for the P1-T11 pivoted plan.
"""

from __future__ import annotations

import json
import subprocess
from typing import Any

from tradingagents.config.model_config import build_cli_args

# Default subprocess timeout. Opus with xhigh effort can take a while;
# 300s is the conservative ceiling. Override per-call if needed.
DEFAULT_TIMEOUT_SEC = 300


class ClaudeCLIError(RuntimeError):
    """Raised when the `claude` CLI returns non-zero or unparseable output."""


def run_claude(
    agent_name: str,
    prompt: str,
    *,
    schema: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT_SEC,
    allow_tools: bool = False,
    return_raw: bool = False,
) -> dict[str, Any] | str:
    """
    Invoke the `claude` CLI for `agent_name` with `prompt`.

    Args:
        agent_name: Key into AGENT_MODEL_MAP (SPEC §6).
        prompt: The prompt text; sent via subprocess stdin.
        schema: Optional JSON Schema dict. When provided, the agent's
            output is validated by the CLI itself (--json-schema).
        timeout: Subprocess timeout in seconds.
        allow_tools: Passthrough to build_cli_args. Default False for
            reproducibility; set True only if an agent truly needs CC's
            built-in tools (rare in this project).
        return_raw: If True, return the raw CLI wrapper JSON (with usage
            info, session_id, modelUsage). Default False returns just the
            parsed `result` field (a dict if schema was provided, else a
            string).

    Returns:
        - schema is None, return_raw=False: agent's text response (str)
        - schema provided, return_raw=False: parsed JSON dict (matches schema)
        - return_raw=True: full CLI wrapper dict

    Raises:
        ClaudeCLIError: subprocess failed, timed out, or stdout unparseable.
    """
    args = build_cli_args(agent_name, schema=schema, allow_tools=allow_tools)

    try:
        proc = subprocess.run(
            args,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as e:
        raise ClaudeCLIError(
            f"`claude` CLI timed out after {timeout}s for agent={agent_name!r}"
        ) from e

    if proc.returncode != 0:
        raise ClaudeCLIError(
            f"`claude` CLI exited with code {proc.returncode} for agent={agent_name!r}\n"
            f"stderr: {proc.stderr.strip()[:500]}"
        )

    try:
        wrapper = json.loads(proc.stdout)
    except json.JSONDecodeError as e:
        raise ClaudeCLIError(
            f"`claude` CLI stdout is not valid JSON for agent={agent_name!r}\n"
            f"stdout head: {proc.stdout[:500]!r}"
        ) from e

    if return_raw:
        return wrapper

    if wrapper.get("is_error"):
        raise ClaudeCLIError(
            f"`claude` CLI reported is_error=True for agent={agent_name!r}: "
            f"{wrapper.get('api_error_status')}"
        )

    if schema is None:
        # Plain text response — body is in `result`.
        result = wrapper.get("result")
        return result if isinstance(result, str) else str(result)

    # Schema mode — the CLI puts the validated object in `structured_output`
    # (pinned during P1-T9 2026-04-16 probe). `result` is empty.
    structured = wrapper.get("structured_output")
    if isinstance(structured, dict):
        return structured
    if isinstance(structured, str):
        try:
            return json.loads(structured)
        except json.JSONDecodeError as e:
            raise ClaudeCLIError(
                f"schema mode: `structured_output` is a string but not valid JSON: "
                f"{structured[:300]!r}"
            ) from e
    raise ClaudeCLIError(
        f"schema mode: `structured_output` field missing or wrong type "
        f"({type(structured).__name__}); wrapper keys: {sorted(wrapper)}"
    )
