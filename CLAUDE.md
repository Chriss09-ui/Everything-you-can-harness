# 司南 Harness Builder — Contributor Context

## One-Screen Summary

司南是一个用 LangGraph 编排的三层系统：**需求层**与用户制定完整需求契约，**架构层**把需求转成经过审查的 harness 设计稿，**研发层**把设计稿变成可运行的代码。

## Canonical Workflow

### Requirement Layer (需求层)

`spec_expansion` → `spec_challenge` → `brief_debate` → `sinan_debrief` → `brief_compile`

拓谱 → 诘问 → 辩论 → 用户确认 → 需求契约定稿。`brief_compile` 输出的 `user_brief_form.json` 是需求契约，作为进入架构层的前提。

### Architecture Layer (架构层)

`framework_design` → `subagent_review` → `framework_adjust` → `zonggong_integrate` → `architecture_challenge` → `approval_gate` → `sinan_approval` / `final_spec`

四步辩论框架设计 → 子代理评审 → 框架调整 → 综合集成 → 架构挑战审查 → 审批门（低风险自动通过，高风险用户审批）→ `arch_revise` on rejection → `final_spec`。

### Coding Layer (研发层)

嵌套循环结构，由 `src/sinan/coding/graph.py` 定义：

```
planner → sprint_plan → sprint_negotiate → sprint_setup
  → session_init → session_setup
  → sanity_check
    ├─ pass → pick_feature → implement_feature → test_feature
    │         → commit_feature → (more? → pick_feature) → generator_review
    │                                                     → evaluator_qa
    │                                                       ├─ pass → sprint_complete
    │                                                       └─ fail → evaluator_bugs → generator_fix → (self-test)
    └─ fail → bug_triage → session_setup
```

- **Sprint Loop**: 最多 10 轮，每轮含 negotiation (≤3 轮)
- **Session Loop**: 每次 session 重置上下文，读取磁盘 artifact 恢复
- **Feature Loop**: 按优先级实现 feature，失败走 Fix Loop
- **Fix Loop**: 最多 2 轮自修复 + 自测

Coding layer definition: [src/sinan/coding/graph.py](/Users/chriss/Desktop/harness/src/sinan/coding/graph.py)

## Core Files

### Requirement + Architecture Layer (需求层 + 架构层)

- [src/sinan/cli.py](/Users/chriss/Desktop/harness/src/sinan/cli.py): terminal entrypoint (runs design → coding sequentially)
- [src/sinan/state.py](/Users/chriss/Desktop/harness/src/sinan/state.py): design layer state schema
- [src/sinan/graph.py](/Users/chriss/Desktop/harness/src/sinan/graph.py): requirement + architecture layer graph
- [src/sinan/nodes/NODES.md](/Users/chriss/Desktop/harness/src/sinan/nodes/NODES.md): **Node 合约参考文档** — 需求层+架构层每个 node 的 Reads/Writes/Artifacts/Routes
- [src/sinan/artifacts.py](/Users/chriss/Desktop/harness/src/sinan/artifacts.py): run folders, logs, versioned artifact writes
- [src/sinan/llm.py](/Users/chriss/Desktop/harness/src/sinan/llm.py): mock and provider adapters
- [src/sinan/mock_responses.py](/Users/chriss/Desktop/harness/src/sinan/mock_responses.py): deterministic mock outputs
- [src/sinan/prompts.py](/Users/chriss/Desktop/harness/src/sinan/prompts.py): role prompts

### Coding Layer

- [src/sinan/coding/](/Users/chriss/Desktop/harness/src/sinan/coding/): coding layer package
- [src/sinan/coding/NODES.md](/Users/chriss/Desktop/harness/src/sinan/coding/NODES.md): **Node 合约参考文档** — 每个 node 的 Reads/Writes/Artifacts/Routes 一目了然
- [src/sinan/coding/state.py](/Users/chriss/Desktop/harness/src/sinan/coding/state.py): `CodingState` TypedDict + `make_coding_state()`
- [src/sinan/coding/graph.py](/Users/chriss/Desktop/harness/src/sinan/coding/graph.py): 17 nodes, 6 conditional routers
- [src/sinan/coding/prompts.py](/Users/chriss/Desktop/harness/src/sinan/coding/prompts.py): Planner / Generator / Evaluator / Initializer / Negotiator prompts
- [src/sinan/coding/git.py](/Users/chriss/Desktop/harness/src/sinan/coding/git.py): thin git subprocess wrappers
- [src/sinan/coding/testing.py](/Users/chriss/Desktop/harness/src/sinan/coding/testing.py): E2E test abstraction (Playwright + fallback)
- [src/sinan/coding/mock_responses.py](/Users/chriss/Desktop/harness/src/sinan/coding/mock_responses.py): coding layer mock triggers
- [src/sinan/coding/nodes/](/Users/chriss/Desktop/harness/src/sinan/coding/nodes/): 17 node modules (每个模块头部有标准合约 docstring)

## Important Behavioral Notes

- User interaction is currently synchronous CLI `input()` inside nodes, not LangGraph `interrupt()` / `resume()`.
- `pending_interrupt` and `resume_payload` exist in state, but they are bookkeeping fields rather than a fully implemented resumable control path.
- Architecture revision is a real loop: reject/request changes -> `arch_revise` -> `framework_design`.
- Rejection loops are capped at 2 rounds.

## Artifact Model

A run writes into `runs/<run_id>/`.

Typical artifacts:

- `requirement_pack.json`
- `spec_review.json`
- `brief_debate.json`
- `user_brief_form.json`
- `framework_design.json`
- `subagent_reviews.json`
- `subagent_outputs.json`
- `framework_adjustment.json`
- `architecture_pack.json`
- `architecture_review.json`
- `arch_revision_brief.json` when needed
- `harness_design_draft.json`
- `harness_design_final.md`

### Coding Layer Artifacts

Coding layer writes into `runs/<run_id>/harness/`:

- `feature_list.json` — feature registry (updated per session)
- `claude-progress.txt` — markdown progress tracker
- `init.sh` — session initialization script
- `sprint_contract.json` — negotiated sprint goals (versioned)
- `sprint_result.json` — sprint completion summary
- `evaluator_grade.json` — QA evaluation scores (versioned)
- `bug_report.json` — bug report from evaluator

Plus `src/` with generated harness code and `.git/` for code history.
- `decision_log.md`
- `progress_log.md`
- `run_state.yaml`
- `version_registry.json` when versioned writes occur

## Development Notes

- This repo uses a `src/` layout.
- From the repo root, use `PYTHONPATH=src` when running modules directly.
- The virtualenv-local test command is `PYTHONPATH=src .venv/bin/python -m pytest -q`.
- Some smoke tests still reference legacy node names and will need alignment if you update graph assertions.

### Coding Layer 开发规范

**交接协议核心**：磁盘文件是 Agent 间的唯一交接协议。跨 Session 的信息通过文件传递，不依赖 state 持久化。详见 [NODES.md](/Users/chriss/Desktop/harness/src/sinan/coding/NODES.md)。

每个 node 模块头部有标准合约 docstring，包含：Agent / Loop / Reads / Writes / Artifacts / Routes。

## Legacy Names To Ignore

If you see these in old docs, old tests, or cached files, treat them as historical:

- `wait_brief`
- `wait_approval`
- `architecture_draft`
- `brief_gate`

The current implementation has replaced them with `sinan_debrief`, `sinan_approval`, and the four-step architecture debate flow.
