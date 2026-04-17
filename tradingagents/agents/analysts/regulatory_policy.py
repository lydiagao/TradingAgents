"""
§7.4 Regulatory & Policy Analyst — Sonnet 4.6, medium effort.

Focus on EVENTS tied to specific companies, not general industry trends.
"""

from __future__ import annotations

import logging
from pydantic import ValidationError

from tradingagents.agents._runner import run_claude
from tradingagents.memory.schemas import RegulatoryPolicyOutput

log = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are a regulatory and policy analyst tracking government action affecting
quantum computing companies.

Monitor:
1. US GOVERNMENT CONTRACTS - DARPA (QBI, HARQ, ONISQ), DOE, NSF, DOD
2. INTERNATIONAL POLICY - EU Quantum Flagship, UK Strategy, China 15th FYP, Japan
3. EXPORT CONTROLS - BIS controls, EU dual-use regulation
4. POST-QUANTUM CRYPTOGRAPHY - NIST PQC progress, enterprise migration deadlines
5. STANDARDS BODIES - IEEE, ISO/IEC, IETF post-quantum TLS
6. SUBSIDIES AND TAX CREDITS - CHIPS Act quantum provisions, R&D credits

Focus on EVENTS that affect specific named companies, not general industry
trends. A DARPA contract to IonQ is actionable; "quantum is strategic" is not."""


def create_regulatory_policy_node():
    def regulatory_policy_node(state: dict) -> dict:
        ticker = state.get("company_of_interest", "IONQ")
        trade_date = state.get("trade_date", "")
        sam_context = state.get("sam_context", "")
        policy_context = state.get("policy_context", "")

        prompt = f"""{SYSTEM_PROMPT}

TICKER: {ticker}
DATE: {trade_date}

SAM.GOV CONTRACT DATA:
{sam_context}

POLICY CONTEXT:
{policy_context}

Analyze the regulatory and policy landscape for {ticker}. Output JSON matching the required schema."""

        schema = RegulatoryPolicyOutput.model_json_schema()
        try:
            raw = run_claude("regulatory_policy", prompt, schema=schema)
            parsed = RegulatoryPolicyOutput.model_validate(raw)
            return {"regulatory_policy": parsed.model_dump(), "data_incomplete": False}
        except (ValidationError, Exception) as e:
            log.warning("regulatory_policy validation failed for %s: %s", ticker, e)
            return {"regulatory_policy": None, "data_incomplete": True}

    return regulatory_policy_node
