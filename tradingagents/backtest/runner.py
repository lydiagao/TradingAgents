"""
Backtest runner — Phase 7 per SPEC §13.

Threads sim_date through every agent call + RAG query.
Checkpoint after each sim_date for crash recovery.

Usage:
    python -m tradingagents.backtest.runner --tickers IONQ --start 2024-01-01 --end 2024-02-01
    python -m tradingagents.backtest.runner --resume  # resume from last checkpoint
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent.parent / ".env")

from .config import BacktestConfig
from .market_simulator import MarketSimulator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
log = logging.getLogger("backtest")


def _json_default(obj):
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


# ---------------------------------------------------------------------------
# Portfolio tracker
# ---------------------------------------------------------------------------

class Portfolio:
    """Simple portfolio tracker for backtest."""

    def __init__(self, initial_capital: float):
        self.cash = initial_capital
        self.initial_capital = initial_capital
        self.positions: dict[str, dict] = {}  # ticker -> {qty, avg_price}
        self.trades: list[dict] = []
        self.daily_values: list[dict] = []  # {date, value}

    @property
    def value(self) -> float:
        """Total portfolio value (cash + positions at last known price)."""
        pos_value = sum(p.get("market_value", 0) for p in self.positions.values())
        return self.cash + pos_value

    def update_prices(self, prices: dict[str, float]):
        """Update position market values with current prices."""
        for ticker, pos in self.positions.items():
            if ticker in prices:
                pos["market_value"] = pos["qty"] * prices[ticker]
                pos["current_price"] = prices[ticker]

    def buy(self, ticker: str, price: float, size_pct: float) -> dict | None:
        """Buy a position. Returns trade record or None if can't."""
        max_cost = self.value * size_pct
        qty = int(max_cost / price)
        if qty <= 0:
            return None
        cost = qty * price
        if cost > self.cash:
            return None

        self.cash -= cost
        if ticker in self.positions:
            old = self.positions[ticker]
            total_qty = old["qty"] + qty
            old["avg_price"] = (old["avg_price"] * old["qty"] + price * qty) / total_qty
            old["qty"] = total_qty
        else:
            self.positions[ticker] = {"qty": qty, "avg_price": price, "market_value": qty * price, "current_price": price}

        trade = {"ticker": ticker, "action": "buy", "qty": qty, "price": price, "cost": cost}
        self.trades.append(trade)
        return trade

    def sell(self, ticker: str, price: float) -> dict | None:
        """Sell entire position. Returns trade record or None."""
        if ticker not in self.positions:
            return None
        pos = self.positions.pop(ticker)
        proceeds = pos["qty"] * price
        self.cash += proceeds
        pnl = (price - pos["avg_price"]) / pos["avg_price"]
        trade = {"ticker": ticker, "action": "sell", "qty": pos["qty"], "price": price,
                 "proceeds": proceeds, "pnl_pct": round(pnl, 4)}
        self.trades.append(trade)
        return trade

    def snapshot(self, date_str: str, prices: dict[str, float]) -> dict:
        self.update_prices(prices)
        snap = {"date": date_str, "value": round(self.value, 2), "cash": round(self.cash, 2),
                "positions": {t: {"qty": p["qty"], "avg_price": p["avg_price"]}
                              for t, p in self.positions.items()}}
        self.daily_values.append({"date": date_str, "value": self.value})
        return snap


# ---------------------------------------------------------------------------
# Checkpoint
# ---------------------------------------------------------------------------

class Checkpoint:
    """Save/load backtest state for crash recovery."""

    def __init__(self, checkpoint_dir: str):
        self._dir = Path(checkpoint_dir)
        self._dir.mkdir(parents=True, exist_ok=True)
        self._file = self._dir / "backtest_state.json"

    def save(self, state: dict):
        self._file.write_text(json.dumps(state, indent=2, default=str))

    def load(self) -> dict | None:
        if not self._file.exists():
            return None
        return json.loads(self._file.read_text())

    def clear(self):
        if self._file.exists():
            self._file.unlink()


# ---------------------------------------------------------------------------
# Main runner
# ---------------------------------------------------------------------------

def run_backtest(config: BacktestConfig, resume: bool = False) -> dict[str, Any]:
    """Run the full backtest."""
    from tradingagents.graph.quantum_pipeline import run_quantum_pipeline

    sim = MarketSimulator(config)
    portfolio = Portfolio(config.initial_capital)
    checkpoint = Checkpoint(config.checkpoint_dir)
    all_decisions: list[dict] = []
    completed_dates: set[str] = set()

    # Resume from checkpoint if requested
    if resume:
        saved = checkpoint.load()
        if saved:
            completed_dates = set(saved.get("completed_dates", []))
            portfolio.cash = saved.get("cash", config.initial_capital)
            portfolio.trades = saved.get("trades", [])
            portfolio.daily_values = saved.get("daily_values", [])
            for t, p in saved.get("positions", {}).items():
                portfolio.positions[t] = p
            all_decisions = saved.get("decisions", [])
            log.info("Resumed from checkpoint: %d dates completed", len(completed_dates))
        else:
            log.info("No checkpoint found, starting fresh")

    # Get trading dates (use first ticker to determine schedule)
    trading_dates = sim.get_trading_dates(config.tickers[0])
    total_dates = len(trading_dates)

    log.info("=== Backtest: %s → %s | %d dates | %s frequency | tickers: %s ===",
             config.start_date, config.end_date, total_dates, config.frequency,
             config.tickers)

    for i, sim_date in enumerate(trading_dates):
        date_str = sim_date.strftime("%Y-%m-%d")

        if date_str in completed_dates:
            continue

        log.info("[%d/%d] sim_date = %s | portfolio = $%.2f",
                 i + 1, total_dates, date_str, portfolio.value)

        # Get current prices for all tickers
        prices = {}
        for ticker in config.tickers:
            try:
                q = sim.get_quote(ticker, sim_date)
                prices[ticker] = q["price"]
            except ValueError:
                log.warning("No data for %s at %s, skipping", ticker, date_str)

        portfolio.update_prices(prices)

        # Run pipeline for each ticker
        for ticker in config.tickers:
            if ticker not in prices:
                continue

            quote = sim.get_quote(ticker, sim_date)
            klines = sim.get_klines(ticker, sim_date, lookback=30)

            context = {
                "market_data_context": json.dumps(quote, indent=2),
                "kline_context": json.dumps(klines[-5:], indent=2, default=str),
            }

            try:
                decision = run_quantum_pipeline(ticker, date_str, context=context)
            except Exception as e:
                log.error("Pipeline failed for %s @ %s: %s", ticker, date_str, e)
                decision = {"action": "hold", "confidence": 0, "error": str(e)}

            decision["sim_date"] = date_str
            decision["ticker"] = ticker
            all_decisions.append(decision)

            # Execute trade
            action = decision.get("action", "hold")
            price = prices[ticker]
            slippage = config.slippage_bps / 10000

            if action == "buy":
                current_pct = 0
                if ticker in portfolio.positions:
                    current_pct = (portfolio.positions[ticker]["qty"] * price) / portfolio.value
                if current_pct < config.max_position_pct:
                    buy_price = price * (1 + slippage)
                    remaining_pct = config.max_position_pct - current_pct
                    trade = portfolio.buy(ticker, buy_price, remaining_pct)
                    if trade:
                        log.info("  BUY %s: %d shares @ $%.2f", ticker, trade["qty"], trade["price"])

            elif action == "sell" and ticker in portfolio.positions:
                sell_price = price * (1 - slippage)
                trade = portfolio.sell(ticker, sell_price)
                if trade:
                    log.info("  SELL %s: %d shares @ $%.2f (pnl: %+.1f%%)",
                             ticker, trade["qty"], trade["price"], trade["pnl_pct"] * 100)

        # Snapshot + checkpoint
        snap = portfolio.snapshot(date_str, prices)
        completed_dates.add(date_str)

        checkpoint.save({
            "completed_dates": list(completed_dates),
            "cash": portfolio.cash,
            "positions": {t: p for t, p in portfolio.positions.items()},
            "trades": portfolio.trades,
            "daily_values": portfolio.daily_values,
            "decisions": all_decisions,
            "config": {
                "tickers": config.tickers,
                "start": config.start_date,
                "end": config.end_date,
                "frequency": config.frequency,
            },
        })

        log.info("  Portfolio: $%.2f | checkpoint saved", portfolio.value)

    # Final results
    checkpoint.clear()
    return {
        "config": {
            "initial_capital": config.initial_capital,
            "start": config.start_date,
            "end": config.end_date,
            "tickers": config.tickers,
            "frequency": config.frequency,
        },
        "final_value": round(portfolio.value, 2),
        "total_return_pct": round((portfolio.value / config.initial_capital - 1) * 100, 2),
        "total_trades": len(portfolio.trades),
        "trades": portfolio.trades,
        "daily_values": portfolio.daily_values,
        "decisions": all_decisions,
    }


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_metrics(results: dict) -> dict[str, Any]:
    """Compute Sharpe, MDD, win rate, etc."""
    daily_values = results.get("daily_values", [])
    trades = results.get("trades", [])
    initial = results["config"]["initial_capital"]

    if len(daily_values) < 2:
        return {"error": "Not enough data points"}

    values = [d["value"] for d in daily_values]

    # Returns
    returns = [(values[i] - values[i - 1]) / values[i - 1] for i in range(1, len(values))]
    avg_return = sum(returns) / len(returns) if returns else 0
    std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5 if returns else 1

    # Annualize (weekly frequency → 52 periods/year)
    periods_per_year = 52 if results["config"]["frequency"] == "weekly" else 252
    annualized_return = avg_return * periods_per_year
    annualized_std = std_return * (periods_per_year ** 0.5)
    sharpe = annualized_return / annualized_std if annualized_std > 0 else 0

    # Max drawdown
    peak = values[0]
    max_dd = 0
    for v in values:
        peak = max(peak, v)
        dd = (peak - v) / peak
        max_dd = max(max_dd, dd)

    # Win rate (from closed trades)
    sells = [t for t in trades if t["action"] == "sell"]
    wins = [t for t in sells if t.get("pnl_pct", 0) > 0]
    win_rate = len(wins) / len(sells) if sells else 0

    # Buy & hold comparison
    bh_return = (values[-1] / values[0] - 1) if values[0] > 0 else 0

    return {
        "total_return_pct": round((values[-1] / initial - 1) * 100, 2),
        "annualized_return_pct": round(annualized_return * 100, 2),
        "sharpe_ratio": round(sharpe, 2),
        "max_drawdown_pct": round(max_dd * 100, 2),
        "win_rate_pct": round(win_rate * 100, 1),
        "total_trades": len(trades),
        "closed_trades": len(sells),
        "avg_hold_periods": "N/A",  # would need entry/exit date tracking
        "pass_sharpe": sharpe > results["config"].get("min_sharpe", 1.5),
        "pass_mdd": max_dd < results["config"].get("max_mdd", 0.25),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Quantum Trading Agent backtest")
    parser.add_argument("--tickers", default="IONQ", help="Comma-separated tickers")
    parser.add_argument("--start", default="2024-01-01", help="Start date")
    parser.add_argument("--end", default="2024-02-01", help="End date")
    parser.add_argument("--frequency", default="weekly", choices=["daily", "weekly"])
    parser.add_argument("--capital", type=float, default=100_000)
    parser.add_argument("--resume", action="store_true", help="Resume from checkpoint")
    args = parser.parse_args()

    config = BacktestConfig(
        initial_capital=args.capital,
        start_date=args.start,
        end_date=args.end,
        tickers=[t.strip().upper() for t in args.tickers.split(",")],
        frequency=args.frequency,
    )

    results = run_backtest(config, resume=args.resume)
    metrics = compute_metrics(results)

    print("\n" + "=" * 60)
    print("BACKTEST RESULTS")
    print("=" * 60)
    print(json.dumps(metrics, indent=2))

    # Save full results
    output_dir = Path("results")
    output_dir.mkdir(exist_ok=True)
    output_file = output_dir / f"backtest_{config.start_date}_{config.end_date}.json"
    with open(output_file, "w") as f:
        json.dump({"metrics": metrics, "results": results}, f, indent=2, default=str)
    print(f"\nFull results saved to {output_file}")

    # Pass/fail
    if metrics.get("pass_sharpe") and metrics.get("pass_mdd"):
        print("\n✅ PASSED: Sharpe > 1.5 AND MDD < 25%")
    else:
        print(f"\n❌ NOT PASSED: Sharpe={metrics.get('sharpe_ratio')} (need >1.5), MDD={metrics.get('max_drawdown_pct')}% (need <25%)")


if __name__ == "__main__":
    main()
