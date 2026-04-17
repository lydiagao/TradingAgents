# Claude Code 项目规则 — Quantum Trading Agent

本文件为本项目的长期规则。Claude Code 在每次 session 都必须遵守。
如与默认行为冲突，本文件优先。

---

## 任务与进度管理

1. **每完成一个任务，立刻更新 `TASKS.md`**
   - 勾选对应复选框（`[ ]` → `[x]`）
   - 重新计算并更新顶部 "进度摘要" 里的完成数和百分比
   - 不要批量勾选；一个任务一次更新

2. **每当调整或改良计划，同步更新 `TASKS.md`**
   - 新增任务 → 插入到对应 session，标记为 `[ ]`
   - 任务被拆分 / 合并 / 删除 → 立刻反映到 `TASKS.md`
   - 调整顺序 → 重排并在变更备注里写原因
   - `PROGRESS.md` 与 `SESSION_PLAN.md` 如有冲突，以最新修订为准，并在 `TASKS.md` 的备注区注明

3. **每个 session 开始和结束都更新顶部进度摘要**
   - Session 开始：
     - 更新 "当前 Session" 字段
     - 将本 session 要做的任务状态从 `[ ]` 改为 `[~]`（进行中）
     - 写入 session 开始时间（UTC）
   - Session 结束：
     - 更新完成数 / 百分比
     - 将完成的任务状态改为 `[x]`
     - 将未完成但曾动过的任务保留 `[~]` 并写原因
     - 写入 session 结束时间（UTC）和本次提交哈希

---

## Git 纪律

4. **发现方向有误，主动 `git` 回溯**
   - 不要在错误的实现基础上继续叠加补丁
   - 回溯方式优先级：
     - (a) 未提交 → `git restore` / `git checkout --` 目标文件
     - (b) 已提交但未 push → `git reset --hard <good-sha>` 或 `git revert`
     - (c) 已 push → `git revert`（保留历史）
   - **回溯前**：告知用户回溯原因 + 目标 SHA，等待确认再执行（destructive 操作需确认）
   - **回溯后**：在 `TASKS.md` 对应任务下追加一行 `> ROLLBACK <date>: <原因> — 回到 <sha>`

5. **每完成一个任务，立刻 `git commit`**
   - 一个任务对应一个 commit（不要把 P1-T3 和 P1-T5 合并提交）
   - Commit message 格式：`feat(P{phase}-T{n}): <任务标题>` 或 `chore(P{phase}-T{n}): ...`
     - 功能实现 → `feat`
     - 配置 / 文档 / 环境 → `chore`
     - 修复 → `fix`
     - 测试新增 → `test`
   - Message body 应包含：完成了什么、对应 SPEC 章节、验证方式
   - 示例：
     ```
     feat(P1-T6): create tradingagents/config/model_config.py

     - AGENT_MODEL_MAP with 16 agent keys per SPEC §6
     - get_model_config() + build_thinking_param() helpers
     - Validates via tests/unit/test_model_config.py (P1-T10)
     ```

---

## 交叉约束（源自 SPEC，贴在这里便于每次 session 快速回顾）

- **模型 ID**：只用 `claude-opus-4-6` / `claude-sonnet-4-6` / `claude-haiku-4-5-20251001`。不存在 "claude-opus-4-7"。
- **Thinking 参数**：`thinking={"type": "enabled", "budget_tokens": N}`。没有 `effort` 字段，不要编造。
- **数据来源纪律（§4.8）**：`agents/` `risk/` `scoring/` `orchestration/` `execution/` 目录**禁止**导入 `yfinance`。P2-T5 的守卫测试从 Phase 2 起每次提交都要通过。
- **延迟埋点（§10A）**：`MoomooClient` 从 Phase 2 起打 T0 / T1；T2-T5 从 Phase 5 起通过 LangGraph state 传递。任何节点不得改写已存在的时间戳。
- **优雅降级（§4.10）**：CRITICAL 源失败 → 停该 ticker；IMPORTANT → 置信度降权重 × 0.5；OPTIONAL → 静默跳过。

---

## Session 交接

- Session 结束时，在 `TASKS.md` 底部写一段 "Session 交接" 短文：
  - 本次完成的任务 ID
  - 遗留的 blocker（等用户决策 / 等外部资源）
  - 下一个 session 开始时的第一个动作
- 下一个 session 开始时，先读 `TASKS.md` 顶部摘要 + 最后一段 "Session 交接"，再读 `PROGRESS.md` 和 `SPEC.md` 的相关章节。

---

## 例外

- 本文件的规则可以被**用户在对话中的显式指令**覆盖（例如 "这次先不要 commit"）。
- 规则的**修改**必须由用户明确同意后才能改 `CLAUDE.md`。
