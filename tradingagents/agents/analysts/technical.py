"""
§7.6 Technical Analyst — Haiku 4.5, no thinking. Moomoo K-lines only.

MUST NOT import yfinance or dataflows.historical.
"""

from __future__ import annotations

import logging
from pydantic import ValidationError

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import TechnicalOutput

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a technical analyst for the quantum computing stock universe.
Analyze price action, momentum indicators, and support/resistance levels.

Focus on: IONQ, RGTI, QBTS, QUBT, IBM, GOOGL, MSFT, NVDA, HON.

Use ONLY the provided moomoo K-line data for your analysis. Do not reference
or request data from yfinance or any delayed source.

Key indicators to assess:
- Trend: price vs 50-day and 200-day SMA
- Momentum: RSI, MACD, MACD histogram
- Volatility: Bollinger Bands width, ATR
- Volume: current vs 20-day average, volume spikes
- Support/resistance levels from recent price action"""


def create_technical_node():
    def technical_node(state: dict) -> dict:
        ticker = state.get("company_of_interest", "NVDA")
        trade_date = state.get("trade_date", "")
        kline_context = state.get("kline_context", "")

        prompt = f"""{SYSTEM_PROMPT}

TICKER: {ticker}
DATE: {trade_date}

MOOMOO K-LINE DATA:
{kline_context}

Analyze {ticker}'s technical setup. Output JSON matching the required schema."""

        schema = TechnicalOutput.model_json_schema()
        try:
            raw = run_claude("technical", prompt, schema=schema)
            parsed = TechnicalOutput.model_validate(raw)
            return {"technical": parsed.model_dump(), "data_incomplete": False}
        except (ValidationError, Exception) as e:
            log.warning("technical validation failed for %s: %s", ticker, e)
            return {"technical": None, "data_incomplete": True}

    return technical_node
