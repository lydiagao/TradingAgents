"""
Phase 1 mini-baseline: run_claude → decision JSON for a given ticker.

Usage:
    python -m tradingagents.phase1_baseline NVDA 2026-04-15

This script demonstrates the ADR-2026-04-16 CLI pipeline end-to-end:
  1. Fetch basic market data for the ticker (via yfinance — quick & free)
  2. Build a simple prompt with the data
  3. Call run_claude("portfolio_manager", prompt, schema=DECISION_SCHEMA)
  4. Print the decision JSON to stdout

Note: this is a MINI baseline (P1-T9 scope narrowing). The full upstream
TradingAgents pipeline (main.py) requires llm.bind_tools() which our CLI
path does not support. The full pipeline replacement is Phase 3 (§7.6/§7.7).
"""

from __future__ import annotations

import json
import sys
from datetime import datetime

from tradingagents.agents._runner import run_claude

DECISION_SCHEMA = {
    "type": "object",
    "properties": {
        "ticker": {"type": "string"},
        "trade_date": {"type": "string"},
        "action": {
            "type": "string",
            "enum": ["buy", "sell", "hold"],
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
        },
        "reasoning": {"type": "string"},
        "risk_notes": {"type": "string"},
    },
    "required": ["ticker", "trade_date", "action", "confidence", "reasoning"],
}


def fetch_basic_data(ticker: str, trade_date: str) -> str:
    """Fetch a small data snippet for the ticker via yfinance."""
    try:
        import yfinance as yf

        stock = yf.Ticker(ticker)
        hist = stock.history(period="5d")
        if hist.empty:
            return f"No recent price data available for {ticker}."
        last = hist.iloc[-1]
        prev = hist.iloc[-2] if len(hist) >= 2 else last
        pct_change = ((last["Close"] - prev["Close"]) / prev["Close"]) * 100
        info = stock.info
        return (
            f"Ticker: {ticker}\n"
            f"Trade date: {trade_date}\n"
            f"Last close: ${last['Close']:.2f}\n"
            f"Previous close: ${prev['Close']:.2f}\n"
            f"1-day change: {pct_change:+.2f}%\n"
            f"Volume: {int(last['Volume']):,}\n"
            f"Market cap: {info.get('marketCap', 'N/A')}\n"
            f"Sector: {info.get('sector', 'N/A')}\n"
            f"52-week range: {info.get('fiftyTwoWeekLow', 'N/A')} – {info.get('fiftyTwoWeekHigh', 'N/A')}\n"
        )
    except Exception as e:
        return f"Data fetch failed for {ticker}: {e}. Proceed with limited info."


def build_prompt(ticker: str, trade_date: str, market_data: str) -> str:
    return f"""You are a portfolio manager analyzing {ticker} for a trading decision on {trade_date}.

Here is the latest market data:

{market_data}

Based on this data, provide a trading decision. Consider:
- Current price action and momentum
- Market conditions and sector context
- Risk factors

Output your decision as a JSON object matching the required schema."""


def main():
    if len(sys.argv) < 3:
        print("Usage: python -m tradingagents.phase1_baseline <TICKER> <TRADE_DATE>")
        print("Example: python -m tradingagents.phase1_baseline NVDA 2026-04-15")
        sys.exit(1)

    ticker = sys.argv[1].upper()
    trade_date = sys.argv[2]

    print(f"[Phase 1 baseline] ticker={ticker} date={trade_date}", file=sys.stderr)
    print("[1/3] Fetching market data...", file=sys.stderr)
    market_data = fetch_basic_data(ticker, trade_date)
    print(market_data, file=sys.stderr)

    print("[2/3] Calling run_claude('portfolio_manager', ...)...", file=sys.stderr)
    prompt = build_prompt(ticker, trade_date, market_data)
    decision = run_claude("portfolio_manager", prompt, schema=DECISION_SCHEMA)

    print("[3/3] Decision received.", file=sys.stderr)
    print(json.dumps(decision, indent=2))
    return decision


if __name__ == "__main__":
    main()
