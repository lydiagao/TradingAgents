"""
§10 Hard Risk Gate — pure Python, no LLM. VETO/HALT before Portfolio Manager.

Session 0a fix: WEEKLY_LOSS_HALT and MAX_TRADES_PER_DAY_PER_TICKER are WIRED
(not dead code). Both require decision_log lookup.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class GateResult(Enum):
    PASS = "pass"
    VETO = "veto"
    HALT = "halt_all_trading"


@dataclass
class TradeProposal:
    ticker: str
    action: str  # 'buy' | 'sell' | 'hold'
    size_pct: float


@dataclass
class PortfolioState:
    total_value: float
    positions: dict  # ticker -> {"pct": float, "unrealized_pnl_pct": float}
    daily_pnl_pct: float
    weekly_pnl_pct: float  # wired per Session 0a
    cash_pct: float
    trades_today: dict[str, int]  # ticker -> count today (wired per Session 0a)


QUANTUM_PURE_PLAYS = {"IONQ", "RGTI", "QBTS", "QUBT"}


class HardRiskGate:

    MAX_POSITION_PCT = 0.03
    MAX_QUANTUM_EXPOSURE = 0.15
    DAILY_LOSS_HALT = -0.05
    WEEKLY_LOSS_HALT = -0.12
    MIN_CASH_PCT = 0.20
    MAX_PS_RATIO_FOR_NEW_BUY = 500
    MAX_IV_FOR_NEW_BUY = 120
    MAX_TRADES_PER_DAY_PER_TICKER = 1

    def check(
        self,
        proposal: TradeProposal,
        state: PortfolioState,
        market_data: dict[str, Any],
    ) -> tuple[GateResult, str]:
        """Run all hard-limit checks. Returns (result, reason)."""
        ticker_data = market_data.get(proposal.ticker, {})

        # §4.8.1 data-source discipline
        if ticker_data.get("_source") != "moomoo":
            return GateResult.VETO, "stale_data_rejected_not_from_moomoo"

        # Daily loss halt
        if state.daily_pnl_pct <= self.DAILY_LOSS_HALT:
            return GateResult.HALT, "daily_loss_halt_triggered"

        # Weekly loss halt (Session 0a: wired, not dead)
        if state.weekly_pnl_pct <= self.WEEKLY_LOSS_HALT:
            return GateResult.HALT, "weekly_loss_halt_triggered"

        if proposal.action == "hold":
            return GateResult.PASS, "ok"

        # Max trades per day per ticker (Session 0a: wired, not dead)
        today_count = state.trades_today.get(proposal.ticker, 0)
        if today_count >= self.MAX_TRADES_PER_DAY_PER_TICKER:
            return GateResult.VETO, "max_trades_per_day_triggered"

        if proposal.action == "buy":
            # Position cap
            current_pct = state.positions.get(proposal.ticker, {}).get("pct", 0)
            if current_pct + proposal.size_pct > self.MAX_POSITION_PCT:
                return GateResult.VETO, "position_cap_exceeded"

            # Quantum aggregate cap
            if proposal.ticker in QUANTUM_PURE_PLAYS:
                quantum_exposure = sum(
                    state.positions.get(t, {}).get("pct", 0)
                    for t in QUANTUM_PURE_PLAYS
                )
                if quantum_exposure + proposal.size_pct > self.MAX_QUANTUM_EXPOSURE:
                    return GateResult.VETO, "quantum_aggregate_cap_exceeded"

            # Valuation guard
            ps_ratio = ticker_data.get("ps_ratio", 0)
            if ps_ratio and ps_ratio > self.MAX_PS_RATIO_FOR_NEW_BUY:
                return GateResult.VETO, f"ps_ratio_too_high_{ps_ratio}"

            # Volatility guard
            iv = ticker_data.get("implied_volatility", 0)
            if iv and iv > self.MAX_IV_FOR_NEW_BUY:
                return GateResult.VETO, f"implied_volatility_too_high_{iv}"

            # Cash reserve
            if state.cash_pct - proposal.size_pct < self.MIN_CASH_PCT:
                return GateResult.VETO, "insufficient_cash_reserve"

        return GateResult.PASS, "ok"
