"""
§4.3 SEC EDGAR client. Tier: IMPORTANT.

CIK lookup, 10-Q/10-K/13F parsers. Rate limit: 10 req/s.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path
from typing import Any

import requests

from .retry import fetch_with_policy

log = logging.getLogger(__name__)

SEC_BASE = "https://data.sec.gov"
USER_AGENT = os.getenv("SEC_USER_AGENT", "QuantumTradingAgent research@example.com")
HEADERS = {"User-Agent": USER_AGENT}
_last_request_time = 0.0


def _rate_limit():
    """Enforce 10 req/s SEC rate limit."""
    global _last_request_time
    elapsed = time.monotonic() - _last_request_time
    if elapsed < 0.1:
        time.sleep(0.1 - elapsed)
    _last_request_time = time.monotonic()


def _get(url: str) -> dict | list:
    _rate_limit()
    resp = requests.get(url, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    return resp.json()


# ---- CIK lookup ----------------------------------------------------------

_CIKS_PATH = Path(__file__).parent.parent / "config" / "ciks.json"


def load_cik_map() -> dict[str, str]:
    return json.loads(_CIKS_PATH.read_text())


def get_cik(ticker: str) -> str:
    cik_map = load_cik_map()
    ticker_upper = ticker.upper()
    if ticker_upper not in cik_map:
        raise KeyError(f"Ticker {ticker_upper!r} not in ciks.json")
    return cik_map[ticker_upper]


# ---- Submissions (filing index) -----------------------------------------

def get_submissions(ticker: str) -> dict[str, Any]:
    """Get all filings metadata for a ticker."""
    cik = get_cik(ticker)
    url = f"{SEC_BASE}/submissions/CIK{cik}.json"
    return fetch_with_policy(f"sec_submissions_{ticker}", lambda: _get(url),
                             tier="important", retries=2, backoff_base=1.0).data or {}


# ---- Company facts (XBRL) -----------------------------------------------

def get_company_facts(ticker: str) -> dict[str, Any]:
    """Get XBRL company facts (revenue, cash, etc.)."""
    cik = get_cik(ticker)
    url = f"{SEC_BASE}/api/xbrl/companyfacts/CIK{cik}.json"
    result = fetch_with_policy(f"sec_xbrl_{ticker}", lambda: _get(url),
                               tier="important", retries=2, backoff_base=1.0)
    return result.data or {}


def extract_financials(ticker: str) -> dict[str, Any]:
    """Extract key financial metrics from XBRL company facts.

    Returns dict with revenue, cash, total_assets, etc. (latest values).
    """
    facts = get_company_facts(ticker)
    us_gaap = facts.get("facts", {}).get("us-gaap", {})

    def _latest_value(concept: str) -> float | None:
        data = us_gaap.get(concept, {}).get("units", {})
        for unit_type in ("USD", "shares"):
            entries = data.get(unit_type, [])
            if entries:
                # Sort by end date, take latest
                sorted_entries = sorted(entries, key=lambda x: x.get("end", ""), reverse=True)
                return sorted_entries[0].get("val")
        return None

    return {
        "ticker": ticker,
        "revenue": _latest_value("Revenues") or _latest_value("RevenueFromContractWithCustomerExcludingAssessedTax"),
        "cash": _latest_value("CashAndCashEquivalentsAtCarryingValue"),
        "total_assets": _latest_value("Assets"),
        "total_liabilities": _latest_value("Liabilities"),
        "shares_outstanding": _latest_value("CommonStockSharesOutstanding"),
        "net_income": _latest_value("NetIncomeLoss"),
        "source": "sec_edgar_xbrl",
    }


# ---- 13F institutional holdings -----------------------------------------

def get_latest_13f_filings(ticker: str) -> list[dict[str, Any]]:
    """Get recent 13F filing references for a ticker's CIK."""
    submissions = get_submissions(ticker)
    recent = submissions.get("filings", {}).get("recent", {})
    forms = recent.get("form", [])
    dates = recent.get("filingDate", [])
    accessions = recent.get("accessionNumber", [])

    filings_13f = []
    for form, date, acc in zip(forms, dates, accessions):
        if "13F" in form:
            filings_13f.append({
                "form": form,
                "filing_date": date,
                "accession": acc,
                "source": "sec_edgar_13f",
            })
    return filings_13f[:5]
