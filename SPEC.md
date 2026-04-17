# Quantum Trading Agent — Implementation Specification

> **Purpose**: Complete build spec for a multi-agent LLM system that trades quantum computing stocks. Designed to be fed to Claude Code for implementation.
>
> **Baseline**: Fork of [TauricResearch/TradingAgents](https://github.com/TauricResearch/TradingAgents) v0.2.0 (which natively supports Claude 4.x).
>
> **Audience**: Claude Code. Read top to bottom, follow the implementation phases at the end. Ask before deviating from the spec.
>
> **Revision notes**:
> - **Section 4.8 hardened**: yfinance is now forbidden on the decision path. All live prices, IV, and order book data must come from moomoo real-time. Enforced via module-level import isolation and a CI guardrail test (Section 4.8.2). Hard Risk Gate now asserts `_source == "moomoo"` before evaluating.
> - **Section 10A added**: Every non-hold decision must auto-submit a paper order to moomoo and log end-to-end latency from market tick to fill. Six timestamps are collected, six derived latencies are pre-computed. Pipeline performance regressions become visible. Note: backtest path cannot capture T4/T5 (no real orders submitted), so only T0-T3 (data-staleness + pipeline-duration) are directly comparable between backtest and live paper.
> - **Session 0a hardening** (see §13 for the full change list): (a) `claude-opus-4-7` → `claude-opus-4-6` — 4.7 does not exist. (b) Anthropic SDK calling convention corrected to `thinking={"type": "enabled", "budget_tokens": N}`; there is no `effort` parameter and no `"adaptive"` thinking type. (c) Embedding provider made explicit — Voyage AI (paid) or local `sentence-transformers`; Anthropic has no embedding API. (d) `agents/risk/` renamed to `agents/risk_debate/` to disambiguate from top-level `risk/`. (e) `dataflows/yfinance_client.py` removed — §4.8.2 mandates `dataflows/historical.py` as the sole yfinance home. (f) Reddit mandates OAuth via PRAW; unauthenticated fallback removed. (g) §4.8.2 guardrail now scans `execution/` as well. (h) `dataflows/__init__.py` uses lazy `get_client()` instead of module-import-time instantiation. (i) News/Sentiment output schemas now explicitly define `strategic_score`/`macro_score`. (j) Added §4.10 (graceful degradation policy), §8.5 (inter-agent Pydantic schema contracts), §8.2 (backtest `sim_date` filter baked into vector store retrieval), and `MoomooClient.wait_for_fill()` in §4.8.3.
> - **Session 0b ADR sync**: (a) **Scheduler**: system cron / launchd (macOS) replaces APScheduler — in-process scheduling shares a process with the pipeline, making crashes a SPOF. (b) **Backtest library**: `vectorbt` replaces `backtrader` — vectorized, actively maintained, simpler API. (c) **Per-cycle cost circuit breaker** added to §11.3 alongside the per-day hard stop (a single Opus-heavy cycle can blow through the daily budget by itself). (d) Phase 5 target revised from 1 week to 2 weeks (T0-T5 state threading is the hardest plumbing task in the project; 1 week is not realistic). (e) §14 integration test cost budget relaxed from $2.50 to $5.00 per decision (matches observed cost with Opus PM + Opus Quantum Tech Expert at thinking_budget=16000). (f) §16 "<10 min pipeline" metric now explicitly = §10A.6 green-zone target (§10A.6 yellow/red adjusted so yellow does not exceed §16 MVP threshold).

---

## 1. Project overview

### What we're building

A 9-layer multi-agent trading system specialized for quantum computing stocks (IONQ, RGTI, QBTS, QUBT + IBM/GOOGL/MSFT/NVDA quantum exposure). The system runs daily pre-market, uses 9 specialized analyst agents feeding into a Bull/Bear debate, then a Trader+Risk team, then hard risk rules, then a Portfolio Manager with stage-weighted scoring, and finally paper/live execution via moomoo.

### Design principles

1. **Model tiering for cost**: Different agents use different Claude models (Haiku 4.5 / Sonnet 4.6 Medium / Sonnet 4.6 High / Opus 4.6) based on cognitive load.
2. **Free-only data sources**: No Bloomberg/Reuters/FT paid feeds. Everything via free RSS, free-tier APIs, SEC EDGAR, and public government sources.
3. **Hard risk gate is code, not LLM**: Non-negotiable rules (position caps, loss limits) are implemented as deterministic Python checks, not agent discussions.
4. **Stage-weighted scoring**: The same stock is scored differently depending on its maturity (pre-revenue vs. scaling).
5. **Paper trading first**: Never execute live until 30+ days of paper validation.

### Target decision cadence

- **Primary**: Daily pre-market (8:00 AM EST, ~90 min before open)
- **Event-driven**: Earnings release, DARPA/DOE contract announcement, major technical milestone
- **Decision output**: Buy / Sell / Hold + position size + rationale

---

## 2. Tech stack

### Core

- **Python**: 3.13
- **Agent framework**: LangGraph (already used by TradingAgents)
- **LLM invocation**: **`claude` CLI subprocess** (走 Claude Code 订阅，不走 API 计费) — see §6 ADR-2026-04-16
  - 原方案 `anthropic` Python SDK 被替换：`claude_agent_sdk` 不支持订阅认证（官方 policy 明确禁止），走 CLI 子进程是唯一走订阅的路径
  - 需要 `claude` CLI 在 `PATH` 里且已 `claude login` 完成
- **Vector store**: ChromaDB (local, embedded)
- **Persistence**: SQLite via SQLAlchemy
- **Scheduler**: system cron on Linux or `launchd` on macOS (NOT APScheduler — see §11.1 ADR)

### Data & market

- **Market data**: moomoo OpenAPI (user already has this configured)
- **Free market data backup**: `yfinance`
- **RSS**: `feedparser`
- **HTTP**: `httpx` (async) + `requests`
- **SEC EDGAR**: `sec-edgar-api` or direct REST
- **Reddit**: `praw` or direct JSON endpoints

### Dev tooling

- **Env management**: `conda` or `uv`
- **Secrets**: `python-dotenv`
- **Logging**: `loguru`
- **Testing**: `pytest`, `pytest-asyncio`
- **Backtest**: `vectorbt` (see §13 Phase 7 ADR — vectorized, Python-native, actively maintained)

### requirements.txt (seed, extend from TradingAgents/requirements.txt)

```
langgraph>=0.2.0
chromadb
sentence-transformers
sqlalchemy
feedparser
httpx
yfinance
requests
beautifulsoup4
sec-edgar-api
praw
python-dotenv
loguru
pytest
pytest-asyncio
pandas
numpy
pydantic>=2.0
```
- `anthropic` / `langchain-anthropic` **已从 requirements 移除**（ADR-2026-04-16：LLM 调用走 `claude` CLI 子进程，不走 Anthropic SDK）。
- 运行前置：系统需装好 `claude` CLI 并已 `claude login`。
- `vectorbt` 暂不纳入（ADR-2026-04-16：Phase 7 回测暂缓）。
- 无 `apscheduler` — scheduling 交给 OS cron/launchd（§11.1）。

---

## 3. Target stock universe

```python
# tradingagents/config/universe.py

QUANTUM_PURE_PLAYS = [
    "IONQ",   # IonQ - trapped ion
    "RGTI",   # Rigetti - superconducting
    "QBTS",   # D-Wave - annealing
    "QUBT",   # Quantum Computing Inc - photonic
]

QUANTUM_EXPOSURE = [
    "IBM",    # Condor, Heron processors
    "GOOGL",  # Sycamore, Willow
    "MSFT",   # Azure Quantum, topological qubits
    "NVDA",   # NVQLink, CUDA-Q, Ising
    "HON",    # Honeywell / Quantinuum
]

UNIVERSE = QUANTUM_PURE_PLAYS + QUANTUM_EXPOSURE
```

Start with `QUANTUM_PURE_PLAYS` for Phase 1. Add exposure stocks in Phase 3.

---

## 4. Data sources (free only)

All sources below have been verified free. Do not add any paid source without explicit user approval.

### 4.1 Quantum-domain media (RSS)

| Source | Feed URL | Notes |
|--------|----------|-------|
| Quantum Insider | `https://thequantuminsider.com/feed/` | Daily industry news |
| Quantum Computing Report | `https://quantumcomputingreport.com/feed/` | Technical depth |
| HPCwire Quantum | `https://www.hpcwire.com/category/quantum-computing/feed/` | Enterprise deals |
| Quantum Zeitgeist | `https://quantumzeitgeist.com/feed/` | Breakthrough news |

Implementation: poll every 30 min, deduplicate by URL hash, embed and store in ChromaDB with `source` and `published_at` metadata.

### 4.2 arXiv (free API)

```
https://export.arxiv.org/api/query?search_query=cat:quant-ph&sortBy=submittedDate&sortOrder=descending&max_results=30
```

Pull daily. Use to detect technical breakthrough papers. Filter on keywords: `logical qubit`, `error correction`, `fault tolerant`, `quantum supremacy`, plus company names (IBM, Rigetti, IonQ, etc.).

### 4.3 SEC EDGAR (free, official)

- **Base**: `https://data.sec.gov/`
- **Submissions API**: `https://data.sec.gov/submissions/CIK{cik}.json`
- **Company facts (XBRL)**: `https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json`

Required filings to parse:
- **10-Q / 10-K**: revenue, cash, RPO (remaining performance obligations), burn rate
- **8-K**: material events (contracts, acquisitions, partnerships)
- **DEF 14A**: compensation, insider alignment
- **13F**: institutional holdings (quarterly, 45-day lag)

**Rate limit**: 10 requests/second with proper User-Agent header. Always set:
```python
headers = {"User-Agent": "QuantumTradingAgent research@example.com"}
```

Company CIK map (store in `config/ciks.json`):
```json
{
  "IONQ": "0001824920",
  "RGTI": "0001838359",
  "QBTS": "0001852101",
  "QUBT": "0001758009",
  "IBM": "0000051143",
  "GOOGL": "0001652044",
  "MSFT": "0000789019",
  "NVDA": "0001045810",
  "HON": "0000773840"
}
```

### 4.4 News aggregator (free tier)

**NewsAPI.org** — 100 requests/day free tier.

```
https://newsapi.org/v2/everything?q={ticker}&sortBy=publishedAt&apiKey={NEWSAPI_KEY}
```

Rationing: reserve 50/day for quantum pure-plays (10 per ticker), 30/day for market-wide queries, 20/day for event-driven queries. Cache aggressively in ChromaDB.

**Alternative**: Google News RSS (fully free, but lower quality):
```
https://news.google.com/rss/search?q={ticker}+quantum+computing
```

### 4.5 Reddit (free, OAuth required)

Subreddits:
- `r/QuantumComputing` - domain signal
- `r/wallstreetbets` - retail sentiment
- `r/stocks`, `r/investing` - broader context

**Authentication is mandatory.** Since July 2023 Reddit has tightened
unauthenticated API access to the point of effective unusability (quotas too
small for any production pipeline, frequent 429s). Register a free developer
app at `https://www.reddit.com/prefs/apps` and use `praw` with OAuth2:

```python
import praw
reddit = praw.Reddit(
    client_id=os.environ["REDDIT_CLIENT_ID"],
    client_secret=os.environ["REDDIT_CLIENT_SECRET"],
    user_agent=os.environ["REDDIT_USER_AGENT"],  # required, identifies the app
)
for submission in reddit.subreddit("QuantumComputing").new(limit=50):
    ...
```

Authenticated rate limit: 100 QPM per OAuth client (Reddit's current cap).
Do not attempt to scrape `reddit.com/.../*.json` without OAuth — it will 429
quickly and is against ToS.

### 4.6 Government contracts

**SAM.gov API** (free, requires registration):
```
https://api.sam.gov/opportunities/v2/search?keywords=quantum&postedFrom={date}&postedTo={date}&api_key={SAM_KEY}
```

Filter on:
- Agency: DARPA, DOE, NSF, DOD, NIST
- Keywords: "quantum computing", "quantum networking", "PQC", "post-quantum"

**DARPA news**: scrape `https://www.darpa.mil/news-events`

### 4.7 USPTO (free patents)

```
https://ppubs.uspto.gov/pubwebapp/external.html?db=USPAT
```

Track patent filings from target companies. Weekly poll. Feed into Quantum Tech Expert's context.

### 4.8 Market data

#### 4.8.1 Data-source discipline (HARD RULE, non-negotiable)

**All decisions that trigger real money movements MUST use moomoo real-time data.**
yfinance (15-minute delayed) or any other non-real-time source is **forbidden** on the decision path.

Rationale:
- yfinance has 15-20 minute delay for US equities (Yahoo public data obligation)
- Quantum stocks routinely move ±5-8% in that window; stop-losses computed on delayed data will trigger at wildly wrong prices
- yfinance has no API contract with Yahoo; it breaks unpredictably when Yahoo updates its site
- Pre-market and after-hours coverage in yfinance is incomplete, exactly when quantum catalysts hit

**Must use moomoo (real-time):**
- Current price for entry/exit decisions
- Implied volatility for Hard Risk Gate `MAX_IV_FOR_NEW_BUY` check
- Position P&L calculation (for `DAILY_LOSS_HALT` check)
- Options chain snapshot for Trader sizing
- Order book depth for slippage modeling
- Session state detection (pre-market / regular / after-hours)

**yfinance permitted ONLY for:**
- Historical OHLC for backtests (no live decision on this path). Prefer
  moomoo historical K-lines when available; yfinance remains as the fallback.
- Nothing else. The earlier "static fundamentals" and "supplementary
  institutional holders" carve-outs were removed in Session 0a hardening —
  SEC EDGAR XBRL is authoritative for both and yfinance was only a tempting
  backdoor that diluted the §4.8 guarantee.

#### 4.8.2 Enforcement — module-level import isolation

Organize `dataflows/` so that yfinance **cannot be accidentally called** from live-decision code. The live decision surface uses a **lazy client accessor**, not a module-import-time instantiation, so that (a) tests can import `tradingagents.dataflows` without opening a moomoo connection and (b) moomoo outages do not brick the whole process at import time:

```python
# dataflows/__init__.py — live decision surface (lazy)
from __future__ import annotations
from typing import Optional
from .moomoo_client import MoomooClient

_client: Optional[MoomooClient] = None

def get_client() -> MoomooClient:
    """Lazy singleton accessor. Raises clearly if moomoo is unreachable."""
    global _client
    if _client is None:
        _client = MoomooClient()  # may raise ConnectionError; callers should handle
    return _client

# Public live-decision API — decision code imports these wrappers, NOT the client
def get_realtime_quote(ticker: str) -> dict:
    return get_client().get_realtime_quote(ticker)

def get_live_options_chain(ticker: str, expiration: str | None = None) -> dict:
    return get_client().get_live_options_chain(ticker, expiration)

def get_order_book(ticker: str, depth: int = 10) -> dict:
    return get_client().get_order_book(ticker, depth)

def get_session_state(ticker: str) -> str:
    return get_client().get_session_state(ticker)

# Historical/analysis namespace — yfinance lives only here, and must be
# imported explicitly: `from dataflows import historical`.
# Code review and the guardrail test below flag any such import appearing
# in files under agents/, risk/, scoring/, orchestration/, or execution/.
from . import historical  # noqa: E402,F401 — re-exported for explicit access
```

```python
# dataflows/historical.py — the ONLY place yfinance is imported
import yfinance as yf

def get_backtest_ohlc(ticker: str, period: str = "2y"):
    return yf.Ticker(ticker).history(period=period)
```

**Guardrail test** (must be in `tests/unit/test_no_yfinance_on_hot_path.py`).
Note: `FORBIDDEN_DIRS` now includes `execution/` so that `paper_executor.py`
and future `live_executor.py` cannot quietly import yfinance:

```python
import ast, pathlib

FORBIDDEN_DIRS = ["agents", "risk", "scoring", "orchestration", "execution"]

def test_no_yfinance_import_on_decision_path():
    repo = pathlib.Path(__file__).parents[2] / "tradingagents"
    violations = []
    for d in FORBIDDEN_DIRS:
        for py in (repo / d).rglob("*.py"):
            tree = ast.parse(py.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mods = [a.name for a in node.names] if isinstance(node, ast.Import) \
                           else [node.module or ""]
                    if any("yfinance" in m for m in mods):
                        violations.append(str(py))
    assert not violations, f"yfinance imported on decision path: {violations}"
```

This test runs in CI on every commit. Any PR that imports yfinance outside `dataflows/historical.py` fails. The guardrail only detects static imports; dynamic imports via `importlib.import_module("yfinance")` would slip through, but such code is unusual and easy to spot in review.

#### 4.8.3 moomoo client interface

The `MoomooClient` must expose at minimum:

```python
class MoomooClient:
    def get_realtime_quote(self, ticker: str) -> dict:
        """<1s latency. Returns:
        {
          "price": float,         # last trade price
          "bid": float, "ask": float, "volume": int,
          "ts_exchange": str,     # ISO8601 UTC with ms — EXCHANGE tick time (T0)
          "ts_received":  str,    # ISO8601 UTC with ms — when this process got the payload (T1)
          "_source": "moomoo",
        }
        Both timestamps are required; `ts_exchange` is T0, `ts_received` is T1.
        If moomoo returns only one of them, MoomooClient fills the other with
        the best available equivalent and tags the payload with
        `_ts_exchange_approximated: True` so downstream code can warn.
        """

    def get_live_options_chain(self, ticker: str, expiration: str | None = None) -> dict:
        """Live IV, OI, greeks. Required for risk gate IV check."""

    def get_order_book(self, ticker: str, depth: int = 10) -> dict:
        """Top N bid/ask levels. Used by Trader for slippage-aware sizing."""

    def get_session_state(self, ticker: str) -> str:
        """One of: 'pre_market' | 'regular' | 'after_hours' | 'closed'."""

    def get_historical_klines(self, ticker: str, interval: str, start: str, end: str) -> list[dict]:
        """Preferred historical OHLC source. Only fall back to yfinance
        (via dataflows.historical.get_backtest_ohlc) if moomoo cannot serve
        the requested range."""

    def place_order(self, ticker: str, side: str, qty: int, order_type: str,
                    trd_env: str = "SIMULATE", **kwargs) -> dict:
        """Submit order. `trd_env='SIMULATE'` for paper, `'REAL'` for live.
        Returns {order_id, status, ts_submitted, _source: 'moomoo'}."""

    def wait_for_fill(self, order_id: str, timeout_sec: int = 10) -> dict:
        """Block until the order is filled, rejected, cancelled, or timeout.
        Returns {
          status: 'filled'|'partial'|'rejected'|'cancelled'|'timeout',
          fill_price: float|None, fill_qty: int, ts_filled: str|None,
          _source: 'moomoo',
        }. On timeout, status is 'timeout' and callers MUST NOT retry
        blindly — decide whether to cancel or keep the order live."""
```

Every return dict from this client must include `_source: "moomoo"` so downstream code (especially Hard Risk Gate) can assert it.

**Subscription tier recommendation**: moomoo Level 2 minimum. Level 1 only gives top-of-book, insufficient for Trader slippage estimation. Premium tier is optional.

### 4.9 13F institutional holdings

Extract from SEC EDGAR 13F filings directly (not paid services like WhaleWisdom).
- Quarterly snapshots
- 45-day reporting lag
- Parse `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F-HR` for the latest

### 4.10 Graceful degradation policy

Data sources fail. The pipeline must have explicit behavior for each source.

Each source falls into one of three **criticality tiers**. The tier determines
what the pipeline does when that source is unavailable (timeout, 5xx, empty
response, parse error, rate limit, or authentication failure).

| Tier | Sources | Failure behavior |
|------|---------|------------------|
| **CRITICAL** (pipeline halts on failure) | moomoo real-time quote, moomoo options chain, moomoo order book, moomoo session state | Halt the pipeline for the affected ticker. Emit a HALT alert. Do NOT substitute yfinance or any other source — that would violate §4.8. The ticker is skipped for the current cycle; other tickers continue. |
| **IMPORTANT** (degrade score, keep running) | SEC EDGAR, NewsAPI, quantum RSS feeds, Reddit (PRAW), SAM.gov | The affected agent receives a `data_incomplete: True` flag and produces a partial output with `confidence: "low"`. Scoring engine applies a confidence discount (multiply that dimension's weight by 0.5). PM prompt receives the flag in context and is instructed to prefer `hold`. |
| **OPTIONAL** (silently skip) | USPTO, DARPA news scrape, arXiv | Agent proceeds without that input. No alert. Log at DEBUG level. |

**Minimum viable data set** per cycle (below this, the pipeline outputs `hold` for the ticker regardless of any agent opinion):
- moomoo real-time quote ✅
- moomoo session state ✅
- At least one of: SEC EDGAR latest 10-Q (for stage detection) OR valid financials cache <30 days old

**Implementation sketch** (`dataflows/retry.py`, shared helper):
```python
from dataclasses import dataclass

@dataclass
class FetchResult:
    ok: bool
    data: dict | None
    source: str
    tier: str              # 'critical' | 'important' | 'optional'
    error: str | None = None

def fetch_with_policy(source_name: str, fetcher, tier: str, retries: int = 2) -> FetchResult:
    """One retry with exponential backoff, then give up per policy."""
    # ... (implementation)
```

Each data-source client in `dataflows/` uses this helper. Agents receive
`FetchResult` objects, not bare dicts, so they can branch on `ok`.

**Acceptance test** (`tests/unit/test_graceful_degradation.py`):
- All CRITICAL sources mocked to fail → pipeline halts for ticker, alert fired
- All IMPORTANT sources mocked to fail → pipeline completes, decision is `hold`, all affected dimension weights halved
- All OPTIONAL sources mocked to fail → pipeline completes, decision unchanged from the all-sources-working baseline

---

## 5. Project structure

Fork `TauricResearch/TradingAgents` and add the following structure:

```
tradingagents/
├── agents/
│   ├── __init__.py
│   ├── analysts/
│   │   ├── technical.py
│   │   ├── news.py
│   │   ├── sentiment.py
│   │   ├── flow_technicals.py        # NEW
│   │   ├── fundamentals.py
│   │   ├── valuation_health.py       # NEW
│   │   ├── commercialization.py      # NEW
│   │   ├── quantum_tech_expert.py    # NEW (Opus 4.6, high thinking budget)
│   │   └── regulatory_policy.py      # NEW
│   ├── researchers/
│   │   ├── bull.py
│   │   └── bear.py
│   ├── risk_debate/                  # RENAMED from risk/ — disambiguates from top-level risk/ (hard gate)
│   │   ├── risky.py
│   │   ├── neutral.py
│   │   └── safe.py
│   ├── trader.py
│   └── portfolio_manager.py
├── dataflows/
│   ├── __init__.py                   # NEW: lazy get_client() surface (see §4.8.2)
│   ├── rss_quantum.py                # NEW: quantum media feeds
│   ├── arxiv_client.py               # NEW
│   ├── sec_edgar.py                  # NEW: 10-Q, 10-K, 13F
│   ├── newsapi_client.py             # NEW: free tier
│   ├── reddit_client.py              # NEW: PRAW with OAuth (no unauth fallback)
│   ├── sam_gov.py                    # NEW: gov contracts
│   ├── uspto_client.py               # NEW
│   ├── moomoo_client.py              # NEW: adapts moomoo OpenAPI
│   └── historical.py                 # NEW: the ONLY module allowed to import yfinance (§4.8.2)
├── memory/
│   ├── vector_store.py               # NEW: ChromaDB wrapper, sim_date-aware retrieval (§8.2)
│   ├── knowledge_base.py             # NEW: quantum domain KB
│   ├── decision_log.py               # NEW: historical decisions + execution_log
│   └── schemas.py                    # NEW: Pydantic models for agent I/O (§8.5)
├── execution/
│   ├── paper_executor.py             # NEW: auto paper orders, latency capture (10A)
│   └── live_executor.py              # NEW: Phase 9+ only, guarded by ENVIRONMENT
├── risk/
│   ├── hard_gate.py                  # NEW: deterministic rules
│   └── kill_switch.py                # NEW
├── scoring/
│   ├── engine.py                     # NEW: stage-weighted scoring
│   └── dimensions.py                 # NEW: 7 dimension calculators
├── orchestration/
│   ├── scheduler.py                  # NEW: Layer 0
│   ├── monitor.py                    # NEW
│   ├── alerts.py                     # NEW: Gmail/Slack
│   ├── cost_tracker.py               # NEW
│   └── latency_report.py             # NEW: daily latency digest (10A.7)
├── graph/
│   └── trading_graph.py              # MODIFIED: add per-agent model config
├── config/
│   ├── default_config.py             # MODIFIED
│   ├── universe.py                   # NEW
│   ├── ciks.json                     # NEW
│   └── model_config.py               # NEW: per-agent model mapping
├── backtest/
│   └── runner.py                     # NEW
└── tests/
    ├── unit/
    ├── integration/
    └── backtest/
```

---

## 6. Model configuration (per-agent)

The baseline TradingAgents framework only has two tiers (`deep_think_llm`, `quick_think_llm`). Modify to support per-agent configuration.

### ADR-2026-04-16 — 走 `claude` CLI 子进程，不走 Anthropic SDK

**背景**：原 SPEC 用 `anthropic` Python SDK / `langchain_anthropic.ChatAnthropic`。调研后确认 `claude_agent_sdk` 不支持 Claude Code 订阅计费（Anthropic 官方 policy 明确禁止 SDK 使用 claude.ai OAuth）。要走订阅，唯一路径是 `claude` CLI 子进程。

**结论**：每次 agent 调用 = `subprocess.run(["claude", "-p", ...])`。从 CC 订阅消耗额度，不产生 API 费用。

**取舍**：
- ✅ 零 API 支出（仅依赖已付的 CC 订阅）
- ✅ CLI 支持 `--output-format json` + JSON Schema 结构化输出
- ✅ 支持 per-call `--model` 覆盖
- ⚠️ 自定义 Python 工具（moomoo client、RAG retrieval、SEC EDGAR）不能作为 MCP tool 挂入 CLI；改为 LangGraph node 里手动编排："先拉数据 → 塞 prompt → CLI 调用 → 解析 JSON"
- ⚠️ Extended thinking 通过 CLI flag 传递（`--thinking-budget N` 或等价），验证后 pin 到 `build_thinking_param` 的输出
- ⚠️ 每次子进程启动 ~500ms overhead，每日 16 agent × 1 ticker = 可忽略

### `tradingagents/config/model_config.py`

```python
# Each entry pins a model ID and an optional extended-thinking budget (tokens).
# Runtime invocation is `claude -p` CLI subprocess — see ADR-2026-04-16.
# There is no "effort" parameter. If you need more reasoning, raise budget_tokens.

AGENT_MODEL_MAP = {
    # Layer 3 - Market & flow analysts (Haiku for structured data, no thinking)
    "technical":           {"model": "claude-haiku-4-5-20251001",  "thinking_budget": 0},
    "news":                {"model": "claude-sonnet-4-6",          "thinking_budget": 4000},
    "sentiment":           {"model": "claude-haiku-4-5-20251001",  "thinking_budget": 0},
    "flow_technicals":     {"model": "claude-haiku-4-5-20251001",  "thinking_budget": 0},

    # Layer 3 - Financial & business (Sonnet with thinking for reasoning)
    "fundamentals":        {"model": "claude-haiku-4-5-20251001",  "thinking_budget": 0},
    "valuation_health":    {"model": "claude-sonnet-4-6",          "thinking_budget": 8000},
    "commercialization":   {"model": "claude-sonnet-4-6",          "thinking_budget": 8000},

    # Layer 3 - Domain specialized (Opus with high thinking)
    "quantum_tech_expert": {"model": "claude-opus-4-6",            "thinking_budget": 16000},
    "regulatory_policy":   {"model": "claude-sonnet-4-6",          "thinking_budget": 4000},

    # Layer 4 - Researchers
    "bull_researcher":     {"model": "claude-sonnet-4-6",          "thinking_budget": 8000},
    "bear_researcher":     {"model": "claude-sonnet-4-6",          "thinking_budget": 8000},

    # Layer 5 - Trader + Risk debate
    "trader":              {"model": "claude-sonnet-4-6",          "thinking_budget": 8000},
    "risky_analyst":       {"model": "claude-sonnet-4-6",          "thinking_budget": 8000},
    "neutral_analyst":     {"model": "claude-sonnet-4-6",          "thinking_budget": 8000},
    "safe_analyst":        {"model": "claude-sonnet-4-6",          "thinking_budget": 8000},

    # Layer 7 - Portfolio manager (Opus with high thinking)
    "portfolio_manager":   {"model": "claude-opus-4-6",            "thinking_budget": 16000},
}

def get_model_config(agent_name: str) -> dict:
    return AGENT_MODEL_MAP[agent_name]

def build_cli_args(agent_name: str, *, schema: dict | None = None,
                   allow_tools: bool = False) -> list[str]:
    """
    构造 `claude -p` CLI 调用参数列表。prompt 通过 subprocess stdin 传入。
    - schema: 可选 JSON Schema dict → `--json-schema '<inline json>'`
    - allow_tools: False 时加 `--tools ""` 禁用所有 built-in 工具（agent 从 prompt 吃数据）
    """
    cfg = get_model_config(agent_name)
    args = ["claude", "-p", "--output-format", "json",
            "--model", cfg["model"],
            "--permission-mode", "bypassPermissions"]
    effort = _budget_to_effort(cfg["thinking_budget"])  # 0 -> None; 1-4k medium; 4-8k high; 8-16k xhigh; >16k max
    if effort is not None:
        args += ["--effort", effort]
    if not allow_tools:
        args += ["--tools", ""]
    if schema is not None:
        args += ["--json-schema", json.dumps(schema, separators=(",",":"))]
    return args
```

**CLI flag findings pinned during 2026-04-16 P1-T5 probe**（更新 ADR assumption list）：
- `--effort <low|medium|high|xhigh|max>` **替代** `--thinking-budget N` —— CLI 无 token 级 flag；token 预算映射到 effort 分级（见 `_budget_to_effort`）
- `--permission-mode bypassPermissions` —— 让 `-p` 在无人值守下不弹 tool-approval
- `--tools ""` —— 禁用所有 built-in 工具（Read/Bash/Edit 等）。agent 的外部数据从 prompt 吃
- `--json-schema '<inline json>'` —— 直接接 JSON 字符串，不要求文件路径

### LangGraph node 调用模板 (`tradingagents/agents/_runner.py`)

```python
import json, subprocess
from tradingagents.config.model_config import build_cli_args

def run_claude(agent_name: str, prompt: str, schema: dict | None = None,
               timeout: int = 120) -> dict:
    """
    LangGraph node 里统一调用入口。Returns parsed JSON (or raw text if schema=None).
    Raises TimeoutError / subprocess.CalledProcessError on failure.
    """
    args = build_cli_args(agent_name, prompt_path=None,
                          schema_path=_write_schema_tmpfile(schema) if schema else None)
    proc = subprocess.run(args, input=prompt, capture_output=True,
                          text=True, timeout=timeout, check=True)
    return json.loads(proc.stdout)
```

### Modify `graph/trading_graph.py`

Locate where agents are instantiated (`setup.py` 或等效文件)。把 `ChatAnthropic` / `Anthropic()` 调用替换为 `run_claude(agent_name, prompt, schema)`。LangGraph 的 node function 里显式调 `run_claude`，不再依赖 `llm.bind_tools(...)` —— 自定义工具（moomoo / RAG / SEC）在 node 里直接调 Python 函数，把结果塞入 prompt 再给 CLI。

**不再使用的模式**：
```python
# 旧（ADR-2026-04-16 之前）
from anthropic import Anthropic
client = Anthropic()
client.messages.create(model=..., thinking={"type":"enabled","budget_tokens":N}, ...)

# 旧
from langchain_anthropic import ChatAnthropic
ChatAnthropic(model=..., thinking=...)
```

**禁止的 pattern**（仍然）：
- `extra_body={"effort": "high"}` — 不存在的字段
- `thinking={"type": "adaptive"}` — SDK 没有；CLI 里如支持再单独验证

**Phase 1 需要验证的 CLI 假设**（P1-T11 跑第一次时落实）：
- `claude -p` 的确切 flag 名（`--thinking-budget` vs 其他）
- `--output-format json` 返回结构（是否包裹在 `{"result": ...}` 里）
- `--json-schema` 参数可用性
- 不可交互场景下 `--allowedTools` / `--permission-mode` 的需要性

验证完毕后，把真实可用的 flag 名 pin 入 `build_cli_args`。

---

## 7. Agent specifications

Each agent gets its own file in `tradingagents/agents/...`. All agents follow this structure:

```python
# tradingagents/agents/analysts/_template.py
from langchain_core.prompts import ChatPromptTemplate

SYSTEM_PROMPT = """..."""

def create_agent(llm, tools):
    prompt = ChatPromptTemplate.from_messages([
        ("system", SYSTEM_PROMPT),
        ("placeholder", "{messages}"),
    ])
    return prompt | llm.bind_tools(tools)
```

Below are the full system prompts for the most novel agents. The traditional 4 agents (Technical, News, Sentiment, Fundamentals) inherit TradingAgents defaults — update ticker lists to the quantum universe.

### 7.1 Quantum Tech Expert (Opus 4.6, high thinking budget)

```
You are a quantum computing industry technical expert advising a trading desk.
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

Output format (JSON):
{
  "tech_score": 0-100,
  "position_vs_peers": "leader" | "competitive" | "laggard",
  "roadmap_credibility": "high" | "medium" | "low",
  "key_risks": [list],
  "time_to_advantage": "estimated years to quantum advantage for this company",
  "reasoning": "3-5 sentences"
}

Rules:
- Refuse to speculate beyond available evidence. Cite sources.
- If a claim cannot be validated against a primary source (paper, filing,
  verified benchmark), flag as "unverified".
- NEVER give investment advice or price targets. That is the portfolio
  manager's job.
```

### 7.2 Commercialization Analyst (Sonnet 4.6, high effort)

```
You are a commercialization analyst for quantum computing stocks. You track
whether companies are converting technology into revenue.

Ignore technical details (other agents cover those). Focus on six dimensions:

1. BACKLOG GROWTH
   - Remaining Performance Obligation (RPO) from 10-Q filings
   - Quarter-over-quarter change
   - Year-over-year change

2. CUSTOMER QUALITY
   - Government (DARPA/DOE/NSF): stable but low margin
   - Academic: showcase, low margin
   - Fortune 500 enterprise: real commercialization signal
   - Cloud marketplace distribution (AWS Braket, Azure Quantum, GCP)

3. REVENUE STRUCTURE
   - One-time hardware sales
   - Recurring QCaaS (Quantum-as-a-Service)
   - Professional services
   - License fees
   - Trend: is recurring % growing?

4. PRODUCTION USE CASES
   - Proof-of-Concept only vs. moved to production
   - Industries: pharma, finance, logistics, materials
   - Cite specific named customers

5. UNIT ECONOMICS
   - Per-shot pricing, subscription pricing, gross margin
   - CAC vs LTV if disclosed

6. CHANNEL AND ECOSYSTEM
   - Integrations (Nvidia NVQLink, Dell, Accenture)
   - Developer community (Qiskit, Cirq, Ocean stats)
   - System integrator partnerships

CRITICAL DISTINCTION:
- REAL signal: SEC-disclosed RPO, confirmed revenue, signed contracts
- WEAK signal: MOU, LOI, "strategic partnership" press releases
- Discount press-release-only signals by 70%.

Output format (JSON):
{
  "commercialization_score": 0-100,
  "score_delta_this_cycle": -10 to +10,
  "dimensions": {
    "backlog_growth": 0-30,
    "customer_quality": 0-20,
    "recurring_revenue": 0-20,
    "production_use_cases": 0-15,
    "cloud_distribution": 0-10,
    "ecosystem_lockin": 0-5
  },
  "recent_signals": [
    {"event": "...", "source": "...", "impact": "+2 | -3 | ..."}
  ],
  "reasoning": "..."
}

If disclosed revenue < $1M TTM, cap commercialization_score at 30 regardless
of other signals (pre-revenue stocks can't score high on commercialization).
```

### 7.3 Valuation & Financial Health (Sonnet 4.6, high effort)

```
You are a financial analyst specialized in pre-profit growth stocks in the
quantum computing sector. Quantum pure-plays routinely trade at P/S ratios
above 100, making traditional valuation methods insufficient.

Evaluate each company on:

1. CASH POSITION (absolute values from latest 10-Q)
   - Total cash + equivalents + short-term investments
   - Compare to quarterly burn rate for runway in quarters

2. BURN RATE TREND
   - Quarterly cash consumption
   - Is burn expanding (bad) or contracting (good)?
   - Operating cash flow trajectory

3. VALUATION MULTIPLES
   - P/S ratio vs 5-year median
   - P/S ratio vs sector median (quantum pure-plays ~200x, tech sector ~7x)
   - Forward P/S using analyst consensus revenue
   - EV/Revenue, if applicable

4. DILUTION RISK
   - Share count trend over last 8 quarters
   - Pending warrants/options that could dilute
   - ATM (at-the-market) offering programs active?
   - Probability of another equity raise in next 12 months

5. EPS REVISION TREND
   - Are analyst EPS estimates being revised up or down?
   - Magnitude of revisions

6. CAPITAL STRUCTURE
   - Debt / equity
   - Convertible securities outstanding
   - Minimum cash covenants

7. RED FLAGS
   - Going-concern language in 10-Q/10-K
   - Material weakness in internal controls
   - Auditor changes

Output format (JSON):
{
  "financial_health_score": 0-100,
  "valuation_tier": "cheap" | "fair" | "rich" | "bubble",
  "runway_quarters": int,
  "dilution_probability_12m": 0.0 to 1.0,
  "red_flags": [list],
  "reasoning": "..."
}

Hard rules:
- If runway < 4 quarters at current burn: flag HIGH risk, score max 40.
- If P/S > 5x sector median AND runway < 6 quarters: flag "bubble risk".
- Going-concern language = immediate flag, score max 20.
```

### 7.4 Regulatory & Policy Analyst (Sonnet 4.6, medium effort)

```
You are a regulatory and policy analyst tracking government action affecting
quantum computing companies.

Monitor:

1. US GOVERNMENT CONTRACTS
   - DARPA programs: QBI, HARQ, ONISQ, LogiQ
   - DOE: National QIS Research Centers, Quantum Leap Challenge Institutes
   - NSF: Quantum Leap, Q-NEXT
   - DOD: Defense Quantum Benchmarking

2. INTERNATIONAL POLICY
   - EU Quantum Flagship and Chips Act
   - UK National Quantum Strategy
   - China 15th Five-Year Plan quantum priorities
   - Japan Takaichi government quantum investment commitments

3. EXPORT CONTROLS
   - US BIS controls on quantum technology to China
   - EU dual-use regulation updates
   - Impact on cross-border contracts

4. POST-QUANTUM CRYPTOGRAPHY
   - NIST PQC standardization progress
   - Enterprise migration deadlines
   - Implications for quantum-safe business lines

5. STANDARDS BODIES
   - IEEE Quantum Standards
   - ISO/IEC JTC 1 SC 27 quantum cryptography
   - IETF post-quantum TLS

6. SUBSIDIES AND TAX CREDITS
   - CHIPS Act quantum provisions
   - R&D tax credit extensions

Output format (JSON):
{
  "policy_score": 0-100,
  "tailwinds": [list of favorable policy events],
  "headwinds": [list of restrictive actions],
  "pending_catalysts": [list with expected dates],
  "reasoning": "..."
}

Focus on EVENTS that affect specific named companies, not general industry
trends. A DARPA contract to IonQ is actionable; "quantum is strategic" is not.
```

### 7.5 Flow & Technicals Analyst (Haiku 4.5)

```
You analyze institutional positioning and market microstructure for quantum
stocks. You use structured data, not narrative.

Inputs:
- 13F institutional holdings (from SEC EDGAR, quarterly with 45-day lag)
- Short interest reports (FINRA, bi-monthly)
- Options open interest, put/call ratio, and implied volatility — **from moomoo `get_live_options_chain` only** (§4.8.1 forbids yfinance for live IV)
- Trading volume vs 20-day average — **from moomoo historical K-lines** (§4.8.3 `get_historical_klines`)
- Relative strength vs QQQ and sector ETFs — same source

For each stock, report:

1. INSTITUTIONAL FLOW
   - Top 10 holders and their QoQ position change
   - New institutional initiators this quarter
   - Notable exits

2. SHORT INTEREST
   - % of float short
   - Days to cover
   - 30-day change

3. OPTIONS POSITIONING
   - Put/call ratio (open interest-weighted)
   - IV rank (current vs 1-year range)
   - Unusual options activity in last 5 trading days
   - Large block trades

4. TECHNICAL SIGNALS
   - Price vs 50-day SMA, 200-day SMA
   - RS vs QQQ (outperforming/underperforming)
   - Volume spike days in last 30 days

5. SQUEEZE / CROWDING INDICATORS
   - Short squeeze probability (float short % + days to cover + IV rank)
   - Crowdedness (institutional holdings concentration)

Output format (JSON):
{
  "flow_score": 0-100,
  "positioning_bias": "bullish" | "neutral" | "bearish",
  "squeeze_risk": "high" | "medium" | "low",
  "key_observations": [list of 3-5 bullet points]
}
```

### 7.6 Traditional agents (Technical, News, Sentiment, Fundamentals)

Inherit the TradingAgents default prompts. Make these changes:

- **Technical**: use moomoo K-line data exclusively (see Section 4.8.1). yfinance is forbidden for any price used in a buy/sell signal.
- **News**: add quantum media feeds as primary source, NewsAPI as secondary. Output schema (required — the Scoring Engine in §9.3 depends on `strategic_score`):
  ```json
  {
    "headline_summary": "2-3 sentences",
    "strategic_score": 0-100,
    "recent_events": [
      {"event": "...", "impact": "positive|neutral|negative", "ts": "ISO8601"}
    ],
    "reasoning": "..."
  }
  ```
  `strategic_score` = Agent's assessment of *strategic action momentum* (new contracts, partnerships, material 8-Ks). 50 = neutral.
- **Sentiment**: add r/QuantumComputing to the subreddit list. Output schema (required — Scoring Engine depends on `macro_score`):
  ```json
  {
    "sentiment_bias": "bullish|neutral|bearish",
    "macro_score": 0-100,
    "retail_heat": "high|medium|low",
    "reasoning": "..."
  }
  ```
  `macro_score` = macro/sector rotation tailwind for quantum-exposed equities (rates, AI cycle, risk-on vs risk-off). 50 = neutral.
- **Fundamentals**: add RPO, cash runway, and qubit count as explicit fields to extract.

### 7.7 Researchers, Trader, Risk team, Portfolio Manager

Inherit TradingAgents defaults. Modifications:

1. Add the 5 new analyst outputs (Quantum Tech, Commercialization, Valuation Health, Regulatory Policy, Flow) to each agent's context.
2. Portfolio Manager receives additional input: **stage-weighted score** from the Scoring Engine (see Section 9).
3. **Trader system prompt must include this rule** (append to the default TradingAgents trader prompt):

   ```
   DATA SOURCE DISCIPLINE
   All prices, implied volatilities, and order book data you use for
   sizing decisions must come from the moomoo real-time tools
   (get_realtime_quote, get_live_options_chain, get_order_book).
   
   You are forbidden from using any data source labeled "delayed",
   "historical", or "yfinance" when computing entry prices, stop-loss
   levels, or position sizing. If you are unsure of a data point's
   source, call get_realtime_quote again before making a decision.
   
   Historical context from vector store retrieval IS allowed for
   narrative/reasoning purposes, but must not be used as a current price.
   ```

---

## 8. Layer 2: Data pipeline & memory

### 8.1 RSS ingestion (`dataflows/rss_quantum.py`)

```python
import feedparser
import hashlib
from datetime import datetime, timezone
from typing import Iterator

QUANTUM_FEEDS = {
    "quantum_insider": "https://thequantuminsider.com/feed/",
    "quantum_computing_report": "https://quantumcomputingreport.com/feed/",
    "hpcwire_quantum": "https://www.hpcwire.com/category/quantum-computing/feed/",
    "quantum_zeitgeist": "https://quantumzeitgeist.com/feed/",
}

def fetch_all_feeds() -> Iterator[dict]:
    for source_name, url in QUANTUM_FEEDS.items():
        feed = feedparser.parse(url)
        for entry in feed.entries:
            yield {
                "id": hashlib.sha256(entry.link.encode()).hexdigest(),
                "source": source_name,
                "title": entry.title,
                "url": entry.link,
                "summary": entry.get("summary", ""),
                "published_at": entry.get("published_parsed"),
                "fetched_at": datetime.now(timezone.utc),
            }
```

### 8.2 Vector store (`memory/vector_store.py`)

Use ChromaDB with a single collection `market_intel`. Metadata fields: `source`, `tickers`, `published_at` (ISO8601 UTC), `doc_type` (news | filing | paper | contract).

**Embeddings** (Anthropic has no embedding API — pick one):
- **Default: local `sentence-transformers`** with `all-MiniLM-L6-v2` (384-dim, CPU-fast, zero cost). Adequate for the volume of docs in this project.
- **Optional: Voyage AI** (`voyage-3` or `voyage-large-2`) via the `voyageai` Python client, if local quality proves insufficient during Phase 7 backtest. Paid per token. Requires `VOYAGE_API_KEY` in `.env`.
- Do NOT claim "Anthropic embedding API" — it does not exist.

Retention: keep rolling 180 days, purge older.

**Backtest `sim_date` discipline (CRITICAL — prevents look-ahead bias)**:

Every retrieval call that is invoked from the backtest runner must pass a
`sim_date` argument. The retrieval layer enforces `published_at <= sim_date`
via a Chroma `where` filter:

```python
def retrieve(query: str, n: int = 10, sim_date: datetime | None = None,
             tickers: list[str] | None = None) -> list[dict]:
    where: dict = {}
    if sim_date is not None:
        where["published_at"] = {"$lte": sim_date.isoformat()}
    if tickers:
        where["tickers"] = {"$in": tickers}
    return collection.query(query_texts=[query], n_results=n, where=where or None)
```

The backtest runner (§Phase 7) threads `sim_date` through agent calls so that
every RAG lookup honors it. A guardrail test (`tests/backtest/test_no_lookahead.py`)
spot-checks this by asserting that querying at `sim_date = 2024-06-01` never
returns documents with `published_at > 2024-06-01`.

In live mode `sim_date=None`, which means "no cutoff" — the filter is skipped.

### 8.3 Knowledge base (`memory/knowledge_base.py`)

Seed a static KB with quantum industry context that rarely changes:
- Qubit modality comparison table (trapped-ion, superconducting, etc.)
- Key technical thresholds (fidelity > 99.9%, logical error rate < 1e-6)
- Major vendor roadmaps (IBM, Google, IONQ, etc. — update quarterly)
- DARPA program phases and current participants
- NIST PQC standard timeline

This KB is retrieved by the Quantum Tech Expert as RAG context. Store as markdown files under `memory/kb/` and embed them.

### 8.4 Decision log (`memory/decision_log.py`)

SQLite schema:

```sql
CREATE TABLE decisions (
    id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    action TEXT NOT NULL,  -- 'buy' | 'sell' | 'hold'
    size_pct REAL,
    rationale TEXT,
    bull_thesis TEXT,
    bear_thesis TEXT,
    final_score REAL,
    cost_usd REAL,
    model_calls_json TEXT,
    execution_status TEXT,  -- 'paper' | 'live' | 'blocked_by_risk_gate' | 'hold_no_action'
    block_reason TEXT
);

-- Execution + latency tracking (one row per decision, nullable for hold)
CREATE TABLE execution_log (
    decision_id INTEGER PRIMARY KEY,
    ticker TEXT NOT NULL,
    environment TEXT NOT NULL,        -- 'paper' | 'live'
    status TEXT NOT NULL,             -- 'filled' | 'rejected' | 'cancelled' | 'skipped_hold'

    -- Six raw timestamps (UTC, millisecond precision)
    t0_market_tick TEXT,              -- ISO 8601 with ms
    t1_data_fetched TEXT,
    t2_pipeline_start TEXT,
    t3_decision_final TEXT,
    t4_order_submitted TEXT,          -- NULL if hold
    t5_order_filled TEXT,             -- NULL if hold or rejected

    -- Six derived latencies (milliseconds, pre-computed for easy query)
    data_staleness_ms INTEGER,        -- t1 - t0
    pipeline_duration_ms INTEGER,     -- t3 - t2
    submission_latency_ms INTEGER,    -- t4 - t3
    fill_latency_ms INTEGER,          -- t5 - t4
    total_decision_to_fill_ms INTEGER, -- t5 - t2
    total_market_to_fill_ms INTEGER,  -- t5 - t0  (the headline "real-time lag")

    -- Pricing for slippage analysis
    price_at_fetch REAL,              -- price the agents saw
    price_at_submit REAL,             -- price when order hit moomoo
    fill_price REAL,
    slippage_bps REAL,                -- (fill - price_at_fetch) / price_at_fetch * 10000

    -- Order details
    moomoo_order_id TEXT,
    order_qty INTEGER,
    fill_qty INTEGER,

    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);

CREATE INDEX idx_exec_ticker_time ON execution_log(ticker, t3_decision_final);
CREATE INDEX idx_exec_latency ON execution_log(total_market_to_fill_ms);

CREATE TABLE outcomes (
    decision_id INTEGER PRIMARY KEY,
    entry_price REAL,
    exit_price REAL,
    pnl_pct REAL,
    hold_days INTEGER,
    FOREIGN KEY (decision_id) REFERENCES decisions(id)
);
```

Feed outcomes back to the vector store as learning signal for future cycles.

### 8.5 Inter-agent schema contracts (`memory/schemas.py`)

Every agent that produces structured JSON must have a **Pydantic model** in
`memory/schemas.py` that matches the JSON spec in §7. Each agent node in the
LangGraph pipeline **validates its own output** with `Model.model_validate(...)`
before handing off downstream. Validation failures are caught and surfaced
as `data_incomplete: True` (per §4.10 degradation policy) rather than raising
into the graph — one malformed output from one agent must not kill the cycle.

```python
# memory/schemas.py
from typing import Literal
from pydantic import BaseModel, Field

class QuantumTechOutput(BaseModel):
    tech_score: int = Field(ge=0, le=100)
    position_vs_peers: Literal["leader", "competitive", "laggard"]
    roadmap_credibility: Literal["high", "medium", "low"]
    key_risks: list[str]
    time_to_advantage: str
    reasoning: str

class CommercializationOutput(BaseModel):
    commercialization_score: int = Field(ge=0, le=100)
    score_delta_this_cycle: int = Field(ge=-10, le=10)
    dimensions: dict[str, int]
    recent_signals: list[dict]
    reasoning: str

class ValuationHealthOutput(BaseModel):
    financial_health_score: int = Field(ge=0, le=100)
    valuation_tier: Literal["cheap", "fair", "rich", "bubble"]
    runway_quarters: int
    dilution_probability_12m: float = Field(ge=0.0, le=1.0)
    red_flags: list[str]
    reasoning: str

class RegulatoryPolicyOutput(BaseModel):
    policy_score: int = Field(ge=0, le=100)
    tailwinds: list[str]
    headwinds: list[str]
    pending_catalysts: list[dict]
    reasoning: str

class FlowTechnicalsOutput(BaseModel):
    flow_score: int = Field(ge=0, le=100)
    positioning_bias: Literal["bullish", "neutral", "bearish"]
    squeeze_risk: Literal["high", "medium", "low"]
    key_observations: list[str]

class NewsOutput(BaseModel):
    headline_summary: str
    strategic_score: int = Field(ge=0, le=100)
    recent_events: list[dict]
    reasoning: str

class SentimentOutput(BaseModel):
    sentiment_bias: Literal["bullish", "neutral", "bearish"]
    macro_score: int = Field(ge=0, le=100)
    retail_heat: Literal["high", "medium", "low"]
    reasoning: str
```

**Enforcement pattern** (in each agent node):
```python
from pydantic import ValidationError
from tradingagents.memory.schemas import QuantumTechOutput

def quantum_tech_node(state: dict) -> dict:
    raw_json = call_llm(...)  # LLM's structured output
    try:
        parsed = QuantumTechOutput.model_validate_json(raw_json)
        return {"quantum_tech": parsed.model_dump(), "data_incomplete": False}
    except ValidationError as e:
        log.warning(f"quantum_tech validation failed: {e}")
        return {"quantum_tech": None, "data_incomplete": True}
```

Scoring Engine (§9.3) reads only validated outputs, so its `.get(..., 50)`
fallbacks hit only when `data_incomplete is True`. Scoring also multiplies
that dimension's weight by 0.5 when `data_incomplete is True` (per §4.10).

**Unit test** (`tests/unit/test_schemas.py`):
- Golden JSON fixture per agent validates.
- Mutated fixture (missing key, out-of-range value, wrong enum literal)
  fails validation with a clear error.

---

## 9. Scoring engine

### 9.1 Stage detection (`scoring/engine.py`)

```python
def detect_stage(ticker: str, financials: dict) -> str:
    """Detect company maturity stage based on financials."""
    ttm_revenue = financials.get("ttm_revenue_usd", 0)
    revenue_growth_yoy = financials.get("revenue_growth_yoy", 0)
    
    if ttm_revenue < 1_000_000:
        return "pre_revenue"
    elif ttm_revenue < 50_000_000:
        return "early_revenue"
    elif revenue_growth_yoy > 0.5:
        return "scaling"
    else:
        return "established"
```

### 9.2 Dimension weights by stage

```python
STAGE_WEIGHTS = {
    "pre_revenue": {
        "financial_health":    0.40,
        "tech":                0.30,
        "commercialization":   0.05,
        "strategic_actions":   0.10,
        "regulatory":          0.10,
        "macro_rotation":      0.03,
        "technicals_flow":     0.02,
    },
    "early_revenue": {
        "financial_health":    0.25,
        "tech":                0.25,
        "commercialization":   0.25,
        "strategic_actions":   0.10,
        "regulatory":          0.08,
        "macro_rotation":      0.04,
        "technicals_flow":     0.03,
    },
    "scaling": {
        "financial_health":    0.15,
        "tech":                0.15,
        "commercialization":   0.30,
        "strategic_actions":   0.15,
        "regulatory":          0.08,
        "macro_rotation":      0.10,
        "technicals_flow":     0.07,
    },
    "established": {
        "financial_health":    0.20,
        "tech":                0.10,
        "commercialization":   0.20,
        "strategic_actions":   0.10,
        "regulatory":          0.10,
        "macro_rotation":      0.15,
        "technicals_flow":     0.15,
    },
}
```

### 9.3 Compute weighted score

```python
def compute_score(ticker: str, agent_outputs: dict, financials: dict) -> dict:
    stage = detect_stage(ticker, financials)
    weights = STAGE_WEIGHTS[stage]
    
    raw_scores = {
        "financial_health":   agent_outputs["valuation_health"]["financial_health_score"],
        "tech":               agent_outputs["quantum_tech_expert"]["tech_score"],
        "commercialization":  agent_outputs["commercialization"]["commercialization_score"],
        "strategic_actions":  agent_outputs["news"].get("strategic_score", 50),
        "regulatory":         agent_outputs["regulatory_policy"]["policy_score"],
        "macro_rotation":     agent_outputs["sentiment"].get("macro_score", 50),
        "technicals_flow":    agent_outputs["flow_technicals"]["flow_score"],
    }
    
    weighted = sum(raw_scores[k] * weights[k] for k in weights)
    
    return {
        "ticker": ticker,
        "stage": stage,
        "weighted_score": weighted,
        "dimension_scores": raw_scores,
        "weights_applied": weights,
    }
```

---

## 10. Layer 6: Hard risk gate

**This layer is pure Python code. No LLM involvement.** Runs after the Trader+Risk team proposes an action, before the Portfolio Manager gets it.

### `risk/hard_gate.py`

```python
from dataclasses import dataclass
from enum import Enum

class GateResult(Enum):
    PASS = "pass"
    VETO = "veto"
    HALT = "halt_all_trading"

@dataclass
class TradeProposal:
    ticker: str
    action: str  # 'buy' | 'sell' | 'hold'
    size_pct: float  # fraction of portfolio
    
@dataclass
class PortfolioState:
    total_value: float
    positions: dict  # ticker -> dict(pct, unrealized_pnl_pct)
    daily_pnl_pct: float
    cash_pct: float

class HardRiskGate:
    # Hard limits
    MAX_POSITION_PCT = 0.03           # 3% of portfolio per stock
    MAX_QUANTUM_EXPOSURE = 0.15        # 15% total in quantum pure-plays
    DAILY_LOSS_HALT = -0.05           # halt if -5% in a day
    WEEKLY_LOSS_HALT = -0.12          # halt if -12% in a week
    MIN_CASH_PCT = 0.20                # must hold 20% cash minimum
    
    # Valuation guard
    MAX_PS_RATIO_FOR_NEW_BUY = 500    # no new buys if P/S > 500
    
    # Volatility guard
    MAX_IV_FOR_NEW_BUY = 120          # no new buys if IV > 120
    
    # Mandatory cooldown
    MAX_TRADES_PER_DAY_PER_TICKER = 1
    
    def check(
        self,
        proposal: TradeProposal,
        state: PortfolioState,
        market_data: dict,   # MUST come from moomoo (real-time), NOT yfinance
    ) -> tuple[GateResult, str]:
        # Data-source discipline enforcement — see Section 4.8.1
        # market_data for the proposal's ticker must carry _source == "moomoo"
        ticker_data = market_data.get(proposal.ticker, {})
        if ticker_data.get("_source") != "moomoo":
            return GateResult.VETO, "stale_data_rejected_not_from_moomoo"
        
        # Daily loss halt
        if state.daily_pnl_pct <= self.DAILY_LOSS_HALT:
            return GateResult.HALT, "daily_loss_halt_triggered"
        
        # Position cap
        if proposal.action == "buy":
            current_pct = state.positions.get(proposal.ticker, {}).get("pct", 0)
            if current_pct + proposal.size_pct > self.MAX_POSITION_PCT:
                return GateResult.VETO, "position_cap_exceeded"
            
            # Quantum pure-play aggregate cap
            quantum_exposure = sum(
                state.positions.get(t, {}).get("pct", 0)
                for t in ["IONQ", "RGTI", "QBTS", "QUBT"]
            )
            if proposal.ticker in ["IONQ", "RGTI", "QBTS", "QUBT"]:
                if quantum_exposure + proposal.size_pct > self.MAX_QUANTUM_EXPOSURE:
                    return GateResult.VETO, "quantum_aggregate_cap_exceeded"
            
            # Valuation guard
            ps_ratio = ticker_data.get("ps_ratio", 0)
            if ps_ratio > self.MAX_PS_RATIO_FOR_NEW_BUY:
                return GateResult.VETO, f"ps_ratio_too_high_{ps_ratio}"
            
            # Volatility guard (IV from moomoo live options chain)
            iv = ticker_data.get("implied_volatility", 0)
            if iv > self.MAX_IV_FOR_NEW_BUY:
                return GateResult.VETO, f"implied_volatility_too_high_{iv}"
            
            # Cash reserve
            if state.cash_pct - proposal.size_pct < self.MIN_CASH_PCT:
                return GateResult.VETO, "insufficient_cash_reserve"
        
        return GateResult.PASS, "ok"
```

The gate returns one of:
- `PASS`: proposal proceeds to Portfolio Manager
- `VETO`: this specific trade is rejected, log reason, pipeline continues for other tickers
- `HALT`: all trading paused for the day, alert sent to user

---

## 10A. Layer 8: Auto paper execution & latency instrumentation

### 10A.1 Purpose

Every approved non-hold decision MUST automatically submit a paper order to
moomoo's paper trading account. The system records end-to-end latency from
market tick time to order fill, broken down by pipeline stage.

Goals:
1. Measure whether the system is fast enough for daily swing trading (the
   assumed frequency, see Section 2).
2. Detect pipeline performance regressions (if pipeline_duration_ms grows
   from 8 min to 15 min over a month, something is wrong).
3. Measure realistic slippage (the price the agents saw vs. the fill price).
4. Produce the "real-time lag" number the user needs: `total_market_to_fill_ms`.

Auto-execution for `hold` decisions is a no-op; they are still logged with
timestamps T0-T3 to track pipeline latency.

### 10A.2 Timestamps (six raw, UTC millisecond precision)

| Name | Meaning | Who records it |
|------|---------|----------------|
| `T0_market_tick` | Timestamp of the last price tick used in the decision | From moomoo quote response payload |
| `T1_data_fetched` | When the trading system's process received the data | `time.time()` at return of `get_realtime_quote` |
| `T2_pipeline_start` | First LLM call initiated for this ticker | Pipeline entry point |
| `T3_decision_final` | Portfolio Manager output written to decision log | At end of graph.propagate() |
| `T4_order_submitted` | Order submitted to moomoo paper API | Before `place_order` call |
| `T5_order_filled` | moomoo confirmed fill (callback or polled status) | From moomoo fill event |

`T4` and `T5` are `NULL` for hold decisions and for risk-gate-vetoed proposals.

### 10A.3 Derived latencies (pre-computed, stored in ms)

| Field | Formula | What it measures |
|-------|---------|------------------|
| `data_staleness_ms` | `T1 - T0` | Freshness of market data at ingestion. Should be <1000ms with moomoo. |
| `pipeline_duration_ms` | `T3 - T2` | Full agent pipeline cost. Target: 5-10 min. |
| `submission_latency_ms` | `T4 - T3` | Code overhead between decision and order send. Target: <500ms. |
| `fill_latency_ms` | `T5 - T4` | moomoo paper fill latency. Target: <2000ms. |
| `total_decision_to_fill_ms` | `T5 - T2` | Whole operational latency. |
| `total_market_to_fill_ms` | `T5 - T0` | **The headline "real-time lag" metric.** |

### 10A.4 Paper executor (`execution/paper_executor.py`)

```python
import time
from datetime import datetime, timezone
from dataclasses import dataclass
from tradingagents.dataflows import MoomooClient
from tradingagents.memory.decision_log import write_execution_log

@dataclass
class DecisionContext:
    decision_id: int
    ticker: str
    action: str             # 'buy' | 'sell' | 'hold'
    qty: int
    
    # Timestamps captured upstream
    t0_market_tick: datetime
    t1_data_fetched: datetime
    t2_pipeline_start: datetime
    t3_decision_final: datetime
    
    # Price snapshot at data fetch
    price_at_fetch: float

def execute_paper(ctx: DecisionContext, moomoo: MoomooClient) -> dict:
    """Submit a paper order and log every latency component."""
    
    # Skip executions for hold
    if ctx.action == "hold":
        write_execution_log(
            decision_id=ctx.decision_id,
            ticker=ctx.ticker,
            environment="paper",
            status="skipped_hold",
            t0_market_tick=ctx.t0_market_tick,
            t1_data_fetched=ctx.t1_data_fetched,
            t2_pipeline_start=ctx.t2_pipeline_start,
            t3_decision_final=ctx.t3_decision_final,
            t4_order_submitted=None,
            t5_order_filled=None,
            price_at_fetch=ctx.price_at_fetch,
        )
        return {"status": "skipped_hold"}
    
    # Capture T4 immediately before submission
    t4 = datetime.now(timezone.utc)
    
    # Get price at time of submission for additional slippage context
    quote_at_submit = moomoo.get_realtime_quote(ctx.ticker)
    price_at_submit = quote_at_submit["price"]
    
    # Submit paper order
    order_result = moomoo.place_order(
        ticker=ctx.ticker,
        side=ctx.action,
        qty=ctx.qty,
        order_type="market",
        trd_env="SIMULATE",   # moomoo paper trading flag
    )
    
    # Poll or wait for fill (moomoo paper typically fills in <1s)
    fill_info = moomoo.wait_for_fill(order_result["order_id"], timeout_sec=10)
    t5 = datetime.now(timezone.utc)
    
    # Compute latencies (in ms)
    def ms(delta): return int(delta.total_seconds() * 1000)
    
    latencies = {
        "data_staleness_ms":       ms(ctx.t1_data_fetched - ctx.t0_market_tick),
        "pipeline_duration_ms":    ms(ctx.t3_decision_final - ctx.t2_pipeline_start),
        "submission_latency_ms":   ms(t4 - ctx.t3_decision_final),
        "fill_latency_ms":         ms(t5 - t4),
        "total_decision_to_fill_ms": ms(t5 - ctx.t2_pipeline_start),
        "total_market_to_fill_ms":   ms(t5 - ctx.t0_market_tick),
    }
    
    # Slippage
    fill_price = fill_info["fill_price"]
    slippage_bps = (fill_price - ctx.price_at_fetch) / ctx.price_at_fetch * 10000
    
    write_execution_log(
        decision_id=ctx.decision_id,
        ticker=ctx.ticker,
        environment="paper",
        status="filled" if fill_info["status"] == "filled" else fill_info["status"],
        t0_market_tick=ctx.t0_market_tick,
        t1_data_fetched=ctx.t1_data_fetched,
        t2_pipeline_start=ctx.t2_pipeline_start,
        t3_decision_final=ctx.t3_decision_final,
        t4_order_submitted=t4,
        t5_order_filled=t5,
        **latencies,
        price_at_fetch=ctx.price_at_fetch,
        price_at_submit=price_at_submit,
        fill_price=fill_price,
        slippage_bps=slippage_bps,
        moomoo_order_id=order_result["order_id"],
        order_qty=ctx.qty,
        fill_qty=fill_info["fill_qty"],
    )
    
    return {"status": "filled", "latencies": latencies, "slippage_bps": slippage_bps}
```

### 10A.5 Wiring into the graph

Modify `graph/trading_graph.py` so the final step after the Portfolio Manager
is execution, conditioned on the Hard Risk Gate result:

```
PortfolioManager decision
    │
    ├── ENVIRONMENT == "paper" AND action != "hold"
    │         └──→ execute_paper(ctx, moomoo)
    │
    ├── ENVIRONMENT == "live" AND action != "hold"
    │         └──→ execute_live(ctx, moomoo)    # Phase 8+ only
    │
    └── action == "hold" OR risk gate vetoed
              └──→ write_execution_log(status="skipped_hold" or "vetoed")
```

Critical: pass `t0, t1, t2, t3` timestamps through the graph state from the
moment data is fetched until execution. Do not let any node reset them.

### 10A.6 Expected latency budgets

Set alerting thresholds based on these. The green zone for `pipeline_duration_ms`
is the project's MVP target (§16: "Daily pipeline completes in <10 minutes").
Yellow = warning, Red = page the operator.

| Metric | Green | Yellow (warn) | Red (alert) |
|--------|-------|---------------|-------------|
| `data_staleness_ms` | <1,000 | 1,000-3,000 | >3,000 (likely not using moomoo real-time) |
| `pipeline_duration_ms` | <600,000 (10 min — §16 MVP target) | 600,000-720,000 (breaches §16; investigate same day) | >720,000 (12 min; page operator, consider parallelization) |
| `submission_latency_ms` | <500 | 500-2,000 | >2,000 (code issue) |
| `fill_latency_ms` | <2,000 | 2,000-5,000 | >5,000 (moomoo paper issue) |
| `total_market_to_fill_ms` | <650,000 | 650,000-780,000 | >780,000 |

Log each decision's latency; alert Gmail if any value hits red for >10% of
decisions in a rolling 7-day window, OR if yellow persists for 3 consecutive
trading days (indicates drift toward red).

### 10A.7 Daily latency report

`orchestration/latency_report.py` generates a daily report after all decisions
are executed, emailed to the user. Content:

- Per-ticker latency table for today's decisions
- Rolling 30-day p50, p95 for each of the six derived latencies
- Top 3 slowest decisions this week (with drill-down into per-agent timing)
- Any red-zone breaches
- Slippage distribution histogram (bps) across all fills this week

### 10A.8 Latency regression test

In `tests/integration/test_latency_budget.py`:

```python
def test_latency_within_budget():
    """Full pipeline on IONQ with fresh moomoo data must fit budget."""
    result = run_pipeline("IONQ")
    assert result["latencies"]["pipeline_duration_ms"] < 900_000
    assert result["latencies"]["total_market_to_fill_ms"] < 1_000_000
    assert result["latencies"]["data_staleness_ms"] < 3_000
```

This test runs nightly (costs real API $), and blocks merges if latency
has regressed more than 20% vs. 7-day baseline.

### 10A.9 Why paper execution is non-optional

Without actual paper orders hitting moomoo:
- You cannot measure real slippage, only theoretical
- You cannot distinguish between "the decision was good but execution missed"
  vs "the decision was bad"
- Backtests become disconnected from live behavior
- When you eventually flip `ENVIRONMENT=live`, the system has never actually
  submitted an order — unacceptable risk

Paper execution is cheap (moomoo doesn't charge for SIMULATE orders) and
produces data that is required for Phase 6 backtest validation and Phase 7
paper trading.

---

## 11. Layer 0: Orchestration

### 11.1 Scheduler

**ADR (Session 0b)**: scheduling is delegated to the **operating system** via
`cron` (Linux) or `launchd` (macOS). APScheduler is NOT used.

*Why*: APScheduler shares a process with the pipeline, so a pipeline crash
takes out the scheduler — a single point of failure. A solo-dev system cannot
afford a scenario where yesterday's bug silently blocks today's run. Putting
the scheduler under the OS means (a) the daemon is independently supervised,
(b) each day's run starts from a clean Python process, and (c) you can inspect
and modify the schedule without touching Python.

**Entry point** (`tradingagents/daily_cycle.py` — single-shot, no loop):

```python
# tradingagents/daily_cycle.py
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.config.universe import UNIVERSE
from tradingagents.risk.kill_switch import check_kill_switch
from tradingagents.orchestration.alerts import alert_error
from tradingagents.orchestration.cost_tracker import check_daily_budget

def main() -> int:
    check_kill_switch()        # raises SystemExit if /tmp/quantum_agent_kill exists
    check_daily_budget()       # raises if yesterday's spend rolled over somehow
    graph = TradingAgentsGraph()
    for ticker in UNIVERSE:
        try:
            decision = graph.propagate(ticker)
            log_decision(decision)
        except Exception as e:
            alert_error(ticker, e)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
```

**macOS launchd installation** (`~/Library/LaunchAgents/com.user.quantum-agent.plist`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key><string>com.user.quantum-agent</string>
    <key>ProgramArguments</key>
    <array>
      <string>/Users/USER/miniconda3/envs/quantum-agent/bin/python</string>
      <string>-m</string>
      <string>tradingagents.daily_cycle</string>
    </array>
    <key>WorkingDirectory</key><string>/path/to/project</string>
    <key>StartCalendarInterval</key>
    <array>
      <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
      <dict><key>Weekday</key><integer>2</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
      <dict><key>Weekday</key><integer>3</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
      <dict><key>Weekday</key><integer>4</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
      <dict><key>Weekday</key><integer>5</integer><key>Hour</key><integer>8</integer><key>Minute</key><integer>0</integer></dict>
    </array>
    <key>StandardOutPath</key><string>/tmp/quantum-agent.out.log</string>
    <key>StandardErrorPath</key><string>/tmp/quantum-agent.err.log</string>
    <key>EnvironmentVariables</key>
    <dict><key>TZ</key><string>America/New_York</string></dict>
  </dict>
</plist>
```

Load with `launchctl load ~/Library/LaunchAgents/com.user.quantum-agent.plist`.
Unload with `launchctl unload ...`. The pre-market run is 8:00 America/New_York,
~90 min before US market open.

**Linux cron equivalent** (`crontab -e`):
```
# m h dom mon dow command
0 8 * * 1-5 cd /path/to/project && /path/to/env/bin/python -m tradingagents.daily_cycle >> /var/log/quantum-agent.log 2>&1
```
(Set `CRON_TZ=America/New_York` at the top of the crontab on systems that
support it, otherwise adjust the hour to your server's TZ.)

**`orchestration/scheduler.py`** in this codebase is a thin module exposing:
- `validate_schedule_installed() -> bool` — checks `launchctl list` / `crontab -l`
  and returns True if the job is registered, for startup self-diagnostics
- `install_launchd_plist(path)` / `uninstall_launchd_plist(path)` — operator helpers
- Nothing that runs a scheduler in-process.

### 11.2 Kill switch (`risk/kill_switch.py`)

```python
from pathlib import Path

KILL_FILE = Path("/tmp/quantum_agent_kill")

def is_killed() -> bool:
    return KILL_FILE.exists()

def check_kill_switch():
    if is_killed():
        raise SystemExit("Kill switch engaged. Delete /tmp/quantum_agent_kill to resume.")
```

Call `check_kill_switch()` at the start of every pipeline run. User can `touch /tmp/quantum_agent_kill` to immediately halt.

### 11.3 Usage tracker (`orchestration/cost_tracker.py`)

ADR-2026-04-16 后，LLM 调用走 CC 订阅（非 per-token 计费），所以 tracker 从"美元预算熔断"改为"**调用次数 + 并发监控**"。目的：防止单 cycle 失控、早期发现订阅额度触顶。

```python
DAILY_CALL_ALERT = 200          # 每日 claude-CLI 调用数告警阈值
DAILY_CALL_HARD_STOP = 400      # 硬停阈值（防止死循环或失控 retry）
PER_CYCLE_CALL_HARD_STOP = 80   # 单 cycle 最多 80 次 CLI 调用（16 agent × 5 retry 留 buffer）
CLI_MAX_CONCURRENCY = 4         # 避免 429/529：同时并发的 claude 子进程不超过 4

def track_call(model: str, input_tokens: int, output_tokens: int,
               wall_ms: int, cycle_id: str) -> None:
    """
    Log 一次 CLI 调用。input_tokens/output_tokens 从 CLI JSON 输出的 usage 字段读取（如存在）。
    Append 到 SQLite cost_log table: (timestamp, cycle_id, model, input_tokens, output_tokens, wall_ms).
    cost_usd 列保留但置 0（订阅计费模型下无法逐次归算美元）。
    """
    # ...

def check_daily_calls():
    today_calls = _count_today()
    if today_calls > DAILY_CALL_HARD_STOP:
        raise RuntimeError(f"Daily CLI call hard stop hit: {today_calls}")
    if today_calls > DAILY_CALL_ALERT:
        alert_user(f"Daily CLI calls approaching limit: {today_calls}")

def check_per_cycle_calls(cycle_id: str):
    calls = _count_cycle(cycle_id)
    if calls > PER_CYCLE_CALL_HARD_STOP:
        raise RuntimeError(f"Per-cycle call hard stop hit: {calls}")
```

**Subscription rate-limit awareness**：CC 订阅的 5 小时滚动窗口上限官方未公开。若遇 429/529 → 退避 + 告警，不要重试风暴。`CLI_MAX_CONCURRENCY` 从 4 起步，出问题降。

### 11.4 Alerts (`orchestration/alerts.py`)

Prefer Gmail via MCP (user has this configured). Fallback: Slack webhook.

```python
def alert_decision(decision: dict):
    """Send decision summary to user after each cycle."""
    # ...

def alert_error(ticker: str, error: Exception):
    """Critical error - immediate notification."""
    # ...

def alert_cost(amount_usd: float):
    """Cost threshold breached."""
    # ...
```

---

## 12. Configuration

### `.env` file

```bash
# LLM: ADR-2026-04-16 起走 `claude` CLI 订阅模式，不再需要 ANTHROPIC_API_KEY
# 前置：确保 `claude --version` 能跑，且 `claude login` 已完成（~/.claude/auth 存在）

# Free-tier APIs
NEWSAPI_KEY=...              # https://newsapi.org/ free tier
SAM_GOV_API_KEY=...          # https://sam.gov/ free registration
REDDIT_CLIENT_ID=...         # https://www.reddit.com/prefs/apps free
REDDIT_CLIENT_SECRET=...
REDDIT_USER_AGENT=QuantumTradingAgent/0.1

# SEC (no key needed, but required User-Agent)
SEC_USER_AGENT=QuantumTradingAgent research@example.com

# moomoo (user's existing setup)
MOOMOO_HOST=127.0.0.1
MOOMOO_PORT=11111
MOOMOO_TRADE_PASSWORD=...    # encrypted trade unlock code

# Alerting
GMAIL_TO=user@example.com
SLACK_WEBHOOK_URL=...        # optional

# Operational
DAILY_CALL_ALERT=200         # CLI 调用次数告警（见 §11.3）
DAILY_CALL_HARD_STOP=400     # CLI 调用次数硬停
PER_CYCLE_CALL_HARD_STOP=80  # 单 cycle 最大调用数
CLI_MAX_CONCURRENCY=4        # 并发 claude 子进程上限
ENVIRONMENT=paper            # 'paper' | 'live'
```

### Batch API（原注）

原 SPEC 推荐 Phase 7 回测用 Anthropic Message Batches API（5 折）。**ADR-2026-04-16 暂缓**：Phase 7 回测已延后；回测上马时再重评估（要么单独开 Anthropic API 账单跑回测，要么用 CLI 串行分批）。

---

## 13. Implementation phases

Execute in order. Do not skip phases.

### Phase 1: Scaffold (target: 1 week)

- [ ] Fork `TauricResearch/TradingAgents` on GitHub
- [ ] Clone locally, create `quantum-fork` branch
- [ ] Create Python 3.13 env via `uv venv --python 3.13 .venv` (or conda — §2 ADR-2026-04-16: uv OK)
- [ ] `pip install -r requirements.txt` + added deps
- [ ] 验证 `claude` CLI 可用且 `claude login` 已完成（**不需要** `ANTHROPIC_API_KEY`，见 §6 ADR-2026-04-16）
- [ ] Create `tradingagents/config/model_config.py` per Section 6
- [ ] Modify `tradingagents/graph/setup.py` to use per-agent CLI invocations via `run_claude(...)`
- [ ] Test baseline: run pipeline on NVDA with existing 4 analysts; verify decision JSON（CLI 模式，无 API 费用）
- [ ] Create `tests/unit/test_model_config.py`

**Exit criteria**: `python main.py NVDA 2026-04-15` produces a decision JSON（CLI 调用走 CC 订阅）。

### Phase 2: Data layer (target: 2 weeks)

- [ ] Implement `dataflows/moomoo_client.py` wrapping user's moomoo setup (FIRST — everything depends on this)
- [ ] Verify every moomoo return dict carries `_source: "moomoo"` tag
- [ ] Implement `dataflows/historical.py` as the ONLY place yfinance lives
- [ ] Wire `dataflows/__init__.py` per Section 4.8.2 (expose moomoo methods, isolate yfinance)
- [ ] Write `tests/unit/test_no_yfinance_on_hot_path.py` guardrail test (Section 4.8.2) and verify it passes
- [ ] Implement `dataflows/rss_quantum.py` with 4 RSS feeds
- [ ] Implement `dataflows/arxiv_client.py`
- [ ] Implement `dataflows/sec_edgar.py` with CIK lookup, 10-Q parsing, 13F parsing
- [ ] Implement `dataflows/newsapi_client.py` with rate limiting and caching
- [ ] Implement `dataflows/reddit_client.py` via PRAW
- [ ] Implement `dataflows/sam_gov.py`
- [ ] Implement `memory/vector_store.py` with ChromaDB
- [ ] Implement `memory/knowledge_base.py` with seed markdown files
- [ ] Implement `memory/decision_log.py` with SQLite schema

**Exit criteria**: All data sources fetch-able via unified interface, stored in vector store with metadata. Guardrail test passes: no yfinance on decision path.

### Phase 3: New agents (target: 2 weeks)

- [ ] Create `agents/analysts/quantum_tech_expert.py` with full prompt from Section 7.1
- [ ] Create `agents/analysts/commercialization.py` with prompt from Section 7.2
- [ ] Create `agents/analysts/valuation_health.py` with prompt from Section 7.3
- [ ] Create `agents/analysts/regulatory_policy.py` with prompt from Section 7.4
- [ ] Create `agents/analysts/flow_technicals.py` with prompt from Section 7.5
- [ ] Update `graph/trading_graph.py` to include new agents in parallel analyst phase
- [ ] Update Bull/Bear researchers to consume new agent outputs in their prompts
- [ ] Update Portfolio Manager prompt to receive stage-weighted score

**Exit criteria**: Running pipeline on IONQ produces outputs from all 9 agents in JSON.

### Phase 4: Scoring & risk gate (target: 1 week)

- [ ] Implement `scoring/engine.py` with stage detection + weighted scoring
- [ ] Implement `scoring/dimensions.py` with score normalization per dimension
- [ ] Implement `risk/hard_gate.py` with all 6 rules
- [ ] Implement `risk/kill_switch.py`
- [ ] Integrate gate between Risk team output and Portfolio Manager input
- [ ] Write `tests/unit/test_hard_gate.py` covering all veto/halt paths

**Exit criteria**: A forced-fail proposal (e.g., 10% position size) gets veto'd with correct reason.

### Phase 5: Auto paper execution & latency (target: 2 weeks — revised from 1 week, Session 0b)

**This phase implements Section 10A.** Do not skip even in early development —
paper execution is how you validate everything before Phase 6.

- [ ] Extend `memory/decision_log.py` with `execution_log` table schema (see Section 8.4)
- [ ] Implement `execution/paper_executor.py` per Section 10A.4
- [ ] Ensure `MoomooClient` supports `trd_env="SIMULATE"` for paper orders
- [ ] Implement `MoomooClient.wait_for_fill()` with timeout
- [ ] Thread T0-T5 timestamps through LangGraph state (do not let any node reset them)
- [ ] Wire execution step into `graph/trading_graph.py` after Portfolio Manager
- [ ] Implement `orchestration/latency_report.py` for daily email digest
- [ ] Write `tests/unit/test_paper_executor.py` with mocked moomoo client
- [ ] Write `tests/integration/test_latency_budget.py` (Section 10A.8)

**Exit criteria**: Running pipeline on IONQ submits a paper order to moomoo, 
`execution_log` row is written with all 6 timestamps and 6 derived latencies, 
daily latency report is generated.

### Phase 6: Orchestration (target: 1 week)

- [ ] Implement `tradingagents/daily_cycle.py` + `orchestration/scheduler.py` helper; install launchd plist / cron entry per §11.1
- [ ] Implement `orchestration/cost_tracker.py` with SQLite persistence
- [ ] Implement `orchestration/alerts.py` via Gmail MCP
- [ ] Implement `orchestration/monitor.py` for log aggregation
- [ ] Configure tool permissions pre-approval for unattended runs
- [ ] Hook latency report (from Phase 5) into daily alert

**Exit criteria**: Schedule daily run at 8:00 EST, decisions appear in Gmail inbox, cost tracked in SQLite, latency report attached.

### Phase 7: Backtest (target: 2-4 weeks) — **[DEFERRED — ADR-2026-04-16 scope cut]**

> 用户 2026-04-16 决定先不做回测。本阶段保留为 future roadmap，实际启动前需重评估：
> - CLI 订阅模式下长回测（~9000 次调用）的速率瓶颈
> - 或单独开 Anthropic API 账单 + Message Batches（5 折）跑一次性回测


- [ ] Implement `backtest/runner.py` using `vectorbt` (Session 0b ADR; backtrader removed from requirements)
- [ ] Historical data: at least Jan 2024 → present (captures quantum rally + drawdown)
- [ ] Freeze agent knowledge cutoff per simulation date (no look-ahead)
- [ ] Compute: Cumulative Return, Annualized Return, Sharpe Ratio, Max Drawdown, Win Rate, Avg Hold Period
- [ ] Compare against: Buy & Hold, MACD, SMA strategies (TradingAgents baselines)
- [ ] Compare backtest slippage assumptions against actual paper slippage from Phase 5 log
- [ ] Document results in `results/backtest_v1.md`

**Exit criteria**: 12 months of backtest complete. SR > 1.5 AND MDD < 25% to proceed.

### Phase 8: Live paper validation (target: 30 days) — **[DEFERRED — ADR-2026-04-16]**

> 依赖 Phase 7 回测结果决定是否启动。保留为 future roadmap。


- [ ] Ensure paper execution (Phase 5) is running daily
- [ ] Daily report to Gmail with positions, P&L, agent rationale, and latency stats
- [ ] Review all vetoed proposals (weekly)
- [ ] Review slippage trends (weekly): is there drift from backtest assumptions?
- [ ] Review latency trends: any regression from Phase 5 baseline?
- [ ] Tune prompts and weights based on paper performance

**Exit criteria**: 30-day paper Sharpe > 1.0 AND max drawdown < 15% AND median `total_market_to_fill_ms` stable within 20% of Phase 5 baseline. User approval required before Phase 9.

### Phase 9: Small live (target: ongoing) — **[DEFERRED — ADR-2026-04-16]**

> 真钱上线前必须通过 Phase 7 回测 + Phase 8 paper 验证。保留为 future roadmap。


- [ ] Switch `ENVIRONMENT=live` in `.env`
- [ ] Cap total quantum exposure at 5% of portfolio initially (not 15%)
- [ ] Run for 3 months at small size
- [ ] Monthly review with user, incrementally raise caps if performance validates

**Exit criteria**: ongoing. Never exceed 15% total quantum exposure.

---

## 14. Testing strategy

### Unit tests (`tests/unit/`)

- Each agent tested with mocked tool outputs. Feed synthetic inputs, assert output schema.
- `test_hard_gate.py`: cover every veto and halt path, including the new `stale_data_rejected_not_from_moomoo` veto.
- `test_scoring_engine.py`: verify stage detection thresholds and weight application.
- `test_rss_quantum.py`: mock feedparser response, verify deduplication.
- **`test_no_yfinance_on_hot_path.py`** (CRITICAL — enforces Section 4.8.1): AST-scans `agents/`, `risk/`, `scoring/`, `orchestration/`, and `execution/` and fails if any file imports yfinance. See Section 4.8.2 for implementation.
- **`test_graceful_degradation.py`** (enforces §4.10): simulates failure of CRITICAL / IMPORTANT / OPTIONAL tier sources and asserts correct pipeline behavior per tier.
- **`test_schemas.py`** (enforces §8.5): golden + mutated JSON fixtures per agent, asserting Pydantic validation catches malformed LLM output.
- `test_moomoo_source_tag.py`: verify `MoomooClient` return dicts always include `_source: "moomoo"`.

### Integration tests (`tests/integration/`)

- `test_full_pipeline_ionq.py`: run complete 8-layer pipeline on IONQ with fixed date. Verify:
  - All 9 agents produce output
  - Bull/Bear debate completes 2 rounds
  - Risk gate evaluates
  - Decision JSON is well-formed
  - **Paper order is submitted to moomoo SIMULATE and filled**
  - **execution_log row is created with all 6 timestamps and 6 derived latencies**
  - Total cost < $5.00 for single decision (Session 0b: relaxed from $2.50 — observed cost with Opus PM + Opus Quantum Tech Expert at thinking_budget=16000 routinely lands in the $3-4 range; $2.50 was unrealistic)
- `test_latency_budget.py` (Section 10A.8): assert `total_market_to_fill_ms` within budget
- `test_hold_decision_logging.py`: hold decisions still log T0-T3 but T4/T5 null

### Backtest tests (`tests/backtest/`)

- `test_no_lookahead.py`: verify agents only receive data up to simulation date
- `test_reproducibility.py`: same inputs produce same outputs (with seed)

Run unit tests in CI on every commit. Integration tests nightly (they cost real money).

---

## 15. Known limitations & caveats

Document these in README so user is aware:

1. **NewsAPI 100 req/day limit**: may miss events during high-news days. Consider upgrading to paid tier ($449/mo) only if backtesting shows Sharpe degradation without full coverage.
2. **SEC EDGAR 45-day 13F lag**: institutional positioning is always backward-looking.
3. **RSS feeds can be down**: implement graceful degradation — pipeline should proceed with partial data if 1-2 feeds fail.
4. **Quantum stocks are extremely volatile**: backtests over < 2 years are unreliable. Prefer longer history even if system wasn't live.
5. **moomoo paper ≠ live**: slippage and partial fills behave differently. Paper Sharpe will overestimate live performance by ~20-30%.
6. **LLM non-determinism**: same inputs can yield different outputs. Set `temperature=0` for reproducibility in backtests. Use `temperature=0.3` in live for slight exploration.

---

## 16. Success metrics

### Minimum viable

- [ ] All 9 agents operational
- [ ] Daily pipeline completes in < 10 minutes (= §10A.6 green zone for `pipeline_duration_ms`)
- [ ] Cost per decision < $5.00 (Session 0b revision; see §14)
- [ ] Hard risk gate vetoes at least one proposal in backtest (proves it works)

### Good

- [ ] 12-month backtest SR > 1.5
- [ ] 30-day paper SR > 1.0
- [ ] Max drawdown < 20% in backtest
- [ ] Commercialization score correctly flags top performer (e.g., IONQ > QUBT over 2025)

### Exceptional

- [ ] Beats Buy & Hold on all 4 quantum pure-plays by 20%+ annualized
- [ ] Correctly sidestepped the Jan 2026 quantum drawdown in paper trading
- [ ] Commercialization signals lead stock moves by > 3 trading days

---

## 17. Appendix: useful references

- **TradingAgents paper**: https://arxiv.org/abs/2412.20138
- **TradingAgents repo**: https://github.com/TauricResearch/TradingAgents
- **Anthropic API docs**: https://docs.claude.com/en/api/overview
- **Effort parameter**: https://docs.claude.com/en/docs/build-with-claude/effort
- **SEC EDGAR API**: https://www.sec.gov/edgar/sec-api-documentation
- **SAM.gov API**: https://open.gsa.gov/api/get-opportunities-public-api/
- **NewsAPI**: https://newsapi.org/docs
- **moomoo OpenAPI**: https://openapi.futunn.com/

### Key analyst reports to mirror in reasoning style

- Mizuho (Vijay Rakesh) — most influential quantum analyst on the sell side
- Rosenblatt Securities — balanced bull/bear coverage
- TD Cowen — technical depth

### Key quantum industry conferences to watch for catalysts

- Q2B (IEEE Quantum) — December
- APS March Meeting — March
- IEEE Quantum Week — September
- Qubits (D-Wave conference) — January

---

## 18. How to use this spec with Claude Code

1. Place this file at project root as `SPEC.md`
2. Start Claude Code session: `claude`
3. Prompt: `Read SPEC.md end to end. Then execute Phase 1 tasks, committing after each checkbox. Ask before starting Phase 2.`
4. Review each phase output before approving the next

Phases 1-4 can be largely autonomous. Phase 5 onward requires operational access (credentials, scheduling, real accounts) and should be supervised.

### Recommended Claude Code settings

```json
// .claude/settings.json
{
  "permissions": {
    "defaultMode": "acceptEdits"
  },
  "env": {
    "ANTHROPIC_MODEL": "claude-opus-4-6"
  }
}
```

When iterating on the Quantum Tech Expert agent prompt, start Claude Code with Opus 4.6 so prompt-design reasoning has the budget it needs. There is no `--effort max` flag; the equivalent is simply choosing Opus plus (in code) raising `thinking_budget` in `AGENT_MODEL_MAP`.

---

**End of spec. Total estimated implementation time: 8-12 weeks to Phase 7 completion.**
