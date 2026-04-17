"""
§7.6 Fundamentals Analyst — Haiku 4.5, no thinking.

Extracts RPO, cash runway, qubit count from SEC EDGAR.
"""

from __future__ import annotations

import logging
from pydantic import ValidationError

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import FundamentalsOutput

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a fundamentals analyst for the quantum computing stock universe.
Extract and analyze key financial metrics from SEC filings.

For quantum companies, pay special attention to:
1. RPO (Remaining Performance Obligations) — leading revenue indicator
2. CASH RUNWAY — quarters of cash at current burn rate
3. QUBIT COUNT — if disclosed, the company's latest qubit milestone
4. REVENUE GROWTH — YoY and QoQ trends
5. GROSS MARGIN — improving or deteriorating
6. OPERATING EXPENSE TREND — is the company becoming more or less efficient?

Use SEC EDGAR data (10-Q, 10-K) as the authoritative source."""


def create_fundamentals_node():
    def fundamentals_node(state: dict) -> dict:
        ticker = state.get("company_of_interest", "IONQ")
        trade_date = state.get("trade_date", "")
        sec_context = state.get("sec_context", "")

        prompt = f"""{SYSTEM_PROMPT}

TICKER: {ticker}
DATE: {trade_date}

SEC EDGAR FINANCIAL DATA:
{sec_context}

Analyze {ticker}'s fundamentals. Output JSON matching the required schema."""

        schema = FundamentalsOutput.model_json_schema()
        try:
            raw = run_claude("fundamentals", prompt, schema=schema)
            parsed = FundamentalsOutput.model_validate(raw)
            return {"fundamentals": parsed.model_dump(), "data_incomplete": False}
        except (ValidationError, Exception) as e:
            log.warning("fundamentals validation failed for %s: %s", ticker, e)
            return {"fundamentals": None, "data_incomplete": True}

    return fundamentals_node
