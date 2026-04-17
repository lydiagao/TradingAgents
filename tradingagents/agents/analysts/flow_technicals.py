"""
§7.5 Flow & Technicals Analyst — Haiku 4.5, no thinking.

Uses moomoo-only for IV + volume (NOT yfinance). Guardrail test enforces this.
"""

from __future__ import annotations

import logging
from pydantic import ValidationError

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import FlowTechnicalsOutput

# NOTE: This file MUST NOT import yfinance or dataflows.historical.
# test_no_yfinance_on_hot_path.py (P2-T5) scans agents/ for yfinance imports.

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You analyze institutional positioning and market microstructure for quantum
stocks. You use structured data, not narrative.

For each stock, report:
1. INSTITUTIONAL FLOW - Top holders, QoQ position change, new initiators, exits
2. SHORT INTEREST - % of float short, days to cover, 30-day change
3. OPTIONS POSITIONING - Put/call ratio, IV rank, unusual activity, block trades
4. TECHNICAL SIGNALS - Price vs 50/200 SMA, RS vs QQQ, volume spikes
5. SQUEEZE / CROWDING INDICATORS - Short squeeze probability, concentration

All options and IV data must come from moomoo get_live_options_chain.
All price/volume data must come from moomoo historical K-lines.
Do NOT use yfinance for any live or current data."""


def create_flow_technicals_node():
    def flow_technicals_node(state: dict) -> dict:
        ticker = state.get("company_of_interest", "IONQ")
        trade_date = state.get("trade_date", "")
        options_context = state.get("options_context", "")
        kline_context = state.get("kline_context", "")
        holdings_context = state.get("holdings_context", "")

        prompt = f"""{SYSTEM_PROMPT}

TICKER: {ticker}
DATE: {trade_date}

OPTIONS CHAIN DATA (from moomoo):
{options_context}

HISTORICAL K-LINES (from moomoo):
{kline_context}

13F INSTITUTIONAL HOLDINGS:
{holdings_context}

Analyze {ticker}'s flow and technical positioning. Output JSON matching the required schema."""

        schema = FlowTechnicalsOutput.model_json_schema()
        try:
            raw = run_claude("flow_technicals", prompt, schema=schema)
            parsed = FlowTechnicalsOutput.model_validate(raw)
            return {"flow_technicals": parsed.model_dump(), "data_incomplete": False}
        except (ValidationError, Exception) as e:
            log.warning("flow_technicals validation failed for %s: %s", ticker, e)
            return {"flow_technicals": None, "data_incomplete": True}

    return flow_technicals_node
