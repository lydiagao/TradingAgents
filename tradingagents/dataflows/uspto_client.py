"""
§4.7 USPTO patent tracking client. Tier: OPTIONAL.

Weekly poll. Tracks patent filings from quantum universe companies.
Uses USPTO PatentsView API (free, no key needed).
"""

from __future__ import annotations

import logging
from typing import Any

import requests

from .retry import fetch_with_policy
from ..config.universe import UNIVERSE

log = logging.getLogger(__name__)

# PatentsView API - free, no auth
PATENTSVIEW_BASE = "https://api.patentsview.org/patents/query"


def _fetch_patents(assignee_keywords: list[str] | None = None) -> list[dict[str, Any]]:
    """Fetch recent quantum patents from PatentsView."""
    if assignee_keywords is None:
        assignee_keywords = ["IonQ", "Rigetti", "D-Wave", "Quantum Computing Inc",
                             "IBM", "Google", "Microsoft", "Honeywell", "Quantinuum"]

    # Build query for multiple assignees
    assignee_filters = [
        {"assignee_organization": kw} for kw in assignee_keywords
    ]

    query = {
        "_or": assignee_filters,
    }

    params = {
        "q": str(query).replace("'", '"'),
        "f": '["patent_number","patent_title","patent_date","assignee_organization"]',
        "o": '{"page":1,"per_page":25}',
        "s": '[{"patent_date":"desc"}]',
    }

    resp = requests.get(PATENTSVIEW_BASE, params=params, timeout=20)
    resp.raise_for_status()
    data = resp.json()

    patents = []
    for p in data.get("patents", []) or []:
        assignees = [a.get("assignee_organization", "") for a in p.get("assignees", [])]
        patents.append({
            "patent_number": p.get("patent_number", ""),
            "title": p.get("patent_title", ""),
            "date": p.get("patent_date", ""),
            "assignees": assignees,
            "source": "uspto_patentsview",
        })
    return patents


def fetch_quantum_patents() -> list[dict[str, Any]]:
    """Fetch recent quantum patents. Tier=optional per §4.10."""
    result = fetch_with_policy(
        "uspto_patents", _fetch_patents,
        tier="optional", retries=0, backoff_base=1.0,
    )
    return result.data if result.ok else []
