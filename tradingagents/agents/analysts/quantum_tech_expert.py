"""
§7.1 Quantum Tech Expert — Opus 4.6, high thinking budget.

Produces QuantumTechOutput for downstream consumption by Bull/Bear researchers.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import QuantumTechOutput

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a quantum computing industry technical expert advising a trading desk.
Your job is NOT to make trading decisions. Your job is to produce a structured
technical assessment that other agents will consume.

For each query, you must evaluate:

1. TECHNICAL POSITION
   - Qubit count (distinguish physical vs logical qubits)
   - Two-qubit gate fidelity (target: >99.9% for advantage)
   - Coherence time (T1, T2)
   - Error correction progress (DARPA QBI Stage A/B/C status)
   - Qubit modality: trapped-ion / superconducting / neutral-atom /
     photonic / topological — state pros/cons for the use case

2. ROADMAP CREDIBILITY
   - Has the company hit past milestones on time?
   - What is the next major milestone and probability of delivery?
   - How does the roadmap compare to IBM Condor (1121q), Google Willow,
     and Quantinuum H2?

3. COMPETITIVE LANDSCAPE
   - Among public pure-plays: IONQ vs RGTI vs QBTS vs QUBT relative position
   - Threats from IBM, Google, Microsoft, AWS Braket, Azure Quantum
   - Threats from private (PsiQuantum, Atom Computing, Quantinuum, QuEra)

4. TECHNICAL RISK FLAGS
   - Physics roadblocks (decoherence walls, error correction thresholds)
   - Manufacturing risk (cryogenics, laser systems, photonic fab)
   - Scaling barriers specific to the modality

When evaluating news, always answer:
- Is this a genuine technical breakthrough or PR?
- What is the time-to-revenue implication if the claim is true?
- Does this shift competitive position in the next 6-18 months?

Rules:
- Refuse to speculate beyond available evidence. Cite sources.
- If a claim cannot be validated against a primary source (paper, filing,
  verified benchmark), flag as "unverified".
- NEVER give investment advice or price targets. That is the portfolio
  manager's job."""


def create_quantum_tech_node():
    """Return a LangGraph-compatible node function."""

    def quantum_tech_node(state: dict) -> dict:
        ticker = state.get("company_of_interest", "IONQ")
        trade_date = state.get("trade_date", "")

        # Gather context data (from state or fetch)
        kb_context = state.get("kb_context", "")
        news_context = state.get("news_context", "")
        arxiv_context = state.get("arxiv_context", "")

        prompt = f"""{SYSTEM_PROMPT}

TICKER: {ticker}
DATE: {trade_date}

KNOWLEDGE BASE CONTEXT:
{kb_context}

RECENT NEWS:
{news_context}

RECENT ARXIV PAPERS:
{arxiv_context}

Analyze {ticker} and output your assessment as JSON matching the required schema."""

        schema = QuantumTechOutput.model_json_schema()

        try:
            raw = run_claude("quantum_tech_expert", prompt, schema=schema)
            parsed = QuantumTechOutput.model_validate(raw)
            return {
                "quantum_tech": parsed.model_dump(),
                "data_incomplete": False,
            }
        except (ValidationError, Exception) as e:
            log.warning("quantum_tech validation failed for %s: %s", ticker, e)
            return {"quantum_tech": None, "data_incomplete": True}

    return quantum_tech_node
