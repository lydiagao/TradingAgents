"""
Daily cycle entry point — run by launchd at 8:00 ET weekdays.

Usage:
    python -m tradingagents.daily_cycle [--tickers IONQ,RGTI,QBTS,QUBT] [--dry-run]

Flow:
  1. Check kill switch
  2. For each ticker: fetch data → run quantum pipeline → collect decision
  3. Send Gmail report with all decisions + latency summary
  4. Log to decision_log
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

# Load .env before anything else
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
import time
import uuid
from datetime import datetime, timezone
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(
            os.path.expanduser("~/.tradingagents/daily_cycle.log"),
            mode="a",
        ),
    ],
)
log = logging.getLogger("daily_cycle")


def run_daily_cycle(tickers: list[str], dry_run: bool = False) -> dict[str, Any]:
    """Run the full daily cycle for a list of tickers."""
    from tradingagents.risk.kill_switch import check_kill_switch
    from tradingagents.orchestration.cost_tracker import CostTracker
    from tradingagents.orchestration.latency_report import generate_latency_report
    from tradingagents.orchestration.alerts import send_gmail_report, alert_error
    from tradingagents.memory.decision_log import DecisionLog
    from tradingagents.graph.quantum_pipeline import run_quantum_pipeline
    from tradingagents.dataflows.moomoo_client import MoomooClient

    cycle_id = f"cycle_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    log.info("=== Daily cycle start: %s | tickers: %s | dry_run: %s ===", cycle_id, tickers, dry_run)

    # Step 1: Kill switch
    check_kill_switch()

    decision_log = DecisionLog()
    cost_tracker = CostTracker(decision_log)
    results: dict[str, Any] = {"cycle_id": cycle_id, "decisions": {}, "errors": {}}

    # Step 2: Gather moomoo data + run pipeline per ticker
    client = MoomooClient()
    trade_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    for ticker in tickers:
        log.info("--- Processing %s ---", ticker)
        try:
            cost_tracker.check_daily_calls()
            cost_tracker.check_per_cycle_calls(cycle_id)

            # Fetch real-time context
            quote = client.get_realtime_quote(ticker)
            session_state = client.get_session_state(ticker)

            if session_state == "closed":
                log.info("Market closed for %s, using last available data", ticker)

            klines = client.get_historical_klines(ticker, "1d", start="2026-04-07", end=trade_date)

            context = {
                "market_data_context": json.dumps(quote, indent=2),
                "kline_context": json.dumps(klines[-5:] if klines else [], indent=2, default=str),
            }

            if dry_run:
                log.info("[DRY RUN] Would run pipeline for %s", ticker)
                results["decisions"][ticker] = {"action": "hold", "confidence": 0, "dry_run": True}
                continue

            # Run the full pipeline
            decision = run_quantum_pipeline(ticker, trade_date, context=context)
            results["decisions"][ticker] = decision

            # Log decision
            decision_log.write_decision(
                ticker=ticker,
                action=decision.get("action", "hold"),
                rationale=decision.get("reasoning", ""),
                final_score=decision.get("confidence", 0),
                execution_status="paper",
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        except SystemExit:
            raise  # kill switch
        except Exception as e:
            log.error("Pipeline failed for %s: %s", ticker, e, exc_info=True)
            results["errors"][ticker] = str(e)
            alert_error(ticker, e)

    client.close()

    # Step 3: Generate latency report
    latency = generate_latency_report(decision_log, days=1)
    results["latency"] = latency

    # Step 4: Send Gmail report
    log.info("Sending Gmail report...")
    try:
        send_gmail_report(results, cycle_id, trade_date)
    except Exception as e:
        log.error("Gmail report failed: %s", e, exc_info=True)
        results["gmail_error"] = str(e)

    log.info("=== Daily cycle complete: %s ===", cycle_id)
    return results


def main():
    parser = argparse.ArgumentParser(description="Quantum Trading Agent daily cycle")
    parser.add_argument(
        "--tickers", default="IONQ,RGTI,QBTS,QUBT",
        help="Comma-separated ticker list (default: quantum pure-plays)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Skip real pipeline calls")
    args = parser.parse_args()

    # Ensure log directory exists
    os.makedirs(os.path.expanduser("~/.tradingagents"), exist_ok=True)

    tickers = [t.strip().upper() for t in args.tickers.split(",")]
    results = run_daily_cycle(tickers, dry_run=args.dry_run)
    print(json.dumps(results, indent=2, default=str))


if __name__ == "__main__":
    main()
