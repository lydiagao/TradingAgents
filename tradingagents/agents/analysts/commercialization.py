"""
§7.2 Commercialization Analyst — Sonnet 4.6, high effort.

Hard rule: TTM revenue < $1M → commercialization_score capped at 30.
"""

from __future__ import annotations

import logging
from pydantic import ValidationError

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import CommercializationOutput

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a commercialization analyst for quantum computing stocks. You track
whether companies are converting technology into revenue.

Ignore technical details (other agents cover those). Focus on six dimensions:

1. BACKLOG GROWTH - RPO from 10-Q, QoQ and YoY change
2. CUSTOMER QUALITY - Government / Academic / Fortune 500 / Cloud marketplace
3. REVENUE STRUCTURE - One-time vs recurring QCaaS vs services vs license
4. PRODUCTION USE CASES - PoC only vs production; cite specific customers
5. UNIT ECONOMICS - Per-shot pricing, subscription, gross margin, CAC vs LTV
6. CHANNEL AND ECOSYSTEM - Integrations, developer community, SI partnerships

CRITICAL DISTINCTION:
- REAL signal: SEC-disclosed RPO, confirmed revenue, signed contracts
- WEAK signal: MOU, LOI, "strategic partnership" press releases
- Discount press-release-only signals by 70%.

If disclosed revenue < $1M TTM, cap commercialization_score at 30 regardless
of other signals (pre-revenue stocks can't score high on commercialization)."""


def create_commercialization_node():
    def commercialization_node(state: dict) -> dict:
        ticker = state.get("company_of_interest", "IONQ")
        trade_date = state.get("trade_date", "")
        sec_context = state.get("sec_context", "")

        prompt = f"""{SYSTEM_PROMPT}

TICKER: {ticker}
DATE: {trade_date}

SEC EDGAR DATA:
{sec_context}

Analyze {ticker}'s commercialization progress and output JSON matching the required schema."""

        schema = CommercializationOutput.model_json_schema()
        try:
            raw = run_claude("commercialization", prompt, schema=schema)
            parsed = CommercializationOutput.model_validate(raw)
            return {"commercialization": parsed.model_dump(), "data_incomplete": False}
        except (ValidationError, Exception) as e:
            log.warning("commercialization validation failed for %s: %s", ticker, e)
            return {"commercialization": None, "data_incomplete": True}

    return commercialization_node
