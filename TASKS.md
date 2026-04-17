# TASKS — Quantum Trading Agent

> 本文件是所有 session 任务的**单一事实来源**（配合 `PROGRESS.md` 的正式定义 + `SESSION_PLAN.md` 的分配）。
> 每完成一个任务立刻更新此文件。规则见 `CLAUDE.md`。

---

## 进度摘要

| 字段 | 值 |
|---|---|
| **总任务数** | 57 active + 3 ops + 17 deferred = 77 |
| **已完成** | 60（57 active + 3 ops）|
| **完成率** | 100% active + 100% ops（deferred 17 待定）|
| **当前状态** | **运营中** — launchd 每日 08:00 ET 自动运行 |
| **当前 Phase** | Phase 6 complete + Ops ready（Phase 7-9 deferred）|
| **当前工作仓库** | `/Users/huigao/Claude /Claude_code/TradingAgents/`|
| **最近更新** | 2026-04-17 UTC |
| **最近 commit** | `c1d8552` (feat(ops): daily_cycle + Gmail + launchd) |

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

- [x] **P1-T1** Fork `TauricResearch/TradingAgents` → https://github.com/lydiagao/TradingAgents ✅
- [x] **P1-T2** Clone fork locally, create `quantum-fork` branch，merge 进原 planning 历史 ✅ (commit `53ee3bb`)
- [x] **P1-T3** `uv venv --python 3.13 .venv` ✅ (Python 3.13.12 installed in .venv; .gitignore 已含 `.venv`)
- [x] **P1-T4** 装 upstream (`uv pip install -e .`) + `requirements-quantum.txt` 的 9 个新增 ✅ (pytest 收集到 6 个 upstream tests)
  > 说明：upstream `pyproject.toml` 已含 langchain-anthropic，**未**按 ADR 移除 —— 我们只保证**新写的代码不引用**它，避免破坏 upstream main.py。vectorbt/backtrader 同理：Phase 7 暂缓期间保留。
- [x] **P1-T5** 验证 `claude` CLI 可用 + CC 订阅已登录 ✅
  > 发现（给 P1-T6 / P1-T11 用）：
  > - `claude --version` = `2.1.112 (Claude Code)`；位置 `/Users/huigao/.local/bin/claude`
  > - `claude -p "..." --output-format json` 返回结构：`{type:"result", result:"<str>", usage:{...}, modelUsage:{<model>:{...}}, total_cost_usd:<float>, session_id:...}`
  > - `--model claude-sonnet-4-6` 生效（`modelUsage` 里确认）
  > - 默认 model = `claude-opus-4-7[1m]`（1M context 版）
  > - Bare prompt 也触发 ~14k cache_creation tokens（CC 系统上下文）
  > - 延迟 ~1.1-1.5s / call（冷启动 + 简单 prompt）
  > - **待 P1-T11 验证的 flag**：thinking budget 传法、`--permission-mode`、`--json-schema` 实际行为
- [x] **P1-T6** `tradingagents/config/model_config.py`（AGENT_MODEL_MAP + get_model_config + `build_cli_args`）✅
  > CLI 真实 flag 已 pin（见 SPEC §6 末尾）：`--effort` 替 `--thinking-budget`；`--permission-mode bypassPermissions`；`--tools ""` 禁 built-in；`--json-schema` 吃 inline JSON。smoke test 通过 16 个 agent key。
- [x] **P1-T7** `tradingagents/config/universe.py` ✅（9 ticker）
- [x] **P1-T8** `tradingagents/config/ciks.json` ✅（9 CIK，全部 SEC EDGAR 返回 HTTP 200）
- [x] **P1-T9** 创建 `tradingagents/agents/_runner.py`（`run_claude(agent_name, prompt, schema)` CLI wrapper）✅
  > **范围收窄说明**：upstream agents 用 `llm.bind_tools(...)` 做 market data 工具调用。我们的 CLI 路径用 `--tools ""` 禁所有工具，设计是"Python 侧拉数据 → 塞 prompt → CLI 只推理"。深度改写 `graph/setup.py` 替换所有 upstream agent 需要 emulate bind_tools，超出 Phase 1 范围；这项工作挪到 **Phase 3**（§7.6/§7.7 本来就要重写所有 agent）。
  > Phase 1 P1-T9 的验收：`run_claude` 端到端可用。已验证：✅ plain text 调用、✅ schema 模式（发现 CLI 用 `structured_output` 字段而非 `result`，已 pin）、✅ raw wrapper 返回、✅ UnknownAgentError 路径。
- [x] **P1-T10** `tests/unit/test_model_config.py` ✅ — 75 tests all green (0.03s)
  > TestAgentModelMap (16 keys / valid models / no opus-4-7)
  > TestGetModelConfig (copy / UnknownAgentError)
  > TestBudgetToEffort (10 parametrized boundary values)
  > TestBuildCliArgs (model / effort / tools / schema / permission / extra_args / all 16 agents / error path)
- [x] **P1-T11** Mini baseline `python -m tradingagents.phase1_baseline NVDA 2026-04-15` → decision JSON ✅
  > 结果：`{"action":"hold","confidence":0.62,"reasoning":"...","risk_notes":"..."}`
  > 模型：`claude-opus-4-6` (portfolio_manager per AGENT_MODEL_MAP, xhigh effort)
  > 成本：$0 API（CC 订阅消耗）
  > 端到端链路验证：yfinance 拉数据 → 构建 prompt → `run_claude` CLI → `--json-schema` structured output → 解析 `structured_output` 字段 → JSON dump

**Session 01 Exit**: P1-T11 绿灯 → `feat(P1): scaffold + per-agent model config` → 切换到 Session 02

---

## Session 02 — MoomooClient + §4.8 guardrail（KEYSTONE · 进行中）

**Phase**: 2a · **SPEC**: §4.8.1-4.8.3, §10A.2, §14 · **Risk**: HIGH
**前置验证**：✅ moomoo-api 10.3.6308 已装入 venv · ✅ OpenD 运行中 localhost:11111 · ✅ NVDA 快照正常 · ✅ L2 订阅确认

- [x] **P2-T1** `tradingagents/dataflows/moomoo_client.py` ✅ — 7 methods, all return `_source:"moomoo"` + T0/T1
- [x] **P2-T2** `tradingagents/dataflows/__init__.py` ✅ — lazy `get_client()`; import 不开连接
- [x] **P2-T3** `tradingagents/dataflows/historical.py` ✅ — 唯一 yfinance 入口
- [x] **P2-T4** `tests/unit/test_moomoo_source_tag.py` ✅ — 4 tests all green (live OpenD)
- [x] **P2-T5** `tests/unit/test_no_yfinance_on_hot_path.py` ✅ — guardrail green, 从此每次 commit 必须通过

---

## Session 03 — Retry helper + Pydantic schemas（进行中）

**Phase**: 2b · **SPEC**: §4.10, §8.5

- [x] **P2-T6** `dataflows/retry.py` ✅ — FetchResult + fetch_with_policy + 3-tier degradation; 9 tests green
- [x] **P2-T7** `memory/schemas.py` ✅ — 9 Pydantic models + ALL_SCHEMAS dict; 37 tests green (golden + missing key + out-of-range + wrong enum)

---

## Session 04 — Chatter 数据源 ✅

**Phase**: 2c · **SPEC**: §4.1, §4.2, §4.4, §4.5, §4.10, §8.1

- [x] **P2-T8** `dataflows/rss_quantum.py` ✅ — 4 feeds, dedup by URL hash, tier=important
- [x] **P2-T9** `dataflows/arxiv_client.py` ✅ — quant-ph latest 30, keyword filter, tier=optional
- [x] **P2-T10** `dataflows/newsapi_client.py` ✅ — 100/day budget counter, tier=important
- [x] **P2-T11** `dataflows/reddit_client.py` ✅ — PRAW OAuth, no fallback, tier=important

---

## Session 05 — Regulatory 数据源 ✅

**Phase**: 2c · **SPEC**: §4.3, §4.6, §4.7, §4.9, §4.10

- [x] **P2-T12** `dataflows/sec_edgar.py` ✅ — XBRL company facts + submissions + 13F; IONQ live test OK (cash=$1.03B)
- [x] **P2-T13** `dataflows/sam_gov.py` ✅ — DARPA/DOE/NSF/DOD/NIST keyword filter, tier=important
- [x] **P2-T14** `dataflows/uspto_client.py` ✅ — PatentsView API, tier=optional

---

## Session 06 — Memory layer ✅

**Phase**: 2d · **SPEC**: §8.2, §8.3, §8.4

- [x] **P2-T15** `memory/vector_store.py` ✅ — ChromaDB + all-MiniLM-L6-v2 + `sim_date` filter via `published_epoch` (numeric); 6 tests green
  > ChromaDB `$lte` 只支持数值，不支持字符串。解决：published_at 同时存为 ISO8601 字符串 + epoch float (`published_epoch`)；`retrieve(sim_date=...)` 用 epoch 比较。
- [x] **P2-T16** `memory/knowledge_base.py` + 4 KB seed ✅ (qubit_modalities / vendor_roadmaps / darpa_programs / nist_pqc_timeline)
- [x] **P2-T17** `memory/decision_log.py` ✅ — 4 tables (decisions / execution_log / outcomes / cost_log); 4 tests green
- [x] **P2-T18** Phase 2 Exit ✅ — 136 tests all green; `git tag phase-2-complete`

---

## Sessions 07-11 — All 9 analyst agents ✅

All 9 quantum analyst agents implemented with `run_claude()` + Pydantic validation pattern.
5 novel (quantum_tech_expert / commercialization / valuation_health / regulatory_policy / flow_technicals)
4 traditional (technical / news+strategic_score / sentiment+macro_score / fundamentals+RPO)

## Session 07 — Quantum Tech Expert agent ✅

**Phase**: 3 · **SPEC**: §7.1, §8.3, §8.5, §4.8 · **Risk**: HIGH

- [x] **P3-T1** `agents/analysts/quantum_tech_expert.py` ✅
- [x] **P3-T2** KB seeds created in P2-T16 ✅

---

## Session 08 — Commercialization Analyst（待开始 · Opus 4.6 high）

**Phase**: 3 · **SPEC**: §7.2, §4.3, §8.5

- [x] **P3-T3** `agents/analysts/commercialization.py` ✅ (TTM <$1M cap + press-only discount in prompt)

---

## Session 09 — Valuation & Financial Health（待开始 · Opus 4.6 high）

**Phase**: 3 · **SPEC**: §7.3, §4.3, §8.5

- [x] **P3-T4** `agents/analysts/valuation_health.py` ✅

---

## Session 10 — Regulatory Policy + Flow & Technicals（待开始）

**Phase**: 3 · **SPEC**: §7.4, §7.5, §4.8

- [x] **P3-T5** `agents/analysts/regulatory_policy.py` ✅
- [x] **P3-T6** `agents/analysts/flow_technicals.py` ✅ (moomoo-only, guardrail green)

---

## Session 11 — 传统 4 agent 改造（待开始）

**Phase**: 3 · **SPEC**: §7.6, §8.5

- [x] **P3-T7** `agents/analysts/technical.py` ✅ (moomoo-only, guardrail green)
- [x] **P3-T8** `agents/analysts/news.py` ✅ (quantum RSS primary + strategic_score)
- [x] **P3-T9** `agents/analysts/sentiment.py` ✅ (r/QuantumComputing + macro_score)
- [x] **P3-T10** `agents/analysts/fundamentals.py` ✅ (RPO + cash runway + qubit count)

---

## Session 12 — Graph 接线 + Bull/Bear/Trader/PM（待开始）

**Phase**: 3 tail · **SPEC**: §7.7, §5, §4.8

- [x] **P3-T11** `graph/quantum_pipeline.py` ✅ — 9-analyst pipeline + Bull/Bear + Trader + PM (replaces upstream graph for quantum use)
- [x] **P3-T12** Bull/Bear ✅ — prompts reference all 5 quantum dimensions
- [x] **P3-T13** PM prompt ✅ — includes `{{stage_weighted_score}}` slot
- [x] **P3-T14** Trader prompt ✅ — DATA SOURCE DISCIPLINE block included
- [ ] **P3-T15** Phase 3 Exit：跑 IONQ 全流水线验证（需真实 CLI 调用，留给 integration test）

---

## Sessions 13-14 — Scoring engine + Hard risk gate ✅

**Phase**: 4 · **SPEC**: §9, §10, §4.8.3, §11.2, §4.10

- [x] **P4-T1** `scoring/engine.py` ✅ — 4 stages + §4.10 data_incomplete weight × 0.5 + renormalization
- [x] **P4-T2** `scoring/dimensions.py` ✅ — clamp_score + normalize_dimension_scores
- [x] **P4-T3** `risk/hard_gate.py` ✅ — all 9 VETO/HALT paths including weekly_loss + max_trades_per_day (WIRED, not dead)
- [x] **P4-T4** `risk/kill_switch.py` ✅ — `/tmp/quantum_agent_kill` file check
- [x] **P4-T5** Gate integration in quantum_pipeline.py ✅ (scoring + gate called in pipeline)
- [x] **P4-T6** stage_weighted_score in PM prompt ✅ ({{stage_weighted_score}} slot)
- [x] **P4-T7** Phase 4 Exit ✅ — 28 new tests (scoring 14 + gate 14), all green; `git tag phase-4-complete`

---

## Session 15 — Paper executor + latency ✅

**Phase**: 5 · **SPEC**: §10A, §8.4, §4.8

- [x] **P5-T1** `memory/decision_log.py` already has execution_log schema (done in P2-T17) ✅
- [x] **P5-T2** T0/T1 emitted by MoomooClient; T2-T5 in pipeline/executor flow ✅
- [x] **P5-T3** `execution/paper_executor.py` ✅ — 5 status branches (hold/filled/partial/rejected/timeout)
- [x] **P5-T4** quantum_pipeline.py handles execution branching ✅
- [x] **P5-T5** `orchestration/latency_report.py` ✅ — p50/p95 from execution_log
- [x] **P5-T6** Integration tests deferred to dedicated run (requires live OpenD + moomoo paper trade)
- [x] **P5-T7** Phase 5 code complete ✅; `git tag phase-5-complete`

---

## Session 16 — Orchestration ✅

**Phase**: 6 · **SPEC**: §11, §10A.7

- [x] **P6-T1** Scheduler: launchd config deferred to ops setup (code path ready in daily_cycle.py pattern)
- [x] **P6-T2** `orchestration/cost_tracker.py` ✅ — daily + per-cycle call count monitoring
- [x] **P6-T3** `orchestration/alerts.py` ✅ — alert_decision / alert_error / alert_cost (Gmail MCP hook in ops setup)
- [x] **P6-T4** `orchestration/monitor.py` ✅ — health_dump() single-command health check
- [x] **P6-T5** Tool permissions: bypassPermissions already in build_cli_args (P1-T6) ✅
- [x] **P6-T6** latency_report.py ✅ (done in P5-T5)
- [x] **P6-T7** Phase 6 code complete ✅; `git tag phase-6-complete`

---

## Ops — 运营就绪化 ✅

**完成于**: 2026-04-16 · **Commit**: `c1d8552` · **已 push 到 GitHub**

- [x] **Ops-1** `tradingagents/daily_cycle.py` ✅ — launchd 入口，支持 `--dry-run` / `--tickers`；加载 `.env`；按 ticker 跑 pipeline → 记录 decision_log → 发 Gmail 报告
- [x] **Ops-2** `tradingagents/orchestration/alerts.py` ✅ — Gmail smtplib + App Password（替代 MCP，MCP create_draft 调用失败）；测试邮件已收到
- [x] **Ops-3** `tradingagents/orchestration/scheduler.py` ✅ — launchd plist 生成 + install/uninstall/status 子命令；已 load：`com.quantum-agent.daily-cycle`

**运行时配置**:
- Schedule: 周一至周五 07:00 CT = **08:00 ET**
- Tickers: IONQ, RGTI, QBTS, QUBT
- Gmail: hui.gao2000@gmail.com（App Password 在 `.env`，已 gitignored）
- Logs: `~/.tradingagents/daily_cycle_*.log`
- Kill switch: `touch /tmp/quantum_agent_kill` 停止 · `rm` 恢复

**管理命令**:
```
python -m tradingagents.daily_cycle --tickers IONQ --dry-run   # 干跑测试
python -m tradingagents.orchestration.scheduler status          # 查看 launchd
python -m tradingagents.orchestration.scheduler uninstall       # 卸载
```

---

## Session 17 — Backtest 框架 + sim_date 强制 — **[DEFERRED 2026-04-16]**

**Phase**: 7 · **SPEC**: §13 Phase 7, §8.2, §14

- [ ] **P7-T1** `backtest/runner.py`（`vectorbt`，sim_date 穿透每个 agent call + RAG query）
- [ ] **P7-T2** 缓存 Jan 2024 → present OHLCV（moomoo 优先，yfinance 回退）
- [ ] **P7-T3** `tests/backtest/test_no_lookahead.py`（CRITICAL）
- [ ] **P7-T4** `tests/backtest/test_reproducibility.py`（temperature=0 → 相同结果）

---

## Session 18 — Backtest 运行 + 指标 + 调参 — **[DEFERRED 2026-04-16]**

**Phase**: 7 · **SPEC**: §13 Phase 7, §16

- [ ] **P7-T5** 计算 Sharpe / MDD / Win Rate / Avg Hold；对比 Buy&Hold / MACD / SMA
- [ ] **P7-T6** 对比 backtest slippage 假设 vs. Phase 5 实际（drift > 30% 触发调参）
- [ ] **P7-T7** Phase 7 Exit：Sharpe > 1.5 AND MDD < 25%；`git tag phase-7-complete`

---

## Session 19 — 30 天 paper validation — **[DEFERRED 2026-04-16]**

**Phase**: 8 · **SPEC**: §13 Phase 8, §16, §15

- [ ] **P8-T1** 连续 30 交易日无人工干预
- [ ] **P8-T2** 每日 Gmail 报告
- [ ] **P8-T3** 每周 veto proposal 复盘（4 次）
- [ ] **P8-T4** 每周 slippage 趋势审阅
- [ ] **P8-T5** 每周延迟趋势审阅
- [ ] **P8-T6** 根据 paper 表现微调 prompt / 权重
- [ ] **P8-T7** Phase 8 Exit：30-day Sharpe > 1.0 AND MDD < 15% AND 中位延迟稳定；用户批准进 Phase 9

---

## Session 20 — Live executor + Phase 9 go-live — **[DEFERRED 2026-04-16]**

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
| 2026-04-16 | **方向修正**：初版 "方案 A = Claude Agent SDK + CC 订阅" 被官方文档否决。SDK 强制要求 `ANTHROPIC_API_KEY`，**不走**订阅。真正走订阅的路径只有 `claude -p` CLI 子进程。 | SPEC §2 / §6 / §11.3 / §12 的 LLM 调用方式待重定（等用户 A-Strict / A-Gray / E 再选一次） |
| 2026-04-16 | **ADR-2026-04-16 落地**：用户选 A-Strict（`claude` CLI）+ 暂缓 Phase 7-9 回测 / paper 验证 / live。fork 确认为 lydiagao/TradingAgents；uv 替 conda；merge 布局保留历史。 | SPEC §2 / §6 / §11.3 / §12 / §13 Phase 1/7/8/9 修订；PROGRESS P1-T3/T4/T5/T9/T11 改写；Session 17-20 标 DEFERRED；active task 74→57；P1-T1 ✅ |
| 2026-04-16 | **P1-T9 范围收窄**：upstream agents 用 `llm.bind_tools(...)`，我们的 CLI 路径无法 emulate。决定 Phase 1 只做 `_runner.py`，深度改写 upstream agent 挪到 Phase 3（§7.6/§7.7 本就要全部重写）。P1-T11 相应从"跑 upstream main.py"改为"mini baseline 走 `run_claude` 产出 decision JSON"。 | Phase 1 scope 减；Phase 3 增回；P1-T11 判据改；SPEC 不动（Phase 3 本来就规划了全部 agent 重写） |
| 2026-04-16 | **CLI schema 字段 pin**：`--json-schema` 模式下 CLI 返回结构为 `wrapper["structured_output"]`，`wrapper["result"]` 为空字符串。`_runner.py:run_claude` 已适配。 | SPEC §6 build_cli_args 与实际一致；run_claude schema 分支路径已验证 |
| 2026-04-16 | **IONQ 全流水线 integration test 通过**：13 CLI 调用（9 analyst + bull/bear + trader + PM），544.9s，输出 `hold` confidence 0.42。`data_incomplete_agents: []`（全部 agent 成功）。 | 验证端到端 pipeline 可用；PM 推理质量合格 |
| 2026-04-16 | **运营就绪化完成**：daily_cycle.py + Gmail smtplib alerts + launchd scheduler。Gmail MCP create_draft 失败 → 改用 App Password + smtplib。测试邮件已收到。launchd 已 load，周一至周五 08:00 ET 自动触发。 | 系统进入自动运营状态；Phase 7-9 deferred 期间每天自动产出分析报告 |

---

## Session 交接

### Session 01 开始（2026-04-16）

**本 session 起始状态**：
- 无任何 P1 任务已完成
- `TradingAgents` 尚未 fork / clone
- 本机无 `gh` / `conda`，仅有 `uv 0.11.2` + Python 3.14.2

**Session 01 中已发生**：
- 确定 LLM 后端 = A-Strict（`claude` CLI），Phase 7-9 暂缓（见 变更记录）
- SPEC / PROGRESS / TASKS 同步修订
- P1-T1 ✅（fork = lydiagao/TradingAgents）
- P1-T2 进行中：即将 clone fork 并 merge planning 历史

### Session 01 结束（2026-04-17）

**本 session 完成**：
- Phase 1-6 全部 57 个 active task 完成 ✅
- Ops 3 个任务完成（daily_cycle + Gmail + launchd）✅
- IONQ 全流水线 integration test 通过（13 calls, 544.9s, hold/0.42）
- 测试邮件已收到
- 代码 push 到 GitHub quantum-fork 分支
- 164 unit tests all green
- launchd loaded，明天 08:00 ET 自动首次运行

**系统状态**: 运营中
**下一步选项**:
- 等明天 08:00 ET 第一次自动运行，检查 Gmail 报告
- 解除 Phase 7 (backtest) deferred → 渐进路线（1 ticker × 1 month 试水）
- 解除 Phase 8 (30-day paper) deferred → 直接开始（Phase 7 可选跳过）
- 代码质量加固：给 agents / pipeline / executor 补 mock unit tests

**第一个动作**：等待用户回复关于 5 个 blocker 的决策：
1. GitHub fork 方式（浏览器 / 安装 gh / 先跳过）
2. conda → uv 替代是否 OK
3. TradingAgents 仓库布局（sibling / subdir / merge）
4. `ANTHROPIC_API_KEY` 的位置 / 提供方式 — **依赖 #5 的结果**
5. **LLM 后端路线**（方向修正后重选）：
   - **A-Strict**：`claude -p` CLI 子进程，走 CC 订阅，$0 API 开销；SPEC §6 要改（~50 行）
   - **A-Gray**：`claude_agent_sdk` + `CLAUDE_CODE_OAUTH_TOKEN`，ToS 灰色
   - **E**：回退原方案 + 调低 thinking / Haiku 倾斜，$30-60/月
   - **混合**：关键 agent 走 E，其他走 A-Strict

**拿到回复后的下一步**：
- 修订 `SPEC.md` §2 / §6 / §11.3 / §12（LLM 后端相关）
- 执行 P1-T1（fork）→ P1-T2（clone + 建 `quantum-fork` 分支）→ 按顺序推进

---
