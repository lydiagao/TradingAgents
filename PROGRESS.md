# Progress Tracker — Quantum Trading Agent

Living checklist mirroring SPEC Phase 1-9 tasks. Each task has a unique ID, an exit definition ("done looks like..."), and a SPEC section reference.

**Update rule**: tick each checkbox in the same commit that completes the task. Do not batch ticks.

**Cross-cutting reminders** (apply to every Phase from P2 onward):
- **§4.8 data discipline**: any file under `agents/`, `risk/`, `scoring/`, `orchestration/`, `execution/` MUST NOT import yfinance. `test_no_yfinance_on_hot_path.py` (installed in P2-T5) must pass on every commit.
- **§10A latency**: T0 / T1 tagging starts at MoomooClient in P2-T2; T2-T5 thread through LangGraph state from P5 onward. No node may mutate an existing timestamp.
- **§4.10 graceful degradation**: CRITICAL sources halt the ticker; IMPORTANT downgrade confidence + weight × 0.5; OPTIONAL silent-skip.

---

## Phase 1 — Scaffold (target: 1 week)

- [x] **P1-T1** Fork `TauricResearch/TradingAgents` on GitHub. → https://github.com/lydiagao/TradingAgents
- [x] **P1-T2** Clone fork locally, create `quantum-fork` branch. Planning history merged via git merge --allow-unrelated-histories.
- [x] **P1-T3** `uv venv --python 3.13 .venv` — Python 3.13.12.
- [x] **P1-T4** `uv pip install -e .` (upstream) + `uv pip install -r requirements-quantum.txt` (9 additions). 75 tests in test_model_config + 6 upstream.
- [x] **P1-T5** `claude` CLI 2.1.112 可用 + CC 订阅已登录。`--model` / `--effort` / `--json-schema` / `--permission-mode` flags pinned.
- [x] **P1-T6** `tradingagents/config/model_config.py` — AGENT_MODEL_MAP (16 keys) + get_model_config + build_cli_args + _budget_to_effort.
- [x] **P1-T7** `tradingagents/config/universe.py` — 9 tickers.
- [x] **P1-T8** `tradingagents/config/ciks.json` — 9 CIKs, all SEC EDGAR 200.
- [x] **P1-T9** `tradingagents/agents/_runner.py` — run_claude(agent_name, prompt, schema). CLI structured_output 字段 pinned. Upstream bind_tools 改写推迟到 Phase 3.
- [x] **P1-T10** `tests/unit/test_model_config.py` — 75 tests all green (0.03s).
- [x] **P1-T11** `python -m tradingagents.phase1_baseline NVDA 2026-04-15` → `{"action":"hold","confidence":0.62,...}`. CLI 走订阅，$0 API。

---

## Phase 2 — Data layer (target: 2 weeks)

### 2a. moomoo + yfinance isolation (keystone — must be FIRST task of Phase 2)

- [ ] **P2-T1** Implement `dataflows/moomoo_client.py` with full interface per §4.8.3 (including `wait_for_fill`, `get_historical_klines`, `ts_exchange`/`ts_received` tagging). *Done*: connects to local OpenD; `get_realtime_quote("IONQ")` returns dict with `_source: "moomoo"`, `ts_exchange`, `ts_received`, `price`. *SPEC*: §4.8.3
- [ ] **P2-T2** Implement `dataflows/__init__.py` with lazy `get_client()` pattern. *Done*: `import tradingagents.dataflows` does NOT open a moomoo connection; only calling `get_realtime_quote(...)` does. *SPEC*: §4.8.2
- [ ] **P2-T3** Implement `dataflows/historical.py` — sole yfinance home. *Done*: only this file contains `import yfinance`. *SPEC*: §4.8.2
- [ ] **P2-T4** Implement `tests/unit/test_moomoo_source_tag.py`. *Done*: asserts every method's return dict carries `_source == "moomoo"`. *SPEC*: §14
- [ ] **P2-T5** Implement `tests/unit/test_no_yfinance_on_hot_path.py` with `FORBIDDEN_DIRS = ["agents","risk","scoring","orchestration","execution"]`. *Done*: passes on current tree; would FAIL if yfinance import added to any forbidden dir. This test **must pass on every commit from now on**. *SPEC*: §4.8.2

### 2b. Resilience + schema scaffolding

- [ ] **P2-T6** Implement `dataflows/retry.py` with `FetchResult` and `fetch_with_policy(source, fetcher, tier)` per §4.10. *Done*: `test_graceful_degradation.py` passes. *SPEC*: §4.10
- [ ] **P2-T7** Implement `memory/schemas.py` with Pydantic models for all 9 agents (Quantum Tech, Commercialization, Valuation Health, Regulatory, Flow, News, Sentiment, and Technical/Fundamentals stubs). *Done*: `from tradingagents.memory.schemas import *` imports; `test_schemas.py` covers golden + mutated fixtures. *SPEC*: §8.5

### 2c. Free data sources

- [ ] **P2-T8** Implement `dataflows/rss_quantum.py` with 4 quantum RSS feeds. *Done*: `fetch_all_feeds()` yields deduped entries; failure of 1-2 feeds is tolerated per §4.10. *SPEC*: §4.1, §8.1
- [ ] **P2-T9** Implement `dataflows/arxiv_client.py`. *Done*: pulls `cat:quant-ph` latest 30; filter keyword set matches SPEC. *SPEC*: §4.2
- [ ] **P2-T10** Implement `dataflows/newsapi_client.py` with rate limiter (100 req/day budget) + cache. *Done*: over-budget call returns cached or `FetchResult(ok=False)`; no 429 errors. *SPEC*: §4.4
- [ ] **P2-T11** Implement `dataflows/reddit_client.py` via PRAW + OAuth (no unauthenticated fallback). *Done*: fetches 50 newest from `r/QuantumComputing`; missing OAuth creds raise clearly at call time. *SPEC*: §4.5
- [ ] **P2-T12** Implement `dataflows/sec_edgar.py` with CIK lookup, 10-Q / 10-K / 13F parsers, proper `User-Agent`. *Done*: pulls IONQ's latest 10-Q and extracts RPO + cash + burn rate. *SPEC*: §4.3, §4.9
- [ ] **P2-T13** Implement `dataflows/sam_gov.py` with DARPA/DOE/NSF/DOD/NIST filters. *Done*: last-7-day quantum query returns opportunities. *SPEC*: §4.6
- [ ] **P2-T14** Implement `dataflows/uspto_client.py` (weekly poll, not real-time). *Done*: tracked patents list for 9 tickers serializes to JSON. *SPEC*: §4.7

### 2d. Memory layer

- [ ] **P2-T15** Implement `memory/vector_store.py` with ChromaDB + `sentence-transformers all-MiniLM-L6-v2` + `sim_date` filter bake-in. *Done*: `retrieve(query, sim_date=datetime(2024,6,1))` never returns docs with `published_at > 2024-06-01`. *SPEC*: §8.2
- [ ] **P2-T16** Implement `memory/knowledge_base.py` with seed markdown in `memory/kb/`. *Done*: seed files cover qubit modalities, vendor roadmaps, DARPA phases, NIST PQC; `ingest_kb()` loads all of them into vector store with `doc_type="kb"`. *SPEC*: §8.3
- [ ] **P2-T17** Implement `memory/decision_log.py` with SQLite schemas: `decisions`, `execution_log` (all 6 timestamps + 6 derived latencies), `outcomes`, `cost_log`. Indexes per §8.4. All timestamp columns are UTC ISO8601. *Done*: schema created; `write_decision(...)` and `write_execution_log(...)` round-trip correctly. *SPEC*: §8.4

### 2e. Phase 2 exit

- [ ] **P2-T18** **Exit criterion**: All 14 data sources fetch-able via unified interface, stored in vector store with metadata; guardrail test still passes. Run `pytest tests/unit/` — all green. *SPEC*: §13 Phase 2 exit

---

## Phase 3 — New agents (target: 2 weeks)

- [ ] **P3-T1** Implement `agents/analysts/quantum_tech_expert.py` (Opus 4.6 runtime, thinking_budget 16000). Validates output with `QuantumTechOutput` schema. *Done*: mocked tool test produces valid schema; live run on IONQ returns `tech_score` + all required fields. *SPEC*: §7.1, §8.5
- [ ] **P3-T2** Seed KB updates for Quantum Tech Expert: `memory/kb/qubit_modalities.md`, `memory/kb/vendor_roadmaps.md`, `memory/kb/darpa_programs.md`. *Done*: all 3 ingested into vector store; RAG retrieval on "Willow processor error correction" returns relevant content. *SPEC*: §7.1, §8.3
- [ ] **P3-T3** Implement `agents/analysts/commercialization.py` (Sonnet 4.6 + thinking_budget 8000). Validates `CommercializationOutput`. Applies the "cap at 30 if TTM revenue < $1M" rule. *Done*: run on QUBT (pre-revenue) caps score; run on IONQ (has revenue) reports full range. *SPEC*: §7.2
- [ ] **P3-T4** Implement `agents/analysts/valuation_health.py` (Sonnet 4.6 + thinking_budget 8000). Applies runway / going-concern / dilution hard rules. *Done*: synthetic 10-Q with going-concern text caps `financial_health_score ≤ 20`. *SPEC*: §7.3
- [ ] **P3-T5** Implement `agents/analysts/regulatory_policy.py` (Sonnet 4.6 + thinking_budget 4000). *Done*: run returns `policy_score` + tailwinds/headwinds list with actual DARPA/DOE events cited. *SPEC*: §7.4
- [ ] **P3-T6** Implement `agents/analysts/flow_technicals.py` (Haiku 4.5, no thinking). Uses moomoo-only for IV + volume (NOT yfinance). *Done*: `from dataflows.historical` does not appear in this file; guardrail test still passes. *SPEC*: §7.5, §4.8
- [ ] **P3-T7** Modify `agents/analysts/technical.py` — moomoo K-lines only; update prompt to quantum universe. *Done*: guardrail passes; test asserts prompt no longer references NVDA-as-example defaults. *SPEC*: §7.6
- [ ] **P3-T8** Modify `agents/analysts/news.py` — add quantum RSS as primary source; output schema includes `strategic_score`. *Done*: `NewsOutput` validates on live run. *SPEC*: §7.6, §8.5
- [ ] **P3-T9** Modify `agents/analysts/sentiment.py` — add `r/QuantumComputing`; output schema includes `macro_score`. *Done*: `SentimentOutput` validates. *SPEC*: §7.6, §8.5
- [ ] **P3-T10** Modify `agents/analysts/fundamentals.py` — extract RPO, cash runway, qubit count. *Done*: test on IONQ 10-Q returns all 3 fields. *SPEC*: §7.6
- [ ] **P3-T11** Modify `graph/trading_graph.py` — include all 9 analysts in parallel analyst phase; rename folder `agents/risk/` → `agents/risk_debate/`. *Done*: graph compiles; running on IONQ emits 9 structured outputs. *SPEC*: §7.7, §5
- [ ] **P3-T12** Update Bull/Bear researcher prompts to consume all 5 new analyst outputs in their context. *Done*: Bull/Bear output mentions at least 3 of the 5 new dimensions by name. *SPEC*: §7.7
- [ ] **P3-T13** Update Portfolio Manager prompt to accept a stage-weighted score input placeholder (actual injection happens in P4). *Done*: prompt has a `{{stage_weighted_score}}` slot. *SPEC*: §7.7, §9
- [ ] **P3-T14** Update Trader prompt with DATA SOURCE DISCIPLINE block. *Done*: prompt includes the verbatim block from SPEC §7.7. *SPEC*: §7.7, §4.8
- [ ] **P3-T15** **Exit criterion**: Running pipeline on IONQ produces JSON outputs from all 9 analyst agents, all validating against their Pydantic schemas. *SPEC*: §13 Phase 3 exit

---

## Phase 4 — Scoring & risk gate (target: 1 week)

- [ ] **P4-T1** Implement `scoring/engine.py` with `detect_stage()` + `compute_score()` per §9. Applies §4.10 confidence discount when `data_incomplete` flag present. *Done*: unit test covers 4 stage cases + `data_incomplete` path. *SPEC*: §9, §4.10
- [ ] **P4-T2** Implement `scoring/dimensions.py` with per-dimension score normalization. *Done*: out-of-range raw scores clamped to 0-100; test asserts. *SPEC*: §9.3
- [ ] **P4-T3** Implement `risk/hard_gate.py` with all hard limits: `MAX_POSITION_PCT`, `MAX_QUANTUM_EXPOSURE`, `DAILY_LOSS_HALT`, `WEEKLY_LOSS_HALT` (wire it in, don't leave dead), `MIN_CASH_PCT`, `MAX_PS_RATIO_FOR_NEW_BUY`, `MAX_IV_FOR_NEW_BUY`, `MAX_TRADES_PER_DAY_PER_TICKER` (wire it), and the `_source == "moomoo"` assertion. *Done*: `test_hard_gate.py` covers every VETO/HALT path including `stale_data_rejected_not_from_moomoo`. *SPEC*: §10
- [ ] **P4-T4** Implement `risk/kill_switch.py` with `/tmp/quantum_agent_kill` file check. *Done*: touching the file halts the next pipeline run with `SystemExit`. *SPEC*: §11.2
- [ ] **P4-T5** Integrate hard gate between Trader/Risk team output and Portfolio Manager input in `graph/trading_graph.py`. *Done*: a forced-fail proposal (10% position) is vetoed; PM never sees it. *SPEC*: §10
- [ ] **P4-T6** Wire stage-weighted score from Scoring Engine into PM input. *Done*: PM prompt sees `stage_weighted_score` value. *SPEC*: §9, §7.7
- [ ] **P4-T7** **Exit criterion**: A forced 10%-position proposal is VETO'd with `position_cap_exceeded`; a stale-data proposal is VETO'd with `stale_data_rejected_not_from_moomoo`. *SPEC*: §13 Phase 4 exit

---

## Phase 5 — Auto paper execution & latency (target: 2 weeks — revised from 1 week in Session 0b ADR)

- [ ] **P5-T1** Extend `memory/decision_log.py` with the full `execution_log` schema per §8.4 (6 timestamps + 6 derived latencies + slippage). Already partially done in P2-T17; this task completes and tests it. *Done*: `write_execution_log()` accepts all fields; NULL handling for hold + vetoed cases. *SPEC*: §8.4, §10A.3
- [ ] **P5-T2** Thread T0-T5 through LangGraph state. T0/T1 emitted by MoomooClient at data fetch; T2 set at pipeline entry; T3 set at PM output; T4/T5 set in paper executor. No node mutates existing timestamps. *Done*: integration test asserts all 6 timestamps captured for a non-hold decision on IONQ. *SPEC*: §10A.5
- [ ] **P5-T3** Implement `execution/paper_executor.py` per §10A.4. Handles hold (skip), timeout (log as `status="timeout"`), reject, partial-fill. *Done*: `test_paper_executor.py` covers all 5 status branches with mocked MoomooClient. *SPEC*: §10A.4
- [ ] **P5-T4** Wire execution step into `graph/trading_graph.py` after PM, branching on `ENVIRONMENT` + `action != "hold"`. *Done*: running on IONQ in `ENVIRONMENT=paper` submits a SIMULATE order to moomoo and writes a fully-populated `execution_log` row. *SPEC*: §10A.5
- [ ] **P5-T5** Implement `orchestration/latency_report.py` generating per-ticker table + rolling p50/p95 + red-zone breach list. *Done*: running `python -m orchestration.latency_report` produces a human-readable report from the last 7 days of `execution_log`. *SPEC*: §10A.7
- [ ] **P5-T6** Implement `tests/integration/test_latency_budget.py` + `tests/integration/test_hold_decision_logging.py`. *Done*: latency test passes (does not run in regular CI — marked `@nightly`); hold-decision test confirms T0-T3 captured and T4/T5 null. *SPEC*: §10A.8, §14
- [ ] **P5-T7** **Exit criterion**: Running pipeline on IONQ submits a paper order to moomoo SIMULATE and writes `execution_log` row with all 6 timestamps + 6 derived latencies; daily latency report generates successfully. *SPEC*: §13 Phase 5 exit

---

## Phase 6 — Orchestration (target: 1 week)

- [ ] **P6-T1** Implement `orchestration/scheduler.py` using system cron (launchd on macOS) — NOT APScheduler (ADR in SESSION_PLAN.md). *Done*: cron entry fires `python -m tradingagents.daily_cycle` at 8:00 ET; entry registered via `launchctl load`. *SPEC*: §11.1
- [ ] **P6-T2** Implement `orchestration/cost_tracker.py` with SQLite `cost_log` + per-cycle circuit breaker in addition to per-day. *Done*: pipeline halts mid-cycle when `DAILY_COST_HARD_STOP_USD` hit; per-cycle estimate exceeding `PER_CYCLE_HARD_STOP_USD` halts before PM call. *SPEC*: §11.3
- [ ] **P6-T3** Implement `orchestration/alerts.py` via Gmail MCP. *Done*: `alert_decision`, `alert_error`, `alert_cost` all deliver to configured Gmail; alert_decision includes latency summary from P5-T5. *SPEC*: §11.4
- [ ] **P6-T4** Implement `orchestration/monitor.py` for log aggregation. *Done*: single-command health dump shows latest decision, latest cost, any kill-switch state, last 5 alerts. *SPEC*: §11
- [ ] **P6-T5** Configure tool permissions pre-approval (`.claude/settings.json`) for unattended runs. *Done*: scheduled run does not prompt for tool approvals. *SPEC*: §18
- [ ] **P6-T6** Hook latency report (P5-T5) into daily Gmail alert. *Done*: daily email contains latency section. *SPEC*: §10A.7, §11.4
- [ ] **P6-T7** **Exit criterion**: Daily scheduled run at 8:00 ET fires; decisions appear in Gmail; cost tracked; latency report attached. *SPEC*: §13 Phase 6 exit

---

## Phase 7 — Backtest (target: 2-4 weeks) — **[DEFERRED 2026-04-16]**

> 用户决定先不做回测。本阶段所有任务暂缓，保留作 future roadmap。启动前需重评估 CLI 订阅的回测吞吐 / 是否临时开 API 账单。

- [ ] **P7-T1** [DEFERRED] Implement `backtest/runner.py` using `vectorbt` (ADR: vectorbt over backtrader). Threads `sim_date` through every RAG query + every agent call. *Done*: running on IONQ Jan 2024 → Apr 2025 completes; decisions written to a separate `backtest_decisions` table. *SPEC*: §13 Phase 7
- [ ] **P7-T2** Acquire historical data: at least Jan 2024 → present via moomoo K-lines (preferred) or yfinance fallback. *Done*: OHLCV files cached under `data/historical/`. *SPEC*: §13 Phase 7
- [ ] **P7-T3** Implement `tests/backtest/test_no_lookahead.py` — asserts vector store retrieval at `sim_date=2024-06-01` returns no docs with `published_at > 2024-06-01`. *Done*: passes. *SPEC*: §8.2, §14
- [ ] **P7-T4** Implement `tests/backtest/test_reproducibility.py` — same inputs + `temperature=0` → same outputs. *Done*: two successive backtests on the same date produce identical decisions. *SPEC*: §14, §15
- [ ] **P7-T5** Compute standard metrics: Cumulative Return, Annualized Return, Sharpe, Max DD, Win Rate, Avg Hold Period. Compare vs. Buy & Hold, MACD, SMA. *Done*: metrics table + baseline comparison exported to `results/backtest_v1.md`. *SPEC*: §13 Phase 7
- [ ] **P7-T6** Compare backtest slippage assumption against actual Phase 5 paper slippage log. *Done*: if assumption drift > 30%, flag for prompt/weight revision. *SPEC*: §13 Phase 7
- [ ] **P7-T7** **Exit criterion**: 12-month backtest complete; Sharpe > 1.5 AND Max DD < 25% to proceed. If not met: iterate prompts/weights before Phase 8. *SPEC*: §13 Phase 7 exit, §16

---

## Phase 8 — Live paper validation (target: 30 days) — **[DEFERRED 2026-04-16]**

> 依赖 Phase 7 完成。保留为 future roadmap。


- [ ] **P8-T1** Paper pipeline runs daily for 30 trading days without manual intervention. *Done*: 30 rows in `execution_log` with non-null T5 for non-hold decisions (excluding halt / kill-switch days). *SPEC*: §13 Phase 8
- [ ] **P8-T2** Daily Gmail report with positions, P&L, agent rationale, latency stats. *Done*: 30 emails received. *SPEC*: §13 Phase 8, §11.4
- [ ] **P8-T3** Weekly vetoed-proposal review. *Done*: 4 weekly review entries in `results/phase8_review.md`. *SPEC*: §13 Phase 8
- [ ] **P8-T4** Weekly slippage trend review. *Done*: slippage p50/p95 tracked; drift > 30% vs. Phase 5 baseline flagged. *SPEC*: §13 Phase 8
- [ ] **P8-T5** Weekly latency trend review. *Done*: median `total_market_to_fill_ms` stable within ±20% of Phase 5 baseline. *SPEC*: §10A.6, §13 Phase 8
- [ ] **P8-T6** Tune prompts + stage weights based on paper performance. *Done*: changelog in `results/phase8_tuning.md`. *SPEC*: §13 Phase 8
- [ ] **P8-T7** **Exit criterion**: 30-day paper Sharpe > 1.0 AND Max DD < 15% AND median latency stable. User approval required to proceed. *SPEC*: §13 Phase 8 exit, §16

---

## Phase 9 — Small live (target: ongoing) — **[DEFERRED 2026-04-16]**

> 真钱上线，依赖 Phase 7/8。保留为 future roadmap。


- [ ] **P9-T1** Implement `execution/live_executor.py` (same interface as paper_executor, `trd_env="REAL"`). Guardrail: raises unless `ENVIRONMENT=live` AND user approval confirmed. *Done*: unit test with `ENVIRONMENT=paper` raises; with `live` executes. *SPEC*: §10A.5, §13 Phase 9
- [ ] **P9-T2** Switch `.env` `ENVIRONMENT=live`. Cap total quantum exposure at 5% (override `MAX_QUANTUM_EXPOSURE = 0.05` via config). *Done*: `.env` updated; hard gate uses 5% cap. *SPEC*: §13 Phase 9
- [ ] **P9-T3** Run at small size for 3 months. *Done*: 60 trading days in `execution_log` with `environment="live"`. *SPEC*: §13 Phase 9
- [ ] **P9-T4** Monthly review; incrementally raise caps only if performance validates. Never exceed 15% total quantum exposure. *Done*: review entries in `results/phase9_monthly/`. *SPEC*: §13 Phase 9 exit

---

## Meta

- Total tasks: 74（其中 Phase 7-9 共 17 task [DEFERRED 2026-04-16]；active = 57）
- Guardrail test (`test_no_yfinance_on_hot_path.py`, P2-T5) must pass on every commit from Phase 2 onward.
- Latency regression test (P5-T6 `test_latency_budget.py`) runs nightly only; marked `@pytest.mark.nightly`.
- Every agent modification in Phase 3 must be accompanied by a schema fixture update in `tests/unit/test_schemas.py`.
- Every Phase's exit criterion is a gate — do not start Phase N+1 before the prior exit is green.
