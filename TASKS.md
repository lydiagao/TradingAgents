# TASKS — Quantum Trading Agent

> 本文件是所有 session 任务的**单一事实来源**（配合 `PROGRESS.md` 的正式定义 + `SESSION_PLAN.md` 的分配）。
> 每完成一个任务立刻更新此文件。规则见 `CLAUDE.md`。

---

## 进度摘要

| 字段 | 值 |
|---|---|
| **总任务数** | 74 |
| **已完成** | 0 |
| **完成率** | 0.0 % |
| **当前 Session** | S01 — Scaffold & model config（进行中） |
| **当前 Phase** | Phase 1 |
| **最近更新** | 2026-04-16 UTC |
| **最近 commit** | `c06a59a` (add CLAUDE.md + TASKS.md) |

### 状态图例

| 标记 | 含义 |
|---|---|
| `[ ]` | 待处理 (Pending) |
| `[~]` | 进行中 (In Progress) |
| `[x]` | 已完成 (Completed) |
| `[!]` | 阻塞 (Blocked — 等用户 / 外部资源) |

---

## Session 01 — Scaffold & model config（进行中）

**Phase**: 1 · **Model**: Sonnet 4.6 medium thinking · **SPEC 参考**: §2, §3, §6, §12, §13 Phase 1

- [!] **P1-T1** Fork `TauricResearch/TradingAgents` on GitHub — *阻塞：本机无 `gh` CLI，等用户选择（a）浏览器 fork / (b) 安装 gh / (c) 跳过先 clone upstream*
- [!] **P1-T2** Clone fork locally, create `quantum-fork` branch — *阻塞：依赖 P1-T1 + 目录布局决策*
- [!] **P1-T3** 创建 Python 3.13 环境 — *用 `uv venv --python 3.13 .venv` 替代 conda（SPEC §2 允许 conda 或 uv），等用户确认替代方案*
- [ ] **P1-T4** `pip install -r requirements.txt` + SPEC §2 的 19 个依赖
- [!] **P1-T5** Copy `.env.example` → `.env`，填入 `ANTHROPIC_API_KEY` — *阻塞：等用户提供 key 或确认 key 所在位置*
- [ ] **P1-T6** 创建 `tradingagents/config/model_config.py`（AGENT_MODEL_MAP + get_model_config() + build_thinking_param()）
- [ ] **P1-T7** 创建 `tradingagents/config/universe.py`（QUANTUM_PURE_PLAYS + QUANTUM_EXPOSURE + UNIVERSE）
- [ ] **P1-T8** 创建 `tradingagents/config/ciks.json`（9 个 ticker 的 CIK 映射）
- [ ] **P1-T9** 修改 `tradingagents/graph/setup.py`，按 agent 名传入 model + thinking_budget
- [ ] **P1-T10** 创建 `tests/unit/test_model_config.py`（覆盖 16 个 agent key）
- [!] **P1-T11** Baseline 跑 `python main.py NVDA 2026-04-15`，cost ≈ $0.50 — *依赖 P1-T1 到 P1-T10 全部 green + 用户授权真实 API 消费*

**Session 01 Exit**: P1-T11 绿灯 → `feat(P1): scaffold + per-agent model config` → 切换到 Session 02

---

## Session 02 — MoomooClient + §4.8 guardrail（KEYSTONE · 待开始）

**Phase**: 2a · **Model**: Sonnet 4.6 high (8000) · **SPEC**: §4.8.1-4.8.3, §10A.2, §14 · **Risk**: HIGH

- [ ] **P2-T1** 实现 `tradingagents/dataflows/moomoo_client.py`（§4.8.3 全接口 + T0/T1 打标）
- [ ] **P2-T2** 实现 `tradingagents/dataflows/__init__.py`（lazy `get_client()`）
- [ ] **P2-T3** 实现 `tradingagents/dataflows/historical.py`（唯一 yfinance 入口）
- [ ] **P2-T4** 实现 `tests/unit/test_moomoo_source_tag.py`（每个方法返回字典必带 `_source == "moomoo"`）
- [ ] **P2-T5** 实现 `tests/unit/test_no_yfinance_on_hot_path.py`（守卫测试，从此每次 commit 必须通过）

---

## Session 03 — Retry helper + Pydantic schemas（待开始）

**Phase**: 2b · **SPEC**: §4.10, §8.5

- [ ] **P2-T6** `dataflows/retry.py` 的 `FetchResult` + `fetch_with_policy(source, fetcher, tier)`
- [ ] **P2-T7** `memory/schemas.py`（9 个 agent 的 Pydantic 模型，含 News `strategic_score` + Sentiment `macro_score`）

---

## Session 04 — Chatter 数据源（待开始 · 可与 S05 并行）

**Phase**: 2c · **SPEC**: §4.1, §4.2, §4.4, §4.5, §4.10, §8.1

- [ ] **P2-T8** `dataflows/rss_quantum.py`（4 个量子 RSS feed）
- [ ] **P2-T9** `dataflows/arxiv_client.py`
- [ ] **P2-T10** `dataflows/newsapi_client.py`（100 req/day 预算 + cache）
- [ ] **P2-T11** `dataflows/reddit_client.py`（PRAW OAuth，无匿名回退）

---

## Session 05 — Regulatory 数据源（待开始 · 可与 S04 并行）

**Phase**: 2c · **SPEC**: §4.3, §4.6, §4.7, §4.9, §4.10

- [ ] **P2-T12** `dataflows/sec_edgar.py`（10-Q / 10-K / 13F + CIK lookup + User-Agent）
- [ ] **P2-T13** `dataflows/sam_gov.py`（DARPA/DOE/NSF/DOD/NIST filter）
- [ ] **P2-T14** `dataflows/uspto_client.py`（weekly poll）

---

## Session 06 — Memory layer（待开始）

**Phase**: 2d · **SPEC**: §8.2, §8.3, §8.4 · **Risk**: MEDIUM（sim_date filter 必须正确）

- [ ] **P2-T15** `memory/vector_store.py`（ChromaDB + all-MiniLM-L6-v2 + `sim_date` filter）
- [ ] **P2-T16** `memory/knowledge_base.py` + 4 个 KB seed（qubit_modalities, vendor_roadmaps, darpa_programs, nist_pqc_timeline）
- [ ] **P2-T17** `memory/decision_log.py`（decisions / execution_log / outcomes / cost_log，UTC ISO8601）
- [ ] **P2-T18** Phase 2 Exit：14 个数据源全通；`pytest tests/unit/` 全绿；`git tag phase-2-complete`

---

## Session 07 — Quantum Tech Expert agent（待开始 · Opus 4.6 high）

**Phase**: 3 · **SPEC**: §7.1, §8.3, §8.5, §4.8 · **Risk**: HIGH

- [ ] **P3-T1** `agents/analysts/quantum_tech_expert.py`（runtime Opus 4.6, thinking 16000）
- [ ] **P3-T2** Extend KB: qubit_modalities.md / vendor_roadmaps.md / darpa_programs.md

---

## Session 08 — Commercialization Analyst（待开始 · Opus 4.6 high）

**Phase**: 3 · **SPEC**: §7.2, §4.3, §8.5

- [ ] **P3-T3** `agents/analysts/commercialization.py`（TTM revenue < $1M → 封顶 30；press-only 折 70%）

---

## Session 09 — Valuation & Financial Health（待开始 · Opus 4.6 high）

**Phase**: 3 · **SPEC**: §7.3, §4.3, §8.5

- [ ] **P3-T4** `agents/analysts/valuation_health.py`（runway < 4Q → ≤40；going-concern → ≤20；P/S > 5× + runway < 6 → bubble_risk）

---

## Session 10 — Regulatory Policy + Flow & Technicals（待开始）

**Phase**: 3 · **SPEC**: §7.4, §7.5, §4.8

- [ ] **P3-T5** `agents/analysts/regulatory_policy.py`
- [ ] **P3-T6** `agents/analysts/flow_technicals.py`（IV 必须来自 moomoo `get_live_options_chain`，禁用 yfinance）

---

## Session 11 — 传统 4 agent 改造（待开始）

**Phase**: 3 · **SPEC**: §7.6, §8.5

- [ ] **P3-T7** `agents/analysts/technical.py`（仅 moomoo K-lines）
- [ ] **P3-T8** `agents/analysts/news.py`（量子 RSS 主源 + `strategic_score`）
- [ ] **P3-T9** `agents/analysts/sentiment.py`（`r/QuantumComputing` + `macro_score`）
- [ ] **P3-T10** `agents/analysts/fundamentals.py`（RPO + cash runway + qubit count）

---

## Session 12 — Graph 接线 + Bull/Bear/Trader/PM（待开始）

**Phase**: 3 tail · **SPEC**: §7.7, §5, §4.8

- [ ] **P3-T11** `graph/trading_graph.py` 9-analyst 并行；`agents/risk/` → `agents/risk_debate/`
- [ ] **P3-T12** Bull/Bear 更新：引用至少 3 个新维度
- [ ] **P3-T13** Portfolio Manager prompt 加入 `{{stage_weighted_score}}` slot
- [ ] **P3-T14** Trader prompt 追加 DATA SOURCE DISCIPLINE block（§7.7 verbatim）
- [ ] **P3-T15** Phase 3 Exit：IONQ 跑完 9 个 analyst，全部 Pydantic 校验通过；`git tag phase-3-complete`

---

## Session 13 — Scoring engine（待开始）

**Phase**: 4 · **SPEC**: §9, §4.10

- [ ] **P4-T1** `scoring/engine.py`（4 stage 检测 + data_incomplete × 0.5 权重）
- [ ] **P4-T2** `scoring/dimensions.py`（raw score clamp 到 0-100）

---

## Session 14 — Hard risk gate + kill switch（待开始）

**Phase**: 4 · **SPEC**: §10, §4.8.3, §11.2, §4.10

- [ ] **P4-T3** `risk/hard_gate.py`（含 WEEKLY_LOSS_HALT + MAX_TRADES_PER_DAY_PER_TICKER，**wire 进去**不要留 dead code）
- [ ] **P4-T4** `risk/kill_switch.py`（`/tmp/quantum_agent_kill` 文件检测）
- [ ] **P4-T5** `graph/trading_graph.py` 里接入 gate（Trader/Risk 之后，PM 之前）
- [ ] **P4-T6** Scoring Engine 的 stage_weighted_score 接入 PM 输入
- [ ] **P4-T7** Phase 4 Exit：10% 仓位 proposal VETO；stale-data proposal VETO；`git tag phase-4-complete`

---

## Session 15 — Paper executor + T0-T5 state threading（待开始 · Opus 4.6 最难接线）

**Phase**: 5 · **SPEC**: §10A, §8.4, §4.8

- [ ] **P5-T1** 扩展 `memory/decision_log.py` 的 `execution_log`（6 时间戳 + 6 派生延迟 + slippage）
- [ ] **P5-T2** T0-T5 穿过 LangGraph state（任何节点不得改写已存在的时间戳）
- [ ] **P5-T3** `execution/paper_executor.py`（hold / filled / partial / rejected / timeout）
- [ ] **P5-T4** `graph/trading_graph.py` 在 PM 之后接入 executor（按 `ENVIRONMENT` 分支）
- [ ] **P5-T5** `orchestration/latency_report.py`（p50/p95 + red-zone breach）
- [ ] **P5-T6** `tests/integration/test_latency_budget.py`（@nightly）+ `test_hold_decision_logging.py`
- [ ] **P5-T7** Phase 5 Exit：IONQ paper order 写入 execution_log（6 时间戳 + 6 延迟 全齐）；`git tag phase-5-complete`

---

## Session 16 — Orchestration（待开始）

**Phase**: 6 · **SPEC**: §11, §10A.7

- [ ] **P6-T1** `orchestration/scheduler.py`（launchd 封装，**不用 APScheduler**）
- [ ] **P6-T2** `orchestration/cost_tracker.py`（per-day + per-cycle 双熔断）
- [ ] **P6-T3** `orchestration/alerts.py`（Gmail MCP）
- [ ] **P6-T4** `orchestration/monitor.py`（日志聚合）
- [ ] **P6-T5** `.claude/settings.json` 工具预授权（unattended 运行）
- [ ] **P6-T6** 延迟报告并入每日 Gmail
- [ ] **P6-T7** Phase 6 Exit：每日 8:00 ET launchd 触发；邮件到；`git tag phase-6-complete`

---

## Session 17 — Backtest 框架 + sim_date 强制（待开始 · Opus 4.6）

**Phase**: 7 · **SPEC**: §13 Phase 7, §8.2, §14

- [ ] **P7-T1** `backtest/runner.py`（`vectorbt`，sim_date 穿透每个 agent call + RAG query）
- [ ] **P7-T2** 缓存 Jan 2024 → present OHLCV（moomoo 优先，yfinance 回退）
- [ ] **P7-T3** `tests/backtest/test_no_lookahead.py`（CRITICAL）
- [ ] **P7-T4** `tests/backtest/test_reproducibility.py`（temperature=0 → 相同结果）

---

## Session 18 — Backtest 运行 + 指标 + 调参（待开始）

**Phase**: 7 · **SPEC**: §13 Phase 7, §16

- [ ] **P7-T5** 计算 Sharpe / MDD / Win Rate / Avg Hold；对比 Buy&Hold / MACD / SMA
- [ ] **P7-T6** 对比 backtest slippage 假设 vs. Phase 5 实际（drift > 30% 触发调参）
- [ ] **P7-T7** Phase 7 Exit：Sharpe > 1.5 AND MDD < 25%；`git tag phase-7-complete`

---

## Session 19 — 30 天 paper validation（待开始）

**Phase**: 8 · **SPEC**: §13 Phase 8, §16, §15

- [ ] **P8-T1** 连续 30 交易日无人工干预
- [ ] **P8-T2** 每日 Gmail 报告
- [ ] **P8-T3** 每周 veto proposal 复盘（4 次）
- [ ] **P8-T4** 每周 slippage 趋势审阅
- [ ] **P8-T5** 每周延迟趋势审阅
- [ ] **P8-T6** 根据 paper 表现微调 prompt / 权重
- [ ] **P8-T7** Phase 8 Exit：30-day Sharpe > 1.0 AND MDD < 15% AND 中位延迟稳定；用户批准进 Phase 9

---

## Session 20 — Live executor + Phase 9 go-live（待开始）

**Phase**: 9 · **SPEC**: §13 Phase 9, §10A.5

- [ ] **P9-T1** `execution/live_executor.py`（`trd_env="REAL"`；ENVIRONMENT != live 时抛错）
- [ ] **P9-T2** `.env` 切 `ENVIRONMENT=live`；`MAX_QUANTUM_EXPOSURE = 0.05`
- [ ] **P9-T3** 小仓位跑 3 个月（60 交易日 `environment="live"`）
- [ ] **P9-T4** 每月复盘，达标才逐步加仓；永不超过 15%

---

## 变更记录

| 日期 | 事件 | 影响 |
|---|---|---|
| 2026-04-16 | 创建 `TASKS.md` + `CLAUDE.md`（Session 01 启动） | 启动任务追踪 |

---

## Session 交接

### Session 01 开始（2026-04-16）

**本 session 起始状态**：
- 无任何 P1 任务已完成
- `TradingAgents` 尚未 fork / clone
- 本机无 `gh` / `conda`，仅有 `uv 0.11.2` + Python 3.14.2

**第一个动作**：等待用户回复关于 4 个 blocker 的决策：
1. GitHub fork 方式（浏览器 / 安装 gh / 先跳过）
2. conda → uv 替代是否 OK
3. TradingAgents 仓库布局（sibling / subdir / merge）
4. `ANTHROPIC_API_KEY` 的位置 / 提供方式

**拿到回复后的下一步**：执行 P1-T1（fork）→ P1-T2（clone + 建 `quantum-fork` 分支）。

---
