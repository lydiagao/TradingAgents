"""
§7.6 Sentiment Analyst — Haiku 4.5, no thinking.

Includes r/QuantumComputing as primary signal. Output includes macro_score.
"""

from __future__ import annotations

import logging
from pydantic import ValidationError

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import SentimentOutput

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a sentiment analyst for the quantum computing stock universe.
Track retail and institutional sentiment across social media and forums.

Primary sources:
- r/QuantumComputing (domain signal)
- r/wallstreetbets (retail momentum)
- r/stocks, r/investing (broader context)

Assess:
1. SENTIMENT DIRECTION - Is the crowd bullish, neutral, or bearish on this ticker?
2. RETAIL HEAT - How much attention is this stock getting from retail traders?
3. MACRO SENTIMENT - Broader market mood affecting quantum sector
4. CONTRARIAN SIGNALS - Is sentiment so extreme it suggests a reversal?

Output must include macro_score (0-100):
- 50 = neutral macro sentiment
- >50 = macro tailwind for quantum stocks
- <50 = macro headwind
The Scoring Engine (§9.3) reads this field directly."""


def create_sentiment_node():
    def sentiment_node(state: dict) -> dict:
        ticker = state.get("company_of_interest", "IONQ")
        trade_date = state.get("trade_date", "")
        reddit_context = state.get("reddit_context", "")

        prompt = f"""{SYSTEM_PROMPT}

TICKER: {ticker}
DATE: {trade_date}

REDDIT DATA:
{reddit_context}

Analyze sentiment for {ticker}. Output JSON matching the required schema."""

        schema = SentimentOutput.model_json_schema()
        try:
            raw = run_claude("sentiment", prompt, schema=schema)
            parsed = SentimentOutput.model_validate(raw)
            return {"sentiment": parsed.model_dump(), "data_incomplete": False}
        except (ValidationError, Exception) as e:
            log.warning("sentiment validation failed for %s: %s", ticker, e)
            return {"sentiment": None, "data_incomplete": True}

    return sentiment_node
