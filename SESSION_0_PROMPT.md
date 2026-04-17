# Session 0 Prompts — Project Kickoff

> Paste these prompts into Claude Code to bootstrap the project.
> Save this file alongside `SPEC.md` at your project root.

---

## How to use

1. Place `SPEC.md` and this file at your project root
2. Start Claude Code: `claude`
3. Run the environment check first (below)
4. Run Session 0a (optional but recommended)
5. Run Session 0b (required)
6. Review the produced `SESSION_PLAN.md` and `PROGRESS.md`
7. `/clear` and start Session 1 using the briefing prompt from `SESSION_PLAN.md`

---

## Environment check (run first, ~5 min)

```
Before we start, verify the environment:
1. Run `pwd` and confirm we're in the project root
2. Run `git status` and show what's tracked
3. Run `python --version` and confirm Python 3.13+
4. Run `ls -la` and confirm SPEC.md and SESSION_0_PROMPT.md exist
5. Check if a TradingAgents fork is already in place
   (look for tradingagents/graph/trading_graph.py)
6. Run `cat .claude/settings.json` and show permission config

Report each result. Then wait for my next instruction.
Do not write any files in this session.
```

---

## Session 0a — SPEC feasibility review (optional, ~15 min)

Run this if you want to catch SPEC issues before planning. Recommended for a first-time project.

```
Read SPEC.md completely. Do not write any code or planning artifacts yet.

The SPEC has a "Revision notes" block at the top listing hardened
requirements. Pay attention to those before reviewing the rest.

Give me a candid review:

1. Any parts of the spec that are internally contradictory?
2. Any parts that are underspecified and would force you to make
   assumptions during implementation?
3. Any parts you think are over-engineered for a solo project?
4. Any parts you think are missing and critical?
5. Any tech choices you'd push back on?
6. Any concerns specifically about the two cross-cutting requirements:
   - Section 4.8 moomoo data discipline
   - Section 10A latency instrumentation
   Are these well-integrated across the spec or patched on?

Be direct. Don't sugarcoat. This is the last chance to change the SPEC
before we commit to implementing it.

Format: numbered list, one concern per item, with SPEC section reference.
```

After review, decide whether to revise `SPEC.md` or proceed.

---

## Session 0b — Full planning (required, ~30 min)

```
Read SPEC.md end-to-end. Do not write any code yet.

The SPEC has a "Revision notes" block at the top listing hardened
requirements (Section 4.8 data discipline, Section 10A auto execution
and latency). Pay special attention to these — they are non-negotiable
constraints that cut across many sessions.

Your task in this session is to produce two planning artifacts and one
self-review.

---

ARTIFACT 1: PROGRESS.md

A living checklist mirroring SPEC Phase 1-9 tasks. Each task gets:
- [ ] checkbox
- Unique ID (e.g., P2-T3)
- Exit definition ("done looks like...")
- Cross-reference to the SPEC section it implements

---

ARTIFACT 2: SESSION_PLAN.md

A breakdown of the project into discrete Claude Code sessions.
Apply these constraints:

a. Each session independently completable in one working day
   (4-8 hours of Claude Code time).

b. Each session touches at most 5-8 files. More than that means
   split it further.

c. Dependencies explicit: session N cannot depend on work in
   session N+1 or later.

d. For each session, specify:
   - Session ID and name
   - Prerequisites (prior sessions required)
   - Files to create or modify (exact paths from SPEC Section 5)
   - Exit criteria (tests passing, commits made)
   - Estimated context window usage (small / medium / large)
   - Recommended Claude model (Sonnet 4.6 for routine code,
     Opus 4.7 for agent prompt design in Sections 7.1-7.5)
   - A standard briefing prompt I can paste when starting that session
   - Explicit SPEC sections the session must reference

e. Identify which sessions are PARALLELIZABLE vs SEQUENTIAL.

f. Identify HIGH RISK sessions (likely to need revisit) vs LOW RISK.

g. CRITICAL — treat these as cross-cutting concerns, not single sessions:

   (i) Data source discipline (SPEC Section 4.8):
       Every session that touches dataflows/, agents/, risk/, scoring/,
       or orchestration/ must respect the moomoo-only rule for live
       decisions. The guardrail test test_no_yfinance_on_hot_path.py
       must be introduced early (in the MoomooClient session) and run
       in CI from that point on.

   (ii) Latency instrumentation (SPEC Section 10A):
        T0-T5 timestamps must be threaded through LangGraph state
        from Session 2 (MoomooClient adds T0/T1 tagging) onward.
        Any session that touches graph state must preserve them.
        Do not defer all latency work to Phase 5 — the hooks must
        exist earlier.

h. Give MoomooClient its own dedicated early session because it is
   a hard dependency for risk gate, execution, and data discipline.
   It is the structural keystone — do not lump it into a generic
   "data sources" session.

i. Give the three novel agents (Quantum Tech Expert, Commercialization,
   Valuation & Health) their OWN sessions each, using Opus 4.7 high
   effort. Their prompts are the hardest work in this project.

---

ARTIFACT 3: self-review (in chat, not file)

After writing the two files, answer these questions directly:

1. Total session count and critical path length
2. Any sessions >200K tokens of context? (if yes, split)
3. Any circular or unclear dependencies?
4. Did you plan a session specifically for:
   - test_no_yfinance_on_hot_path.py guardrail
   - execution_log schema + paper_executor.py
   - latency_report.py daily digest
   If not, why not?
5. Any gaps or contradictions you found in SPEC.md during planning?
   (I wrote the SPEC across multiple revisions and some inconsistencies
   are likely.)
6. Which sessions are you least confident about? Why?
7. If I only had 2 weeks of dev time, which sessions would be the
   minimum viable subset?

---

OUTPUT

Write PROGRESS.md and SESSION_PLAN.md at repo root.
Commit with: "chore: session plan and progress tracker".
Then post your self-review in chat.

Do not start Session 1 in this session. After review, I will /clear
and start Session 1 fresh.
```

---

## After Session 0 — what to do next

1. Read `SESSION_PLAN.md` carefully
2. If anything looks wrong (session too big, wrong dependencies, missing cross-cutting concerns), tell Claude Code to revise — that is still part of Session 0, not Session 1
3. When `SESSION_PLAN.md` is approved, `/clear` to free context
4. Start Session 1 by pasting its briefing prompt from `SESSION_PLAN.md`
5. Each subsequent session: `/clear`, paste the next briefing prompt

---

## Tips for running sessions

- **Do not let a session run past its exit criteria.** If Claude Code wants to "just quickly also do X", say no. X belongs to its own session.
- **Always commit at the end of each session.** Clean git history is how you recover when something goes wrong.
- **After every 3 sessions, run a short orchestrator check**:
  ```
  Read SESSION_PLAN.md, PROGRESS.md, and the last 15 commits.
  Are we on track? Any drift from the plan? Any gaps in test coverage?
  Don't write code; just report.
  ```
- **When tuning agent prompts (Sessions 5-7 for the novel agents), budget multiple sessions per agent.** The first session gets it running; subsequent sessions iterate on prompt quality using real output.

---

## Claude model recommendations per session type

| Session type | Model | Effort |
|--------------|-------|--------|
| Planning (Session 0) | Opus 4.7 | high |
| Scaffolding, config, wiring | Sonnet 4.6 | high |
| Routine agent (4 inherited TradingAgents agents) | Sonnet 4.6 | medium |
| Novel agent prompt design (Quantum Tech, Commerce, Valuation) | Opus 4.7 | high |
| Data source integration (RSS, SEC, Reddit, etc.) | Sonnet 4.6 | medium |
| Testing, CI, guardrails | Sonnet 4.6 | medium |
| Backtest framework | Sonnet 4.6 | high |
| Orchestrator check (every 3 sessions) | Sonnet 4.6 | high |
| Debugging production issues | Opus 4.7 | max |

Cost budget guidance: Opus 4.7 high-effort sessions are ~5x the cost of Sonnet
medium sessions. Reserve Opus for the 3-4 sessions that truly need it
(planning, novel agent prompts, hard bugs).
