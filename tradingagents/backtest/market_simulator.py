"""
Market simulator — replaces live MoomooClient during backtest.

Feeds historical OHLCV to agents as if it were real-time data.
Synthesizes T0/T1 timestamps from the bar's date.
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import yfinance as yf

from .config import BacktestConfig

log = logging.getLogger(__name__)


class MarketSimulator:
    """Provides historical market data as if it were live, for a given sim_date."""

    def __init__(self, config: BacktestConfig):
        self.config = config
        self._cache: dict[str, pd.DataFrame] = {}
        self._cache_dir = Path(config.historical_data_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _load_history(self, ticker: str) -> pd.DataFrame:
        """Load or download historical OHLCV for a ticker."""
        if ticker in self._cache:
            return self._cache[ticker]

        cache_file = self._cache_dir / f"{ticker}.csv"

        if cache_file.exists():
            df = pd.read_csv(cache_file, index_col=0, parse_dates=True)
            log.info("Loaded cached history for %s (%d bars)", ticker, len(df))
        else:
            log.info("Downloading history for %s via yfinance...", ticker)
            df = yf.Ticker(ticker).history(start=self.config.start_date, end=self.config.end_date)
            if df.empty:
                raise ValueError(f"No historical data for {ticker}")
            df.to_csv(cache_file)
            log.info("Cached %d bars for %s → %s", len(df), ticker, cache_file)

        self._cache[ticker] = df
        return df

    def get_trading_dates(self, ticker: str) -> list[datetime]:
        """Return all trading dates for a ticker in the backtest range."""
        df = self._load_history(ticker)
        dates = [d.to_pydatetime().replace(tzinfo=timezone.utc) for d in df.index]

        if self.config.frequency == "weekly":
            # Keep only Mondays (or first trading day of each week)
            weekly = []
            seen_weeks: set[tuple[int, int]] = set()
            for d in dates:
                week_key = (d.isocalendar()[0], d.isocalendar()[1])
                if week_key not in seen_weeks:
                    seen_weeks.add(week_key)
                    weekly.append(d)
            return weekly

        return dates

    def get_quote(self, ticker: str, sim_date: datetime) -> dict[str, Any]:
        """Simulate a real-time quote at sim_date.

        Returns dict matching MoomooClient.get_realtime_quote() shape.
        """
        df = self._load_history(ticker)
        date_str = sim_date.strftime("%Y-%m-%d")

        # Find the bar for this date (or closest prior)
        ts = pd.Timestamp(date_str)
        if df.index.tz is not None:
            ts = ts.tz_localize(df.index.tz)
        mask = df.index <= ts
        if mask.sum() == 0:
            raise ValueError(f"No data for {ticker} at or before {date_str}")

        bar = df[mask].iloc[-1]
        bar_date = df[mask].index[-1]

        ts_exchange = bar_date.strftime("%Y-%m-%d %H:%M:%S.000")
        ts_received = bar_date.strftime("%Y-%m-%dT%H:%M:%S.000Z")

        return {
            "ticker": ticker,
            "price": float(bar["Close"]),
            "open": float(bar["Open"]),
            "high": float(bar["High"]),
            "low": float(bar["Low"]),
            "volume": int(bar["Volume"]),
            "prev_close": float(bar["Close"]),  # simplified
            "_source": "moomoo",  # synthetic tag so pipeline accepts it
            "ts_exchange": ts_exchange,
            "ts_received": ts_received,
            "_ts_exchange_approximated": True,
            "_backtest": True,
        }

    def get_klines(self, ticker: str, sim_date: datetime, lookback: int = 30) -> list[dict]:
        """Return last N bars up to sim_date (for technical analysis context)."""
        df = self._load_history(ticker)
        ts = pd.Timestamp(sim_date.strftime("%Y-%m-%d"))
        if df.index.tz is not None:
            ts = ts.tz_localize(df.index.tz)
        mask = df.index <= ts
        recent = df[mask].tail(lookback)

        klines = []
        for idx, row in recent.iterrows():
            klines.append({
                "ticker": ticker,
                "time": idx.strftime("%Y-%m-%d"),
                "open": float(row["Open"]),
                "high": float(row["High"]),
                "low": float(row["Low"]),
                "close": float(row["Close"]),
                "volume": int(row["Volume"]),
                "_source": "moomoo",
            })
        return klines

    def execute_simulated_trade(
        self, ticker: str, action: str, sim_date: datetime, size_pct: float, portfolio_value: float,
    ) -> dict[str, Any]:
        """Simulate a trade execution with slippage."""
        quote = self.get_quote(ticker, sim_date)
        price = quote["price"]
        slippage_mult = self.config.slippage_bps / 10000

        if action == "buy":
            fill_price = price * (1 + slippage_mult)
            qty = int((portfolio_value * size_pct) / fill_price)
            cost = qty * fill_price
        elif action == "sell":
            fill_price = price * (1 - slippage_mult)
            qty = 0  # sell all — determined by caller
            cost = 0
        else:
            return {"status": "skipped_hold"}

        return {
            "ticker": ticker,
            "action": action,
            "fill_price": round(fill_price, 4),
            "qty": qty,
            "cost": round(cost, 2),
            "sim_date": sim_date.isoformat(),
            "status": "filled",
        }
