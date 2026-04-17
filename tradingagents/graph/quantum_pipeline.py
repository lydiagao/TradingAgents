"""
Quantum Trading Pipeline — orchestrates all 9 analysts + downstream agents.

This is the quantum-fork replacement for the upstream trading_graph.py.
Per ADR-2026-04-16, all LLM calls go through `run_claude()` (CLI subprocess),
not through LangChain's ChatAnthropic.

Pipeline stages:
  1. Data gathering (Python-side, no LLM)
  2. 9 analyst calls (parallel-ready, currently sequential)
  3. Bull/Bear research debate
  4. Trader proposal
  5. Risk debate (aggressive / neutral / conservative)
  6. Portfolio Manager decision
  7. (Phase 4+) Scoring engine + hard risk gate
  8. (Phase 5+) Paper/live execution
"""

from __future__ import annotations

import json
import logging
from typing import Any

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import ALL_SCHEMAS

log = logging.getLogger(__name__)

# Agent names matching AGENT_MODEL_MAP keys
ANALYST_AGENTS = [
    "quantum_tech_expert", "commercialization", "valuation_health",
    "regulatory_policy", "flow_technicals",
    "technical", "news", "sentiment", "fundamentals",
]


def _run_analyst(agent_name: str, state: dict) -> dict[str, Any]:
    """Run a single analyst agent via CLI, with schema validation."""
    ticker = state.get("company_of_interest", "IONQ")
    trade_date = state.get("trade_date", "")

    # Build a generic prompt with available context
    context_parts = [f"TICKER: {ticker}", f"DATE: {trade_date}"]
    for key in ["market_data_context", "sec_context", "kb_context",
                "news_context", "rss_context", "reddit_context",
                "arxiv_context", "options_context", "kline_context",
                "holdings_context", "sam_context", "policy_context"]:
        if state.get(key):
            context_parts.append(f"\n{key.upper()}:\n{state[key]}")

    prompt = f"You are the {agent_name} agent. Analyze {ticker} for {trade_date}.\n\n" + "\n".join(context_parts)
    prompt += f"\n\nOutput JSON matching the {agent_name} schema."

    schema_cls = ALL_SCHEMAS.get(agent_name)
    schema = schema_cls.model_json_schema() if schema_cls else None

    try:
        raw = run_claude(agent_name, prompt, schema=schema)
        if schema_cls:
            parsed = schema_cls.model_validate(raw)
            return {agent_name: parsed.model_dump(), "data_incomplete": False}
        return {agent_name: raw, "data_incomplete": False}
    except Exception as e:
        log.warning("Analyst %s failed for %s: %s", agent_name, ticker, e)
        return {agent_name: None, "data_incomplete": True}


def _run_researcher(role: str, state: dict, analyst_outputs: dict) -> str:
    """Run bull or bear researcher."""
    ticker = state.get("company_of_interest", "IONQ")
    agent_name = f"{role}_researcher"

    analyst_summary = json.dumps(analyst_outputs, indent=2, default=str)

    prompt = f"""You are the {role.upper()} researcher for {ticker}.

Based on the following 9 analyst outputs, construct the strongest possible
{role} case for {ticker}. Reference at least 3 of the 5 new quantum dimensions
(tech, commercialization, valuation, regulatory, flow) by name.

ANALYST OUTPUTS:
{analyst_summary}

Write a compelling {role} thesis in 3-5 paragraphs."""

    return run_claude(agent_name, prompt)


def _run_trader(state: dict, bull_thesis: str, bear_thesis: str) -> str:
    """Run the trader agent."""
    ticker = state.get("company_of_interest", "IONQ")

    prompt = f"""You are the trader for {ticker}.

DATA SOURCE DISCIPLINE (§7.7):
All market data in this pipeline comes from moomoo (real-time). Do not request
or reference yfinance data. If any data appears stale or lacks the _source tag,
flag it and recommend HOLD.

BULL THESIS:
{bull_thesis}

BEAR THESIS:
{bear_thesis}

Based on both theses, propose a trade action (buy/sell/hold) with position sizing
and risk parameters. Be specific about entry/exit levels."""

    return run_claude("trader", prompt)


def _run_portfolio_manager(state: dict, analyst_outputs: dict,
                           bull_thesis: str, bear_thesis: str,
                           trader_proposal: str) -> dict:
    """Run the portfolio manager for final decision."""
    ticker = state.get("company_of_interest", "IONQ")
    trade_date = state.get("trade_date", "")

    prompt = f"""You are the portfolio manager making the final trading decision for {ticker} on {trade_date}.

ANALYST OUTPUTS (9 agents):
{json.dumps(analyst_outputs, indent=2, default=str)}

BULL THESIS:
{bull_thesis}

BEAR THESIS:
{bear_thesis}

TRADER PROPOSAL:
{trader_proposal}

STAGE WEIGHTED SCORE: {{{{stage_weighted_score}}}}

Make your final decision. Output JSON with: ticker, trade_date, action (buy/sell/hold),
confidence (0-1), reasoning, risk_notes."""

    schema = {
        "type": "object",
        "properties": {
            "ticker": {"type": "string"},
            "trade_date": {"type": "string"},
            "action": {"type": "string", "enum": ["buy", "sell", "hold"]},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "reasoning": {"type": "string"},
            "risk_notes": {"type": "string"},
        },
        "required": ["ticker", "trade_date", "action", "confidence", "reasoning"],
    }

    return run_claude("portfolio_manager", prompt, schema=schema)


def run_quantum_pipeline(
    ticker: str,
    trade_date: str,
    context: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Run the full quantum trading pipeline for a single ticker.

    Args:
        ticker: stock ticker (e.g. 'IONQ')
        trade_date: ISO date string
        context: optional pre-fetched context data keyed by context type

    Returns:
        Decision dict from Portfolio Manager.
    """
    state: dict[str, Any] = {
        "company_of_interest": ticker,
        "trade_date": trade_date,
    }
    if context:
        state.update(context)

    log.info("=== Quantum Pipeline: %s @ %s ===", ticker, trade_date)

    # Stage 1: Run all 9 analysts
    analyst_outputs: dict[str, Any] = {}
    data_incomplete_agents: list[str] = []

    for agent_name in ANALYST_AGENTS:
        log.info("Running analyst: %s", agent_name)
        result = _run_analyst(agent_name, state)
        if result.get("data_incomplete"):
            data_incomplete_agents.append(agent_name)
        analyst_outputs[agent_name] = result.get(agent_name)

    if data_incomplete_agents:
        log.warning("Data incomplete from: %s", data_incomplete_agents)

    # Stage 2: Bull/Bear debate
    log.info("Running bull researcher")
    bull_thesis = _run_researcher("bull", state, analyst_outputs)
    log.info("Running bear researcher")
    bear_thesis = _run_researcher("bear", state, analyst_outputs)

    # Stage 3: Trader proposal
    log.info("Running trader")
    trader_proposal = _run_trader(state, bull_thesis, bear_thesis)

    # Stage 4: Portfolio Manager decision
    log.info("Running portfolio manager")
    decision = _run_portfolio_manager(
        state, analyst_outputs, bull_thesis, bear_thesis, trader_proposal
    )

    decision["_pipeline_metadata"] = {
        "data_incomplete_agents": data_incomplete_agents,
        "analyst_count": len(ANALYST_AGENTS),
    }

    log.info("=== Pipeline complete: %s → %s (confidence: %s) ===",
             ticker, decision.get("action"), decision.get("confidence"))

    return decision
