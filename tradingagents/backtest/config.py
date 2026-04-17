"""
Backtest configuration — all user-confirmed parameters in one place.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date


@dataclass
class BacktestConfig:
    # Confirmed 2026-04-17
    initial_capital: float = 100_000.0
    start_date: str = "2024-01-01"
    end_date: str = "2025-04-01"
    tickers: list[str] = field(default_factory=lambda: ["IONQ", "RGTI", "QBTS", "QUBT"])
    frequency: str = "weekly"  # "daily" or "weekly" (weekly = every Monday)

    # Pass/fail thresholds
    min_sharpe: float = 1.5
    max_mdd: float = 0.25  # 25%

    # Position sizing (matches hard_gate.py)
    max_position_pct: float = 0.03
    max_quantum_exposure: float = 0.15
    min_cash_pct: float = 0.20

    # Execution assumptions
    slippage_bps: float = 10.0  # 0.1%
    commission_pct: float = 0.0  # moomoo US stocks commission-free

    # Checkpoint
    checkpoint_dir: str = "data/backtest_checkpoints"

    # Data
    historical_data_dir: str = "data/historical"
