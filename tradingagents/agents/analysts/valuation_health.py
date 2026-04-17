"""
§7.3 Valuation & Financial Health — Sonnet 4.6, high effort.

Hard rules: runway < 4Q → score ≤ 40; going-concern → score ≤ 20.
"""

from __future__ import annotations

import logging
from pydantic import ValidationError

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import ValuationHealthOutput

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a financial analyst specialized in pre-profit growth stocks in the
quantum computing sector. Quantum pure-plays routinely trade at P/S ratios
above 100, making traditional valuation methods insufficient.

Evaluate each company on:
1. CASH POSITION - Total cash + equivalents + short-term investments from latest 10-Q
2. BURN RATE TREND - Quarterly cash consumption, expanding vs contracting
3. VALUATION MULTIPLES - P/S vs 5-year median, vs sector, EV/Revenue
4. DILUTION RISK - Share count trend, warrants/options, ATM offerings
5. EPS REVISION TREND - Analyst estimates direction and magnitude
6. CAPITAL STRUCTURE - Debt/equity, convertibles, cash covenants
7. RED FLAGS - Going-concern language, material weakness, auditor changes

Hard rules:
- If runway < 4 quarters at current burn: flag HIGH risk, score max 40.
- If P/S > 5x sector median AND runway < 6 quarters: flag "bubble risk".
- Going-concern language = immediate flag, score max 20."""


def create_valuation_health_node():
    def valuation_health_node(state: dict) -> dict:
        ticker = state.get("company_of_interest", "IONQ")
        trade_date = state.get("trade_date", "")
        sec_context = state.get("sec_context", "")
        market_data = state.get("market_data_context", "")

        prompt = f"""{SYSTEM_PROMPT}

TICKER: {ticker}
DATE: {trade_date}

SEC EDGAR FINANCIALS:
{sec_context}

MARKET DATA:
{market_data}

Analyze {ticker}'s valuation and financial health. Output JSON matching the required schema."""

        schema = ValuationHealthOutput.model_json_schema()
        try:
            raw = run_claude("valuation_health", prompt, schema=schema)
            parsed = ValuationHealthOutput.model_validate(raw)
            return {"valuation_health": parsed.model_dump(), "data_incomplete": False}
        except (ValidationError, Exception) as e:
            log.warning("valuation_health validation failed for %s: %s", ticker, e)
            return {"valuation_health": None, "data_incomplete": True}

    return valuation_health_node
