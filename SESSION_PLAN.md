# Session Plan — Quantum Trading Agent

> Execution plan for implementing SPEC.md across discrete Claude Code sessions.
> Each session fits within 4-8h of CC time and touches ≤5-8 files.

---

## Global

- **Total sessions**: 20
- **Critical-path length**: 14 sessions (S01 → S02 → S06 → S07/08/09 → S11 → S12 → S13 → S14 → S15 → S16 → S17 → S18 → S19)
- **Hardware prereq already satisfied**: moomoo OpenD running locally + Level 2 subscription (confirmed)
- **Cross-cutting discipline (every session from S02 onward must honor)**:
  - **§4.8 data discipline**: no yfinance under `agents/`, `risk/`, `scoring/`, `orchestration/`, `execution/`. Guardrail test `test_no_yfinance_on_hot_path.py` installed in S02 and runs on every commit.
  - **§10A latency**: T0/T1 emitted by `MoomooClient` from S02; T2-T5 thread through LangGraph state from S14 onward. No node may overwrite a timestamp.
  - **§4.10 graceful degradation**: every data-source client wraps its fetcher in `fetch_with_policy(...)`.
  - **§8.5 schema contracts**: every agent validates output via the Pydantic models in `memory/schemas.py`.
- **Commit discipline**: every session ends with a commit. Never leave a session mid-commit. Never skip the guardrail test.

## Session dependency DAG

```
S01 ──► S02 ──► S03 ──► S04 ┐
                     └► S05 ┤
                     └► S06 ┘
                          │
                          ├──► S07 ┐
                          ├──► S08 ┤
                          ├──► S09 ┤ (parallel agent work)
                          ├──► S10 ┤
                          └──► S11 ┘
                                │
                                ▼
                              S12 ──► S13 ──► S14 ──► S15 ──► S16 ──► S17 ──► S18 ──► S19 ──► S20
```

## Parallel vs. sequential

| Sessions | Parallelism |
|----------|-------------|
| S04, S05 | Parallel (different data-source files, no shared state) |
| S07, S08, S09, S10 | Parallel (different agent files; all depend on S06 memory + S03 schemas) |
| S11 | Sequential with S07-S10 (traditional agent edits + graph wiring; waits for new agents to finish) |
| Everything else | Sequential |

## Risk classification

| Level | Sessions | Reason |
|-------|----------|--------|
| HIGH | S02 (keystone), S07-09 (novel agent prompt design), S14 (T0-T5 state threading), S16 (backtest correctness), S18 (30-day ops) | Likely to need a revisit; high cost of getting wrong |
| MEDIUM | S03 (schema design), S04-05 (API failure surface), S10 (agent folder rename + graph wiring), S12-13 (scoring + risk gate integration), S15 (scheduler + alerts), S17 (backtest execution + tuning), S19 (go-live switch) | Standard complexity |
| LOW | S01 (scaffold), S06 (memory layer follows clear spec) | Well-defined |

## Minimum viable subset (if only 2 weeks of dev time)

S01 → S02 → S06 → S07 → S12 → S13 → S14. That gets you: data in, Quantum Tech Expert speaking, scoring + risk gate working, and paper-executing one ticker. Not a complete system but a demonstrable end-to-end slice. Everything else (additional agents, orchestration, backtest) can follow.

## Model selection rubric

| Task type | Model | Thinking budget |
|-----------|-------|-----------------|
| Scaffolding, wiring, config | Sonnet 4.6 | 4000-8000 |
| Data-source client integration | Sonnet 4.6 | 4000 |
| Novel agent prompt design (S07-S09) | **Opus 4.6** | 16000 (high) |
| Traditional agent modifications | Sonnet 4.6 | 4000 |
| Scoring / risk gate | Sonnet 4.6 | 8000 |
| LangGraph state threading (S14) | **Opus 4.6** | 16000 (hardest plumbing task in the project) |
| Backtest correctness design | Opus 4.6 | 16000 |
| Ops / tuning | Sonnet 4.6 | 4000 |

---

## Session briefs

Each brief is designed to be pasted into a fresh `/clear`'d Claude Code session.

---

### S01 — Scaffold & model config

| Field | Value |
|-------|-------|
| **Phase** | 1 |
| **Prereq** | None |
| **Model** | Sonnet 4.6 medium thinking |
| **Context** | Small (~40K) |
| **Risk** | LOW |
| **Parallelizable** | No |
| **Files** | `tradingagents/config/model_config.py` (new) · `tradingagents/config/universe.py` (new) · `tradingagents/config/ciks.json` (new) · `tradingagents/graph/setup.py` (modify inherited) · `tests/unit/test_model_config.py` (new) · `.env` (from `.env.example`) · `requirements.txt` (extend) |
| **SPEC refs** | §2, §3, §6, §12, §13 Phase 1 |
| **PROGRESS tasks** | P1-T1 through P1-T11 |
| **Exit criteria** | • `pytest tests/unit/test_model_config.py` green <br> • `python main.py NVDA 2026-04-15` emits decision JSON, cost ≈ $0.50 <br> • Commit `feat(P1): scaffold + per-agent model config` |

**Briefing prompt**:
```
Read SPEC.md §2, §3, §6, §12, §13 Phase 1 before editing anything.
Read PROGRESS.md, specifically P1-T1 through P1-T11.

Session goal: Execute Phase 1. Fork TradingAgents, wire per-agent model
config, confirm baseline pipeline runs on NVDA.

Constraints:
- Model IDs must use claude-opus-4-6 / claude-sonnet-4-6 / claude-haiku-4-5-20251001.
  No "claude-opus-4-7" — it does not exist (see SPEC revision note #3).
- SDK calling uses `thinking={"type":"enabled","budget_tokens":N}`. There is
  no `effort` parameter. Do not invent kwargs.
- Commit after each completed PROGRESS task; use conventional commits.

Ask before: adding paid APIs, touching Phase 2+ files, changing SPEC.

Exit when P1-T11 is green: baseline pipeline on NVDA produces decision JSON.
```

---

### S02 — MoomooClient + §4.8 guardrail (KEYSTONE)

| Field | Value |
|-------|-------|
| **Phase** | 2a |
| **Prereq** | S01 |
| **Model** | Sonnet 4.6 high thinking (8000) |
| **Context** | Medium (~80K — SPEC §4.8 is dense) |
| **Risk** | HIGH |
| **Parallelizable** | No (every downstream session depends on this) |
| **Files** | `tradingagents/dataflows/moomoo_client.py` (new) · `tradingagents/dataflows/__init__.py` (new, lazy) · `tradingagents/dataflows/historical.py` (new) · `tests/unit/test_no_yfinance_on_hot_path.py` (new, **CRITICAL**) · `tests/unit/test_moomoo_source_tag.py` (new) |
| **SPEC refs** | §4.8.1-4.8.3, §10A.2, §14 |
| **PROGRESS tasks** | P2-T1 through P2-T5 |
| **Exit criteria** | • moomoo realtime quote on IONQ returns dict with `_source: "moomoo"`, `ts_exchange`, `ts_received` <br> • `import tradingagents.dataflows` does NOT open a moomoo connection <br> • `test_no_yfinance_on_hot_path.py` passes (zero violations) <br> • `test_moomoo_source_tag.py` passes (every method tagged) <br> • Commit `feat(P2): MoomooClient + §4.8 import isolation + guardrail` |

**Briefing prompt**:
```
THIS IS THE STRUCTURAL KEYSTONE SESSION. Everything downstream — risk gate,
execution, data discipline — depends on MoomooClient existing and the
guardrail test being green.

Read SPEC.md §4.8 (all subsections, carefully) + §10A.2 + §14 before editing.
Read PROGRESS.md tasks P2-T1 through P2-T5.

Session goal: Implement MoomooClient with full §4.8.3 interface (including
wait_for_fill, get_historical_klines, T0/T1 timestamp tagging). Wire
dataflows/__init__.py with the lazy get_client() pattern per §4.8.2.
Implement the yfinance guardrail test with FORBIDDEN_DIRS including
"execution". Implement _source tag test.

Non-negotiable constraints:
- Every return dict from MoomooClient MUST carry _source: "moomoo".
- get_realtime_quote MUST return both ts_exchange (T0) and ts_received (T1).
  If moomoo gives only one, synthesize the other and add _ts_exchange_approximated: True.
- dataflows/__init__.py MUST NOT instantiate MoomooClient at import time.
  Use lazy get_client().
- dataflows/historical.py is the SOLE yfinance home.
- The guardrail test FORBIDDEN_DIRS is ["agents","risk","scoring","orchestration","execution"].

Ask before: changing the §4.8.3 interface; adding paid endpoints; modifying
graph/setup.py (wait for S11).

Exit when all 5 tasks green and commit made.
```

---

### S03 — Retry helper + Pydantic schemas scaffold

| Field | Value |
|-------|-------|
| **Phase** | 2b |
| **Prereq** | S02 |
| **Model** | Sonnet 4.6 high thinking (8000) |
| **Context** | Medium (~60K) |
| **Risk** | MEDIUM (small code, but bad schemas = downstream pain) |
| **Parallelizable** | No (S04+ use these helpers; but itself has no parallel peer) |
| **Files** | `tradingagents/dataflows/retry.py` (new) · `tradingagents/memory/schemas.py` (new) · `tests/unit/test_graceful_degradation.py` (new) · `tests/unit/test_schemas.py` (new) |
| **SPEC refs** | §4.10, §8.5, §14 |
| **PROGRESS tasks** | P2-T6, P2-T7 |
| **Exit criteria** | • 3-tier degradation helper working; mocked failures behave per policy <br> • All 9 agent Pydantic models importable; golden + mutated fixtures tested <br> • Commit `feat(P2): retry helper + Pydantic schemas` |

**Briefing prompt**:
```
Read SPEC.md §4.10 (graceful degradation) + §8.5 (schema contracts) + §7
output JSON blocks + §7.6 (News/Sentiment strategic_score/macro_score).
Read PROGRESS tasks P2-T6, P2-T7.

Session goal: Implement the cross-cutting infrastructure that every
subsequent session will use — the `fetch_with_policy` retry/degradation
helper and the Pydantic schema hub.

Key design points:
- FetchResult dataclass per §4.10; tier-aware behavior
- Schema models cover ALL 9 agents including traditional 4 (News/Sentiment
  schemas include strategic_score/macro_score — this is new in the Session
  0a hardening, see revision note #3)
- Each agent's enforcement pattern: validate, catch ValidationError, emit
  data_incomplete: True

Tests:
- test_graceful_degradation.py: mock each tier failing; assert correct behavior
- test_schemas.py: one golden JSON per agent + 3 mutation classes (missing key,
  out-of-range int, wrong enum literal) → assert ValidationError

Exit when tests green and commit made.
```

---

### S04 — Chatter data sources (RSS + arXiv + NewsAPI + Reddit OAuth)

| Field | Value |
|-------|-------|
| **Phase** | 2c |
| **Prereq** | S03 |
| **Model** | Sonnet 4.6 medium thinking (4000) |
| **Context** | Medium (~70K — 4 API integrations) |
| **Risk** | MEDIUM |
| **Parallelizable** | Yes — can run parallel with S05 (distinct files) |
| **Files** | `tradingagents/dataflows/rss_quantum.py` (new) · `tradingagents/dataflows/arxiv_client.py` (new) · `tradingagents/dataflows/newsapi_client.py` (new, with 100/day budgeter) · `tradingagents/dataflows/reddit_client.py` (new, PRAW OAuth) · `tests/unit/test_rss_quantum.py` (new) · `tests/unit/test_reddit_oauth.py` (new) |
| **SPEC refs** | §4.1, §4.2, §4.4, §4.5, §4.10, §8.1 |
| **PROGRESS tasks** | P2-T8 through P2-T11 |
| **Exit criteria** | • All 4 clients operational; each wrapped in `fetch_with_policy` <br> • Reddit requires OAuth creds; missing creds raises clearly <br> • NewsAPI rate-limits within 100/day budget <br> • Commit `feat(P2): chatter data sources` |

**Briefing prompt**:
```
Read SPEC.md §4.1, §4.2, §4.4, §4.5, §4.10, §8.1.
Read PROGRESS tasks P2-T8 through P2-T11.

Session goal: Implement the 4 "chatter" data-source clients.

Hardened constraints (Session 0a):
- Reddit is PRAW-OAuth only. There is no unauthenticated fallback.
- NewsAPI has a 100/day hard budget — implement a call counter that refuses
  when over budget (returns FetchResult(ok=False, error="budget exhausted")).
- Every client wraps its real fetcher in `fetch_with_policy(source_name, fetcher, tier=...)`.
- Tier assignments per §4.10: RSS = IMPORTANT, arXiv = OPTIONAL,
  NewsAPI = IMPORTANT, Reddit = IMPORTANT.

Tests:
- test_rss_quantum.py: mock feedparser, test dedup
- test_reddit_oauth.py: missing creds → clear error; successful OAuth returns
  at least 1 submission from r/QuantumComputing

Exit when all 4 tasks green and commit made.
```

---

### S05 — Regulatory data sources (SEC EDGAR + SAM.gov + USPTO)

| Field | Value |
|-------|-------|
| **Phase** | 2c |
| **Prereq** | S03 |
| **Model** | Sonnet 4.6 medium thinking (4000) |
| **Context** | Medium (~70K — SEC EDGAR XBRL is gnarly) |
| **Risk** | MEDIUM |
| **Parallelizable** | Yes — can run parallel with S04 |
| **Files** | `tradingagents/dataflows/sec_edgar.py` (new, 10-Q + 10-K + 13F + CIK lookup) · `tradingagents/dataflows/sam_gov.py` (new) · `tradingagents/dataflows/uspto_client.py` (new, weekly poll) · `tests/unit/test_sec_edgar.py` (new) |
| **SPEC refs** | §4.3, §4.6, §4.7, §4.9, §4.10 |
| **PROGRESS tasks** | P2-T12 through P2-T14 |
| **Exit criteria** | • IONQ latest 10-Q RPO + cash + burn extractable <br> • 13F latest filing parseable (CIK→filing→holdings) <br> • SAM.gov last-7-day quantum query returns opportunities <br> • Commit `feat(P2): regulatory + patent data sources` |

**Briefing prompt**:
```
Read SPEC.md §4.3, §4.6, §4.7, §4.9, §4.10.
Read PROGRESS tasks P2-T12 through P2-T14.

Session goal: Implement the 3 regulatory/gov-contract/patent data-source clients.

Constraints:
- SEC EDGAR: always send User-Agent "QuantumTradingAgent research@example.com";
  respect 10 req/s; parse XBRL via companyfacts endpoint for numeric fields,
  HTML filing for narrative (red flags). Tier = IMPORTANT.
- SAM.gov: requires API key (configured in .env). Tier = IMPORTANT.
- USPTO: web-scrape with care; tier = OPTIONAL.

Tests:
- test_sec_edgar.py: offline fixtures (checked-in 10-Q XML) → assert RPO extraction

Exit when all 3 tasks green and commit made.
```

---

### S06 — Memory layer (vector store + KB + decision log)

| Field | Value |
|-------|-------|
| **Phase** | 2d |
| **Prereq** | S03 (for schemas) + S04/S05 content to ingest (optional; can seed after) |
| **Model** | Sonnet 4.6 high thinking (8000) |
| **Context** | Medium (~70K) |
| **Risk** | MEDIUM (sim_date filter must be correct or Phase 7 backtests are worthless) |
| **Parallelizable** | No (structural blocker for S07-S11) |
| **Files** | `tradingagents/memory/vector_store.py` (new, ChromaDB + sim_date filter) · `tradingagents/memory/knowledge_base.py` (new) · `tradingagents/memory/kb/qubit_modalities.md` (seed) · `tradingagents/memory/kb/vendor_roadmaps.md` (seed) · `tradingagents/memory/kb/darpa_programs.md` (seed) · `tradingagents/memory/kb/nist_pqc_timeline.md` (seed) · `tradingagents/memory/decision_log.py` (new, SQLite schema including execution_log skeleton) · `tests/unit/test_vector_store_sim_date.py` (new) · `tests/unit/test_decision_log.py` (new) |
| **SPEC refs** | §8.2, §8.3, §8.4 |
| **PROGRESS tasks** | P2-T15 through P2-T17, plus exit P2-T18 |
| **Exit criteria** | • Vector store ingests all 4 KB files; retrieval at `sim_date=2024-06-01` returns NO doc with `published_at > 2024-06-01` <br> • SQLite schema created with UTC ISO8601 timestamps <br> • `pytest tests/unit/` all green <br> • Commit `feat(P2): memory layer with sim_date discipline` <br> • Phase 2 tag: `git tag phase-2-complete` |

**Briefing prompt**:
```
Read SPEC.md §8.2, §8.3, §8.4, and review §4.10 + §8.5 for integration points.
Read PROGRESS tasks P2-T15, P2-T16, P2-T17, P2-T18 (exit).

Session goal: Implement the memory layer. This closes Phase 2.

Embedding: Use sentence-transformers all-MiniLM-L6-v2 locally. Do NOT use
"Anthropic embedding API" — it does not exist (see Session 0a revision).

Critical: vector_store.retrieve() MUST accept a sim_date parameter and filter
via Chroma `where: {"published_at": {"$lte": sim_date.isoformat()}}`. Phase 7
backtests depend on this. Test it explicitly — ingest 3 docs with known dates,
query at a middle date, assert only 1 or 2 return.

decision_log.py schemas (all timestamps UTC ISO8601 with 'Z'):
  - decisions (§8.4)
  - execution_log (§8.4, all 6 timestamps + 6 derived latencies + slippage)
  - outcomes (§8.4)
  - cost_log (for S15 cost tracker)

Exit when all tests green and phase tag applied.
```

---

### S07 — Quantum Tech Expert agent (NOVEL, Opus 4.6 high)

| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Prereq** | S06 |
| **Model** | **Opus 4.6, thinking_budget 16000** (prompt engineering benefits from max reasoning) |
| **Context** | Large (~150K — SPEC §7.1 + KB files + reference papers) |
| **Risk** | HIGH |
| **Parallelizable** | Yes — with S08, S09, S10 |
| **Files** | `tradingagents/agents/analysts/quantum_tech_expert.py` (new) · `tradingagents/memory/kb/qubit_modalities.md` (extend) · `tradingagents/memory/kb/vendor_roadmaps.md` (extend) · `tests/unit/test_quantum_tech_expert.py` (new, mocked tools) · `tests/unit/test_schemas.py` (extend fixtures for QuantumTechOutput) |
| **SPEC refs** | §7.1, §8.3, §8.5, §4.8 |
| **PROGRESS tasks** | P3-T1, P3-T2 |
| **Exit criteria** | • Mocked-input test produces `QuantumTechOutput`-valid JSON <br> • Live run on IONQ returns `tech_score` + all required fields <br> • Guardrail test still passes (no yfinance in this file) <br> • Commit `feat(P3): Quantum Tech Expert agent` |

**Briefing prompt**:
```
Read SPEC.md §7.1 (verbatim prompt — do not paraphrase), §8.3, §8.5, §4.8.
Read PROGRESS tasks P3-T1, P3-T2.

Session goal: Implement the Quantum Tech Expert agent. Prompt quality is
the hardest work in this project — this session gets it running; future
sessions iterate on quality with real output.

Constraints:
- Runtime model: claude-opus-4-6 + thinking_budget=16000 (per AGENT_MODEL_MAP).
- Output MUST validate against QuantumTechOutput (memory/schemas.py).
- The RAG context (§8.3 knowledge base) is retrieved before calling the LLM —
  top 5 KB docs + top 5 arxiv/RSS docs matching the query ticker.
- This session is the first to extend the KB: add qubit_modalities.md
  (comparison table) and vendor_roadmaps.md (IBM/Google/IONQ/Rigetti/
  Quantinuum/D-Wave/PsiQuantum). 400-800 words each, factual, citations.

Test strategy:
- Mocked tool outputs (fabricated IONQ data blob) → agent produces valid JSON
- Live run (requires moomoo + data sources) → decision JSON with reasoning citing
  at least 2 of the KB entries

Exit when 2 tasks green and commit made.
```

---

### S08 — Commercialization Analyst (NOVEL, Opus 4.6 high)

| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Prereq** | S06 |
| **Model** | **Opus 4.6, thinking_budget 16000** (prompt design) |
| **Context** | Medium (~100K — SPEC §7.2 + SEC EDGAR examples) |
| **Risk** | HIGH |
| **Parallelizable** | Yes — with S07, S09, S10 |
| **Files** | `tradingagents/agents/analysts/commercialization.py` (new) · `tests/unit/test_commercialization.py` (new) · `tests/unit/test_schemas.py` (extend) |
| **SPEC refs** | §7.2, §4.3, §8.5 |
| **PROGRESS tasks** | P3-T3 |
| **Exit criteria** | • QUBT (pre-revenue) capped at 30 per the hard rule <br> • IONQ run returns full dimensional breakdown <br> • Press-release-only signals discounted 70% per prompt <br> • Commit `feat(P3): Commercialization Analyst` |

**Briefing prompt**:
```
Read SPEC.md §7.2 (verbatim prompt), §4.3 (SEC EDGAR inputs), §8.5.
Read PROGRESS task P3-T3.

Session goal: Implement the Commercialization Analyst. Runtime model per
AGENT_MODEL_MAP is Sonnet 4.6 high, but the prompt-design session (this one)
uses Opus 4.6 for reasoning budget.

Hard rules embedded in the prompt (see §7.2):
- TTM revenue < $1M → cap commercialization_score at 30
- Press-release-only signals discounted by 70%
- REAL signals: SEC-disclosed RPO, confirmed revenue, signed contracts

Test:
- Feed a QUBT-like synthetic input (revenue < $1M) → assert score ≤ 30
- Feed an IONQ-like synthetic input → assert full range accessible
- Feed an MOU-only input → assert "recent_signals" mark the MOU with ≤ 30%
  of the impact weight a signed contract would get

Exit when tests green and commit made.
```

---

### S09 — Valuation & Financial Health (NOVEL, Opus 4.6 high)

| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Prereq** | S06 |
| **Model** | **Opus 4.6, thinking_budget 16000** (prompt design) |
| **Context** | Medium (~90K — SPEC §7.3 + XBRL examples) |
| **Risk** | HIGH |
| **Parallelizable** | Yes — with S07, S08, S10 |
| **Files** | `tradingagents/agents/analysts/valuation_health.py` (new) · `tests/unit/test_valuation_health.py` (new) · `tests/unit/test_schemas.py` (extend) |
| **SPEC refs** | §7.3, §4.3, §8.5 |
| **PROGRESS tasks** | P3-T4 |
| **Exit criteria** | • Runway < 4 quarters → `financial_health_score` capped at 40 <br> • Synthetic 10-Q with going-concern text → capped at 20 <br> • P/S > 5× sector AND runway < 6 → `bubble_risk` flag <br> • Commit `feat(P3): Valuation & Financial Health` |

**Briefing prompt**:
```
Read SPEC.md §7.3 (verbatim prompt), §4.3 (SEC EDGAR inputs), §8.5.
Read PROGRESS task P3-T4.

Session goal: Implement the Valuation & Financial Health analyst.

Hard rules embedded (see §7.3):
- Runway < 4 quarters → HIGH risk, score ≤ 40
- P/S > 5× sector median AND runway < 6 → bubble_risk flag
- Going-concern language → immediate flag, score ≤ 20

Tests: feed synthetic 10-Q variants (3 cases above + a control) → assert
each hard rule fires correctly.

Exit when tests green and commit made.
```

---

### S10 — Regulatory Policy + Flow & Technicals agents

| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Prereq** | S06 |
| **Model** | Sonnet 4.6 medium-high (8000) |
| **Context** | Medium (~80K) |
| **Risk** | MEDIUM |
| **Parallelizable** | Yes — with S07, S08, S09 |
| **Files** | `tradingagents/agents/analysts/regulatory_policy.py` (new) · `tradingagents/agents/analysts/flow_technicals.py` (new) · `tests/unit/test_regulatory_policy.py` (new) · `tests/unit/test_flow_technicals.py` (new) · `tests/unit/test_schemas.py` (extend) |
| **SPEC refs** | §7.4, §7.5, §4.8 (flow_technicals uses moomoo-only for IV) |
| **PROGRESS tasks** | P3-T5, P3-T6 |
| **Exit criteria** | • Regulatory agent returns policy events citing actual DARPA/DOE names <br> • Flow agent pulls IV from `get_live_options_chain` (moomoo), never yfinance <br> • Guardrail still passes <br> • Commit `feat(P3): Regulatory Policy + Flow & Technicals` |

**Briefing prompt**:
```
Read SPEC.md §7.4, §7.5 (verbatim prompts). §7.5 was hardened in Session 0a:
IV and options data come from moomoo get_live_options_chain, NOT yfinance.
Read PROGRESS tasks P3-T5, P3-T6.

Session goal: Implement the remaining two novel analyst agents together
(smaller scope than S07-S09).

Constraints:
- flow_technicals.py MUST NOT import yfinance anywhere. Guardrail
  test will fail on commit otherwise.
- regulatory_policy: focus on EVENTS tied to specific companies
  (DARPA contract to IonQ is actionable; "quantum is strategic" is not).

Exit when tests green and commit made.
```

---

### S11 — Traditional 4 agent modifications

| Field | Value |
|-------|-------|
| **Phase** | 3 |
| **Prereq** | S07-S10 (so all 9 schemas exist) |
| **Model** | Sonnet 4.6 medium (4000) |
| **Context** | Medium (~80K) |
| **Risk** | MEDIUM (touching inherited files — careful with rebase semantics) |
| **Parallelizable** | No |
| **Files** | `tradingagents/agents/analysts/technical.py` (modify — moomoo-only) · `tradingagents/agents/analysts/news.py` (modify — add strategic_score + quantum RSS primary) · `tradingagents/agents/analysts/sentiment.py` (modify — add macro_score + r/QuantumComputing) · `tradingagents/agents/analysts/fundamentals.py` (modify — RPO + runway + qubit count) · `tests/unit/test_schemas.py` (extend News/Sentiment fixtures) |
| **SPEC refs** | §7.6, §8.5 |
| **PROGRESS tasks** | P3-T7 through P3-T10 |
| **Exit criteria** | • All 4 modified agents validate new outputs <br> • `NewsOutput` contains `strategic_score`, `SentimentOutput` contains `macro_score` <br> • Guardrail passes <br> • Commit `feat(P3): traditional 4 agents — quantum universe + schema contracts` |

**Briefing prompt**:
```
Read SPEC.md §7.6 and §8.5.
Read PROGRESS tasks P3-T7, P3-T8, P3-T9, P3-T10.

Session goal: Retrofit the 4 inherited TradingAgents analyst agents to the
quantum universe and the new schema contracts.

Critical additions (per Session 0a hardening):
- News agent: output MUST include strategic_score (0-100, 50=neutral).
  The Scoring Engine in §9.3 reads this field.
- Sentiment agent: output MUST include macro_score (0-100, 50=neutral).

Constraint: technical.py can ONLY read price/volume from moomoo. Do not
import from dataflows.historical. Guardrail will flag it.

Exit when tests green and commit made.
```

---

### S12 — Graph wiring + Bull/Bear/Trader/PM updates

| Field | Value |
|-------|-------|
| **Phase** | 3 (tail) |
| **Prereq** | S11 |
| **Model** | Sonnet 4.6 high (8000) |
| **Context** | Medium (~90K — touching orchestration) |
| **Risk** | MEDIUM (LangGraph state plumbing starts here) |
| **Parallelizable** | No |
| **Files** | `tradingagents/graph/trading_graph.py` (modify — 9-analyst parallel phase; rename `agents/risk/` → `agents/risk_debate/`) · `tradingagents/agents/researchers/bull.py` (modify — consume new outputs) · `tradingagents/agents/researchers/bear.py` (modify) · `tradingagents/agents/trader.py` (modify — append DATA SOURCE DISCIPLINE block) · `tradingagents/agents/portfolio_manager.py` (modify — add {{stage_weighted_score}} slot) · `tests/integration/test_full_pipeline_ionq.py` (new, Phase 3 exit gate) |
| **SPEC refs** | §7.7, §5 (folder rename), §4.8 (trader discipline) |
| **PROGRESS tasks** | P3-T11 through P3-T15 |
| **Exit criteria** | • Pipeline on IONQ produces valid outputs from all 9 analysts <br> • Bull/Bear reasoning references ≥3 of the 5 new dimensions <br> • Trader prompt contains DATA SOURCE DISCIPLINE verbatim <br> • `agents/risk_debate/` exists (folder renamed) <br> • Commit `feat(P3): graph wiring + 9-analyst pipeline` + `git tag phase-3-complete` |

**Briefing prompt**:
```
Read SPEC.md §7.7, §5 (for the renamed agents/risk_debate/ folder), §4.8.
Read PROGRESS tasks P3-T11 through P3-T15.

Session goal: Wire all 9 analysts into the parallel analyst phase of
trading_graph.py. Update downstream agents (Bull/Bear/Trader/PM) to
consume the new outputs. Rename agents/risk/ → agents/risk_debate/.

Folder rename steps (via git mv to preserve history):
- git mv tradingagents/agents/risk tradingagents/agents/risk_debate
- Update all imports referencing the old path
- Run guardrail test; verify no yfinance regressions

Trader prompt must include the verbatim DATA SOURCE DISCIPLINE block from §7.7.

Integration test (test_full_pipeline_ionq.py — first integration test):
- Run full pipeline on IONQ
- Assert 9 analyst outputs all Pydantic-valid
- Assert Bull and Bear mention at least 3 of {tech, commercialization, valuation,
  regulatory, flow} by name
- Cost budget: <$5 per run (per SPEC §14, relaxed from $2.50 in Session 0b ADR)

Exit when test green, commit made, phase-3 tag applied.
```

---

### S13 — Scoring engine

| Field | Value |
|-------|-------|
| **Phase** | 4 |
| **Prereq** | S12 |
| **Model** | Sonnet 4.6 high (8000) |
| **Context** | Small (~50K) |
| **Risk** | LOW-MEDIUM |
| **Parallelizable** | No (but thin enough to be quick) |
| **Files** | `tradingagents/scoring/engine.py` (new) · `tradingagents/scoring/dimensions.py` (new) · `tests/unit/test_scoring_engine.py` (new) |
| **SPEC refs** | §9, §4.10 (confidence discount) |
| **PROGRESS tasks** | P4-T1, P4-T2 |
| **Exit criteria** | • All 4 stages (pre_revenue / early_revenue / scaling / established) correctly detected <br> • Weighted score math matches §9.3 exactly <br> • `data_incomplete` dimensions have their weight × 0.5 per §4.10 <br> • Commit `feat(P4): stage-weighted scoring engine` |

---

### S14 — Hard risk gate + kill switch

| Field | Value |
|-------|-------|
| **Phase** | 4 |
| **Prereq** | S13 |
| **Model** | Sonnet 4.6 high (8000) |
| **Context** | Medium (~70K) |
| **Risk** | MEDIUM (wiring into graph; §4.8 `_source` assertion must be enforced) |
| **Parallelizable** | No |
| **Files** | `tradingagents/risk/hard_gate.py` (new) · `tradingagents/risk/kill_switch.py` (new) · `tradingagents/graph/trading_graph.py` (modify — insert gate between Trader/Risk and PM) · `tests/unit/test_hard_gate.py` (new) |
| **SPEC refs** | §10 (all rules), §4.8.3 (moomoo `_source` check), §11.2 |
| **PROGRESS tasks** | P4-T3 through P4-T7 |
| **Exit criteria** | • Every VETO/HALT path covered by unit test, including `stale_data_rejected_not_from_moomoo` <br> • `WEEKLY_LOSS_HALT` and `MAX_TRADES_PER_DAY_PER_TICKER` **actually wired** (not dead code — dead limits were a risk in v1 of SPEC) <br> • Kill switch works: `touch /tmp/quantum_agent_kill` halts next run with SystemExit <br> • Commit `feat(P4): hard risk gate + kill switch` + `git tag phase-4-complete` |

**Briefing prompt**:
```
Read SPEC.md §10, §4.8.3, §11.2, §4.10.
Read PROGRESS tasks P4-T3 through P4-T7.

Session goal: Implement Layer 6 (Hard Risk Gate) and the kill switch. Wire
the gate between Trader/Risk team output and Portfolio Manager input.

Critical: Session 0a review flagged that SPEC §10's hard_gate.py example has
DEAD CODE (WEEKLY_LOSS_HALT and MAX_TRADES_PER_DAY_PER_TICKER are defined
but never checked). Fix both in this session — actually check weekly PnL
(requires decision_log lookup) and per-ticker daily trade count.

Test every VETO/HALT path including:
- stale_data_rejected_not_from_moomoo (feed market_data without _source tag)
- position_cap_exceeded
- quantum_aggregate_cap_exceeded
- daily_loss_halt_triggered
- weekly_loss_halt_triggered  <-- formerly dead
- max_trades_per_day_triggered <-- formerly dead
- insufficient_cash_reserve
- ps_ratio_too_high
- implied_volatility_too_high

Exit when all tests green, gate wired into graph, phase-4 tag applied.
```

---

### S15 — Paper executor + T0-T5 state threading (HARDEST PLUMBING)

| Field | Value |
|-------|-------|
| **Phase** | 5 |
| **Prereq** | S14 |
| **Model** | **Opus 4.6, thinking_budget 16000** |
| **Context** | Large (~130K — LangGraph internals + §10A) |
| **Risk** | HIGH |
| **Parallelizable** | No |
| **Files** | `tradingagents/execution/paper_executor.py` (new) · `tradingagents/memory/decision_log.py` (extend — complete execution_log writer) · `tradingagents/graph/trading_graph.py` (modify — thread T0-T5 through state, wire execution after PM) · `tradingagents/dataflows/moomoo_client.py` (verify `trd_env="SIMULATE"` path) · `tests/unit/test_paper_executor.py` (new, 5 status branches) · `tests/integration/test_latency_budget.py` (new, nightly) · `tests/integration/test_hold_decision_logging.py` (new) |
| **SPEC refs** | §10A (all subsections), §8.4, §4.8 |
| **PROGRESS tasks** | P5-T1 through P5-T6 |
| **Exit criteria** | • Running pipeline on IONQ in `ENVIRONMENT=paper` submits SIMULATE order <br> • `execution_log` row has all 6 timestamps (non-null for buy/sell) + all 6 derived latencies <br> • Hold decision writes T0-T3 only (T4/T5 null) <br> • Timeout / reject / partial-fill each covered <br> • Guardrail test still passes (paper_executor does NOT import yfinance) <br> • Commit `feat(P5): paper executor + T0-T5 state threading` + `git tag phase-5-complete` |

**Briefing prompt**:
```
Read SPEC.md §10A (every subsection), §8.4, §4.8.3 (wait_for_fill).
Read PROGRESS tasks P5-T1 through P5-T6.

Session goal: This is the hardest plumbing session in the project. Thread
6 timestamps (T0-T5) through LangGraph state from data ingestion all the
way to order fill, without any node overwriting an existing value.

State-threading design:
- T0 and T1: already emitted by MoomooClient (see S02). Add them to the
  graph state dict at the data-fetch node: state["t0_market_tick"],
  state["t1_data_fetched"].
- T2: first LLM call node — stamp state["t2_pipeline_start"] = now_utc().
- T3: after PM node completes — stamp state["t3_decision_final"] = now_utc().
- T4/T5: set in paper_executor.execute_paper(ctx, moomoo) before/after order.

Invariant: no graph node mutates an existing timestamp. Add a unit test
(`test_state_threading.py`) that runs a pipeline with mocked moomoo + LLMs
and asserts all 6 state keys are set exactly once.

paper_executor must handle all 5 status branches:
- "skipped_hold"   — action=="hold"
- "filled"         — full fill
- "partial"        — partial fill (non-zero fill_qty < order_qty)
- "rejected"       — moomoo returned rejection
- "timeout"        — wait_for_fill hit timeout_sec; status="timeout", T5=None

Do NOT retry after timeout. Log the state and leave the decision for manual
review.

Nightly test_latency_budget.py: mark @pytest.mark.nightly. Do not include
in default CI — it costs real API + moomoo paper and should run once/day.

Exit when phase-5-complete tag applied.
```

---

### S16 — Orchestration: scheduler + cost + alerts + latency report

| Field | Value |
|-------|-------|
| **Phase** | 6 |
| **Prereq** | S15 |
| **Model** | Sonnet 4.6 high (8000) |
| **Context** | Medium (~80K) |
| **Risk** | MEDIUM (Gmail integration surface) |
| **Parallelizable** | No |
| **Files** | `tradingagents/orchestration/scheduler.py` (new — launchd wrapper, NOT APScheduler) · `tradingagents/orchestration/cost_tracker.py` (new — per-day + per-cycle circuit breakers) · `tradingagents/orchestration/alerts.py` (new — Gmail via MCP) · `tradingagents/orchestration/monitor.py` (new) · `tradingagents/orchestration/latency_report.py` (new) · `tradingagents/daily_cycle.py` (new — single-shot entry point for launchd) · `tests/unit/test_cost_tracker_circuit_breaker.py` (new) |
| **SPEC refs** | §11 (all subsections), §10A.7 |
| **PROGRESS tasks** | P6-T1 through P6-T7 |
| **Exit criteria** | • launchd job fires `python -m tradingagents.daily_cycle` at 8:00 ET weekdays <br> • Per-cycle + per-day cost circuit breakers both enforced <br> • Daily Gmail report (positions + PnL + rationale + latency summary) delivered <br> • Commit `feat(P6): orchestration` + `git tag phase-6-complete` |

**Briefing prompt**:
```
Read SPEC.md §11, §10A.7.
Read PROGRESS tasks P6-T1 through P6-T7.

Session goal: Wire the project up for unattended daily operation.

Per SPEC §11.1 (updated in Session 0b ADR sync): use **system launchd** on
macOS (not APScheduler in-process). Reason: if APScheduler shares a process
with the pipeline, a pipeline crash kills the scheduler — SPOF. launchd +
a single-shot `python -m tradingagents.daily_cycle` is simpler and
independently recoverable. SPEC §11.1 contains the full launchd plist.

Cost tracker must enforce BOTH per-day AND per-cycle hard stops (Session 0a
flagged per-cycle as missing). A single cycle running Opus + 9 agents can
spend > $30. Before each new agent call, check the running per-cycle total
against PER_CYCLE_HARD_STOP_USD; if exceeded, abort the cycle (write decision
as "hold" with block_reason="per_cycle_cost_halt").

Alerts via Gmail MCP (user has configured). Do NOT add Slack in this session —
deferred per Session 0a review (only one channel for V1).

Exit when phase-6-complete tag applied.
```

---

### S17 — Backtest framework + sim_date enforcement

| Field | Value |
|-------|-------|
| **Phase** | 7 |
| **Prereq** | S16 |
| **Model** | **Opus 4.6, thinking_budget 16000** (correctness is subtle) |
| **Context** | Large (~120K) |
| **Risk** | HIGH (look-ahead bias is silent and catastrophic) |
| **Parallelizable** | No |
| **Files** | `tradingagents/backtest/runner.py` (new, `vectorbt`) · `tradingagents/backtest/market_simulator.py` (new — mocks moomoo at a sim_date) · `tests/backtest/test_no_lookahead.py` (new, CRITICAL) · `tests/backtest/test_reproducibility.py` (new) · `data/historical/` (cached OHLCV) |
| **SPEC refs** | §13 Phase 7, §8.2 (sim_date filter), §14 |
| **PROGRESS tasks** | P7-T1 through P7-T4 |
| **Exit criteria** | • Running backtest for IONQ at sim_date=2024-06-01 succeeds <br> • test_no_lookahead.py passes (RAG retrieval honors sim_date) <br> • test_reproducibility.py passes (temperature=0, same inputs → same outputs) <br> • Commit `feat(P7): backtest framework + sim_date enforcement` |

**Briefing prompt**:
```
Read SPEC.md §13 Phase 7, §8.2 (sim_date filter — critical), §14, §15.
Read PROGRESS tasks P7-T1 through P7-T4.

Session goal: Implement the backtest framework. Correctness over speed —
look-ahead bias is silent and will invalidate every metric.

Per SPEC §2 (updated in Session 0b ADR sync): use **vectorbt**. Reasons:
vectorized, Python-native, better maintained, simpler API. Backtrader was
dropped from requirements.txt in Session 0b.

Every code path that calls an agent must pass sim_date. Every RAG lookup
the agent makes must use that sim_date to filter vector store retrieval.
No exceptions. Test this explicitly.

market_simulator replaces the live MoomooClient during backtest: returns
historical OHLCV + a synthetic T0/T1 matching the bar's timestamp. This
allows T0-T3 latency to be measured even in backtest (T4/T5 remain null
since no real order is placed).

For reproducibility: all LLM calls use temperature=0 during backtest mode.

Exit when all 4 tasks green and commit made.
```

---

### S18 — Backtest run + metrics + tuning

| Field | Value |
|-------|-------|
| **Phase** | 7 |
| **Prereq** | S17 |
| **Model** | Sonnet 4.6 high (8000) |
| **Context** | Medium (~80K — large output review) |
| **Risk** | MEDIUM (budget and patience; a 12-month backtest is expensive) |
| **Parallelizable** | No |
| **Files** | `tradingagents/backtest/metrics.py` (new — Sharpe, MDD, etc.) · `tradingagents/backtest/compare_baselines.py` (new — vs. Buy&Hold, MACD, SMA) · `results/backtest_v1.md` (new, output) · Possibly minor prompt/weight tweaks in agents |
| **SPEC refs** | §13 Phase 7, §16 |
| **PROGRESS tasks** | P7-T5 through P7-T7 |
| **Exit criteria** | • 12-month backtest Jan 2024 → Apr 2025 complete on all 4 quantum pure-plays <br> • Metrics table + baseline comparison in `results/backtest_v1.md` <br> • Sharpe > 1.5 AND MDD < 25% to proceed <br> (if not met, iterate weights/prompts before closing this session) <br> • Commit `feat(P7): backtest v1 results` + `git tag phase-7-complete` |

**Briefing prompt**:
```
Read SPEC.md §13 Phase 7, §16.
Read PROGRESS tasks P7-T5, P7-T6, P7-T7.

Session goal: Run the 12-month backtest and produce the metrics report.

Cost warning: this is the single most expensive session in the project.
12 months × ~250 trading days × 9 agents × full pipeline ≈ $$$. Consider:
- Use Message Batches API (50% discount) since this is non-urgent
- Run only quantum pure-plays (4 tickers) for v1; add exposure stocks in v2
- Consider weekly decision cadence for backtest v1, daily for later

Metrics (§16 targets):
- Sharpe > 1.5 (Good tier)
- MDD < 25% (Good tier)
- Beats Buy & Hold on all 4 pure-plays by 20%+ (Exceptional tier)

If Sharpe < 1.5: tune weights (§9.2) or iterate one novel agent's prompt
before closing this session. Document tuning in backtest_v1.md.

Exit when phase-7-complete tag applied (requires Sharpe > 1.5 AND MDD < 25%).
```

---

### S19 — Paper validation (30-day ops)

| Field | Value |
|-------|-------|
| **Phase** | 8 |
| **Prereq** | S18 |
| **Model** | Sonnet 4.6 medium (for weekly reviews) |
| **Context** | Small per review (~40K) |
| **Risk** | HIGH (operational; regressions surface here) |
| **Parallelizable** | No |
| **Files** | `results/phase8_review.md` (running log) · `results/phase8_tuning.md` (running log) · Possibly minor prompt/weight tweaks |
| **SPEC refs** | §13 Phase 8, §16 |
| **PROGRESS tasks** | P8-T1 through P8-T7 |
| **Exit criteria** | • 30 trading days logged in `execution_log` <br> • 4 weekly review entries <br> • 30-day Sharpe > 1.0 AND MDD < 15% AND median latency stable within ±20% of Phase 5 baseline <br> • User approval to proceed to Phase 9 <br> • `git tag phase-8-complete` |

**Briefing prompt**:
```
Read SPEC.md §13 Phase 8, §16, §15.
Read PROGRESS tasks P8-T1 through P8-T7.

Session type: OPERATIONS, not feature building. This "session" spans 30
calendar days; plan to use short CC sessions for weekly review cycles.

Do not edit agent prompts mid-week without a written reason in
phase8_tuning.md. Regression detection requires stability.

Weekly checklist:
1. Review all VETO decisions — is the hard gate too strict / too lax?
2. Slippage histogram for the week — drift > 30% vs Phase 5 baseline?
3. Latency: median total_market_to_fill_ms — stable?
4. Any KILL_SWITCH activations?

Exit after day 30 IF all gates pass. User approval required.
```

---

### S20 — Live executor + Phase 9 go-live

| Field | Value |
|-------|-------|
| **Phase** | 9 |
| **Prereq** | S19 + explicit user approval |
| **Model** | Sonnet 4.6 high (8000) |
| **Context** | Small (~40K) |
| **Risk** | MEDIUM (code is small, but real money) |
| **Parallelizable** | No |
| **Files** | `tradingagents/execution/live_executor.py` (new) · `tradingagents/graph/trading_graph.py` (modify — branch on ENVIRONMENT==live) · `.env` (switch) · `tests/unit/test_live_executor_guardrail.py` (new) |
| **SPEC refs** | §13 Phase 9, §10A.5 |
| **PROGRESS tasks** | P9-T1 through P9-T4 |
| **Exit criteria** | • live_executor guardrail: raises unless ENVIRONMENT=live AND explicit user approval flag <br> • Cap MAX_QUANTUM_EXPOSURE=0.05 (not 0.15 — 5% for first 3 months per SPEC) <br> • First live trade recorded in execution_log with environment="live" <br> • Commit `feat(P9): live executor (5% exposure cap)` + `git tag phase-9-live` |

**Briefing prompt**:
```
User approval already obtained for this session. Re-confirm before the
FIRST live order by reading back: "I am about to submit a REAL money order
to moomoo for {ticker} {action} {qty}. Confirm by typing APPROVED."

Read SPEC.md §13 Phase 9, §10A.5.
Read PROGRESS tasks P9-T1 through P9-T4.

Session goal: Ship the live executor and switch ENVIRONMENT=live under a
reduced exposure cap.

Hardcoded safety:
- live_executor refuses if ENVIRONMENT != "live"
- live_executor refuses if MAX_QUANTUM_EXPOSURE > 0.05 (first 3 months only)
- Kill switch checked at every pipeline entry

After the first successful live fill, commit and tag. Monthly reviews
happen in follow-up sessions not scheduled here.
```

---

## Cross-cutting concerns — how they appear in sessions

### §4.8 data discipline

| Session | Concern manifestation |
|---------|-----------------------|
| S02 | Introduces MoomooClient + guardrail test. Test must pass on every commit FROM THIS SESSION ONWARD. |
| S04, S05 | Data-source clients all tier-wrapped; none import yfinance. |
| S06 | Memory layer touches no market data. Neutral. |
| S07-S12 | Every agent file is subject to the guardrail. Commit = guardrail run. |
| S14 | Hard gate's `_source == "moomoo"` assertion is the runtime enforcement point. |
| S15 | paper_executor must not import yfinance. Guardrail dir list includes `execution/`. |
| S17 | Backtest uses market_simulator (historical data OK); decision path still honors moomoo discipline via the simulator's `_source="moomoo"` synthesized tag. |
| S20 | live_executor subject to guardrail. |

### §10A latency instrumentation

| Session | Concern manifestation |
|---------|-----------------------|
| S02 | MoomooClient emits T0 (`ts_exchange`) and T1 (`ts_received`). |
| S06 | decision_log.py schema includes `execution_log` with all 6 timestamps + 6 derived latencies. |
| S12 | Graph wiring preserves T0/T1 through the analyst parallel phase into downstream nodes. |
| S15 | **The session where T2-T5 are added and end-to-end latency is wired.** Hardest plumbing work. Nightly latency budget test installed. |
| S16 | latency_report.py generates daily digest; alerts hook into Gmail. |
| S17 | Backtest's market_simulator synthesizes T0/T1 so backtest decisions carry comparable data-staleness + pipeline-duration metrics (T4/T5 remain null — no real orders). |
| S19 | Latency regressions detected in weekly review of 30-day paper run. |

### §4.10 graceful degradation

| Session | Concern manifestation |
|---------|-----------------------|
| S03 | Introduces `fetch_with_policy` helper + `test_graceful_degradation.py`. |
| S04, S05 | Every data-source client wrapped in `fetch_with_policy`. |
| S07-S11 | Every agent branches on `data_incomplete` flag. |
| S13 | Scoring engine halves the weight of any dimension flagged `data_incomplete`. |
| S14 | Hard gate treats stale moomoo data as CRITICAL failure → pipeline halts for ticker. |

### §8.5 Pydantic schemas

| Session | Concern manifestation |
|---------|-----------------------|
| S03 | `memory/schemas.py` written with all 9 agent models + test_schemas.py fixtures. |
| S07-S11 | Each agent validates output against its model; fails → `data_incomplete`. |
| S12 | Integration test asserts 9 analysts all produce schema-valid JSON. |
| S17 | Backtest reuses the same validation — schema breakage stops the backtest cleanly. |
