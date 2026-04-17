"""
P4-T3 tests: hard risk gate — every VETO/HALT path covered.

Per Session 0a: WEEKLY_LOSS_HALT and MAX_TRADES_PER_DAY_PER_TICKER
are WIRED (not dead code).
"""

import pytest
from tradingagents.risk.hard_gate import (
    HardRiskGate, GateResult, TradeProposal, PortfolioState,
)


@pytest.fixture
def gate():
    return HardRiskGate()


def _state(**overrides) -> PortfolioState:
    defaults = dict(
        total_value=100_000, positions={}, daily_pnl_pct=0.0,
        weekly_pnl_pct=0.0, cash_pct=0.50, trades_today={},
    )
    defaults.update(overrides)
    return PortfolioState(**defaults)


def _market(ticker: str = "IONQ", **extra) -> dict:
    base = {ticker: {"_source": "moomoo", "price": 45.0, **extra}}
    return base


class TestSourceDiscipline:

    def test_stale_data_veto(self, gate):
        p = TradeProposal("IONQ", "buy", 0.02)
        market = {"IONQ": {"_source": "yfinance", "price": 45.0}}
        r, reason = gate.check(p, _state(), market)
        assert r == GateResult.VETO
        assert reason == "stale_data_rejected_not_from_moomoo"

    def test_missing_source_veto(self, gate):
        p = TradeProposal("IONQ", "buy", 0.02)
        market = {"IONQ": {"price": 45.0}}  # no _source
        r, reason = gate.check(p, _state(), market)
        assert r == GateResult.VETO


class TestDailyLoss:

    def test_daily_loss_halt(self, gate):
        p = TradeProposal("IONQ", "buy", 0.01)
        r, reason = gate.check(p, _state(daily_pnl_pct=-0.06), _market())
        assert r == GateResult.HALT
        assert reason == "daily_loss_halt_triggered"


class TestWeeklyLoss:

    def test_weekly_loss_halt(self, gate):
        p = TradeProposal("IONQ", "buy", 0.01)
        r, reason = gate.check(p, _state(weekly_pnl_pct=-0.13), _market())
        assert r == GateResult.HALT
        assert reason == "weekly_loss_halt_triggered"


class TestPositionCap:

    def test_position_cap_exceeded(self, gate):
        p = TradeProposal("IONQ", "buy", 0.02)
        s = _state(positions={"IONQ": {"pct": 0.02}})
        r, reason = gate.check(p, s, _market())
        assert r == GateResult.VETO
        assert reason == "position_cap_exceeded"


class TestQuantumAggregateCap:

    def test_quantum_aggregate_exceeded(self, gate):
        p = TradeProposal("IONQ", "buy", 0.01)
        s = _state(positions={
            "RGTI": {"pct": 0.05}, "QBTS": {"pct": 0.05}, "QUBT": {"pct": 0.05},
        })
        r, reason = gate.check(p, s, _market())
        assert r == GateResult.VETO
        assert reason == "quantum_aggregate_cap_exceeded"


class TestValuationGuard:

    def test_ps_ratio_too_high(self, gate):
        p = TradeProposal("IONQ", "buy", 0.01)
        r, reason = gate.check(p, _state(), _market(ps_ratio=600))
        assert r == GateResult.VETO
        assert "ps_ratio_too_high" in reason


class TestVolatilityGuard:

    def test_iv_too_high(self, gate):
        p = TradeProposal("IONQ", "buy", 0.01)
        r, reason = gate.check(p, _state(), _market(implied_volatility=150))
        assert r == GateResult.VETO
        assert "implied_volatility_too_high" in reason


class TestCashReserve:

    def test_insufficient_cash(self, gate):
        p = TradeProposal("IONQ", "buy", 0.02)
        s = _state(cash_pct=0.21)  # 0.21 - 0.02 = 0.19 < MIN_CASH_PCT (0.20)
        r, reason = gate.check(p, s, _market())
        assert r == GateResult.VETO
        assert reason == "insufficient_cash_reserve"


class TestMaxTradesPerDay:

    def test_max_trades_exceeded(self, gate):
        p = TradeProposal("IONQ", "buy", 0.01)
        s = _state(trades_today={"IONQ": 1})
        r, reason = gate.check(p, s, _market())
        assert r == GateResult.VETO
        assert reason == "max_trades_per_day_triggered"


class TestHoldPassthrough:

    def test_hold_passes(self, gate):
        p = TradeProposal("IONQ", "hold", 0.0)
        r, reason = gate.check(p, _state(), _market())
        assert r == GateResult.PASS


class TestCleanPass:

    def test_normal_buy_passes(self, gate):
        p = TradeProposal("IONQ", "buy", 0.02)
        r, reason = gate.check(p, _state(), _market())
        assert r == GateResult.PASS
        assert reason == "ok"


class TestKillSwitch:

    def test_kill_switch_raises(self, tmp_path):
        from tradingagents.risk.kill_switch import check_kill_switch, KILL_FILE
        # Create the kill file
        KILL_FILE.touch()
        try:
            with pytest.raises(SystemExit, match="KILL SWITCH"):
                check_kill_switch()
        finally:
            KILL_FILE.unlink(missing_ok=True)

    def test_no_kill_file_passes(self):
        from tradingagents.risk.kill_switch import check_kill_switch, KILL_FILE
        KILL_FILE.unlink(missing_ok=True)
        check_kill_switch()  # should not raise
