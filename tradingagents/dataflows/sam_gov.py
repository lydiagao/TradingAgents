"""
§4.6 SAM.gov government contracts client. Tier: IMPORTANT.

Requires SAM_GOV_API_KEY env var (free registration at sam.gov).
Filters: DARPA, DOE, NSF, DOD, NIST + quantum keywords.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from .retry import fetch_with_policy

log = logging.getLogger(__name__)

SAM_BASE = "https://api.sam.gov/opportunities/v2/search"
QUANTUM_KEYWORDS = "quantum computing,quantum networking,PQC,post-quantum"
AGENCY_FILTERS = ["DARPA", "DOE", "NSF", "DOD", "NIST"]


def _fetch_opportunities(days_back: int = 7) -> list[dict[str, Any]]:
    api_key = os.getenv("SAM_GOV_API_KEY", "")
    if not api_key:
        raise EnvironmentError("SAM_GOV_API_KEY not set. Register at https://sam.gov/")

    from datetime import datetime, timedelta
    end = datetime.utcnow().strftime("%m/%d/%Y")
    start = (datetime.utcnow() - timedelta(days=days_back)).strftime("%m/%d/%Y")

    resp = requests.get(
        SAM_BASE,
        params={
            "api_key": api_key,
            "keywords": QUANTUM_KEYWORDS,
            "postedFrom": start,
            "postedTo": end,
            "limit": 25,
        },
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json()

    opportunities = []
    for opp in data.get("opportunitiesData", []):
        opportunities.append({
            "title": opp.get("title", ""),
            "solicitation_number": opp.get("solicitationNumber", ""),
            "department": opp.get("department", ""),
            "subtier": opp.get("subtierAgency", ""),
            "posted_date": opp.get("postedDate", ""),
            "response_deadline": opp.get("responseDeadLine", ""),
            "type": opp.get("type", ""),
            "url": opp.get("uiLink", ""),
            "source": "sam_gov",
        })
    return opportunities


def fetch_quantum_contracts(days_back: int = 7) -> list[dict[str, Any]]:
    """Fetch recent quantum-related govt opportunities. Tier=important."""
    result = fetch_with_policy(
        "sam_gov_quantum", lambda: _fetch_opportunities(days_back),
        tier="important", retries=1, backoff_base=3.0,
    )
    return result.data if result.ok else []
