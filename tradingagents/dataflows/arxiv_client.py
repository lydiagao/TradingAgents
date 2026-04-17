"""
§4.2 arXiv quant-ph client. Tier: OPTIONAL.

Pulls latest 30 papers from cat:quant-ph, filters by quantum keywords.
"""

from __future__ import annotations

import logging
import re
from typing import Any
from xml.etree import ElementTree

import requests

from .retry import fetch_with_policy

log = logging.getLogger(__name__)

ARXIV_URL = (
    "https://export.arxiv.org/api/query?"
    "search_query=cat:quant-ph&sortBy=submittedDate&sortOrder=descending&max_results=30"
)

KEYWORDS = {
    "logical qubit", "error correction", "fault tolerant", "quantum supremacy",
    "quantum advantage", "quantum volume", "surface code", "topological",
    "trapped ion", "superconducting", "photonic", "neutral atom",
    "ibm", "rigetti", "ionq", "quantinuum", "d-wave", "psiquantum", "google",
    "willow", "condor", "heron",
}

NS = {"atom": "http://www.w3.org/2005/Atom"}


def _fetch_arxiv() -> list[dict[str, Any]]:
    resp = requests.get(ARXIV_URL, timeout=30)
    resp.raise_for_status()
    root = ElementTree.fromstring(resp.content)
    papers = []
    for entry in root.findall("atom:entry", NS):
        title = (entry.findtext("atom:title", "", NS) or "").strip()
        summary = (entry.findtext("atom:summary", "", NS) or "").strip()[:500]
        link = ""
        for lnk in entry.findall("atom:link", NS):
            if lnk.get("type") == "text/html":
                link = lnk.get("href", "")
                break
        published = (entry.findtext("atom:published", "", NS) or "")

        text_lower = (title + " " + summary).lower()
        matched = [kw for kw in KEYWORDS if kw in text_lower]

        papers.append({
            "title": title,
            "link": link,
            "published_at": published,
            "summary": summary,
            "matched_keywords": matched,
            "source": "arxiv_quant_ph",
        })
    return papers


def fetch_arxiv_papers(keyword_filter: bool = True) -> list[dict[str, Any]]:
    """Fetch latest quant-ph papers. Tier=optional per §4.10."""
    result = fetch_with_policy("arxiv_quant_ph", _fetch_arxiv, tier="optional", retries=1)
    if not result.ok:
        return []
    papers = result.data or []
    if keyword_filter:
        papers = [p for p in papers if p.get("matched_keywords")]
    return papers
