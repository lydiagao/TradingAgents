"""
dataflows/historical.py — the SOLE place yfinance is imported (SPEC §4.8.2).

Any other file under agents/ risk/ scoring/ orchestration/ execution/ that
imports yfinance will FAIL the guardrail test (test_no_yfinance_on_hot_path.py).

Use this module ONLY for:
  - Historical OHLC for backtests (no live decision on this path)
  - yfinance is the fallback when moomoo historical K-lines are unavailable
"""

from __future__ import annotations

import yfinance as yf
import pandas as pd


def get_backtest_ohlc(ticker: str, period: str = "2y") -> pd.DataFrame:
    """Fetch historical OHLCV from yfinance.

    Args:
        ticker: bare ticker like 'NVDA' or 'IONQ'
        period: yfinance period string (e.g. '1y', '2y', '6mo')

    Returns:
        DataFrame with columns: Open, High, Low, Close, Volume
    """
    return yf.Ticker(ticker).history(period=period)
