"""
§7.6 News Analyst — Sonnet 4.6, medium effort.

Primary source: quantum RSS feeds. Output includes strategic_score (0-100, 50=neutral).
"""

from __future__ import annotations

import logging
from pydantic import ValidationError

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import NewsOutput

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a news analyst for the quantum computing stock universe.
Your primary sources are quantum-domain RSS feeds (Quantum Insider,
Quantum Computing Report, HPCwire Quantum, Quantum Zeitgeist) and
general financial news.

For each ticker, assess:
1. HEADLINE ANALYSIS - What are the most impactful recent headlines?
2. STRATEGIC SIGNIFICANCE - Does this news change the company's competitive position?
3. CATALYST POTENTIAL - Could this trigger a near-term price move?
4. NOISE vs SIGNAL - Is this genuine news or recycled PR?

Output must include strategic_score (0-100):
- 50 = neutral (no strategic impact)
- >50 = positive strategic signal
- <50 = negative strategic signal
The Scoring Engine (§9.3) reads this field directly."""


def create_news_node():
    def news_node(state: dict) -> dict:
        ticker = state.get("company_of_interest", "IONQ")
        trade_date = state.get("trade_date", "")
        rss_context = state.get("rss_context", "")
        news_context = state.get("news_context", "")

        prompt = f"""{SYSTEM_PROMPT}

TICKER: {ticker}
DATE: {trade_date}

QUANTUM RSS FEEDS:
{rss_context}

GENERAL NEWS:
{news_context}

Analyze recent news for {ticker}. Output JSON matching the required schema."""

        schema = NewsOutput.model_json_schema()
        try:
            raw = run_claude("news", prompt, schema=schema)
            parsed = NewsOutput.model_validate(raw)
            return {"news": parsed.model_dump(), "data_incomplete": False}
        except (ValidationError, Exception) as e:
            log.warning("news validation failed for %s: %s", ticker, e)
            return {"news": None, "data_incomplete": True}

    return news_node
