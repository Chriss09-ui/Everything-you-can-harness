# 司南 Harness Builder — Current Implementation Spec

## Overview

司南是一个面向 agentic harness 设计的元系统。
它的输入是一段自然语言需求，输出是一套经过扩展、质疑、用户确认和架构审查后的 harness 设计稿与过程产物。

当前代码实现的重点是：

- 将需求澄清流程工程化
- 将架构设计过程拆成多个可审计节点
- 在关键风险点引入人工确认
- 将每一步的 artifact 写入磁盘，便于追溯和回修

它当前不是：

- 代码生成器
- 可恢复的 LangGraph interrupt/resume 系统
- 运行真实 harness 的执行框架
- 生产级持久化服务

## Source Of Truth

当前实现的权威来源是代码，不是旧文档。
优先级建议如下：

1. [src/sinan/graph.py](/Users/chriss/Desktop/harness/src/sinan/graph.py)
2. [src/sinan/state.py](/Users/chriss/Desktop/harness/src/sinan/state.py)
3. `src/sinan/nodes/*.py`
4. [src/sinan/artifacts.py](/Users/chriss/Desktop/harness/src/sinan/artifacts.py)
5. 本文档

## Runtime Model

### Execution Mode

运行模式是单次 CLI 调用：

1. 用户在终端输入一个需求
2. CLI 初始化 `run_id` 和 state
3. LangGraph 串行执行节点
4. 个别节点通过同步 `input()` 与用户交互
5. 最终产物写入 `runs/<run_id>/`

### Important Clarification

虽然 state 中保留了 `pending_interrupt`、`resume_payload` 这类字段，但当前实现并没有使用 LangGraph 的 `interrupt()` / `resume()` 机制。

实际情况是：

- `sinan_debrief.py` 直接在节点内调用 `input()`
- `sinan_approval.py` 直接在节点内调用 `input()`
- 流程是同步阻塞式 CLI 交互，而不是可持久化恢复的交互式图执行

## Graph Topology

当前 graph 由以下节点组成：

1. `spec_expansion`
2. `spec_challenge`
3. `brief_debate`
4. `sinan_debrief`
5. `brief_compile`
6. `framework_design`
7. `subagent_review`
8. `framework_adjust`
9. `zonggong_integrate`
10. `architecture_challenge`
11. `approval_gate`
12. `sinan_approval`
13. `arch_revise`
14. `final_spec`

图外还有一个初始化步骤：

- `intake_node` in [src/sinan/nodes/intake.py](/Users/chriss/Desktop/harness/src/sinan/nodes/intake.py)

### Edge Flow

Normal path:

1. `spec_expansion -> spec_challenge`
2. `spec_challenge -> brief_debate`
3. `brief_debate -> sinan_debrief`
4. `sinan_debrief -> brief_compile`
5. `brief_compile -> framework_design`
6. `framework_design -> subagent_review`
7. `subagent_review -> framework_adjust`
8. `framework_adjust -> zonggong_integrate`
9. `zonggong_integrate -> architecture_challenge`
10. `architecture_challenge -> approval_gate`

Conditional routing:

- `approval_gate -> final_spec` when `risk_level == low`
- `approval_gate -> sinan_approval` otherwise
- `sinan_approval -> final_spec` when user approves
- `sinan_approval -> arch_revise` when user rejects or requests changes
- `arch_revise -> framework_design` to start another architecture revision round

### Retry Policy

Architecture rejection rounds are capped at 2.
If the user rejects or requests changes too many times, the graph raises a runtime error instead of looping forever.

## State Schema

The workflow state lives in [src/sinan/state.py](/Users/chriss/Desktop/harness/src/sinan/state.py).

### Core Metadata

- `run_id`
- `started_at`
- `current_phase`

### User Inputs

- `user_raw_input`
- `user_supplements`

### Primary Artifacts

- `requirement_pack`
- `spec_review`
- `brief_debate`
- `user_brief_form`
- `architecture_pack`
- `architecture_review`
- `arch_revision_brief`
- `harness_design_draft`

### Architecture Debate Artifacts

- `framework_design`
- `subagent_reviews`
- `framework_adjustments`

### Gatekeeping And Flow Control

- `gate_flags`
- `pending_interrupt`
- `interrupted_by`
- `resume_payload`
- `arch_reject_count`

### Audit And Memory-Like Tracking

- `decision_log`
- `progress_log`
- `artifact_versions`
- `risk_register`
- `messages`

## Node Responsibilities

### `intake_node`

File: [src/sinan/nodes/intake.py](/Users/chriss/Desktop/harness/src/sinan/nodes/intake.py)

Responsibilities:

- receive the initial user prompt
- set `user_raw_input`
- append the first user message
- initialize run-state tracking on disk

### `spec_expansion`

File: [src/sinan/nodes/spec_expansion.py](/Users/chriss/Desktop/harness/src/sinan/nodes/spec_expansion.py)

Role: Tuopu

Outputs:

- `requirement_pack.json`
- `state["requirement_pack"]`

### `spec_challenge`

File: [src/sinan/nodes/spec_challenge.py](/Users/chriss/Desktop/harness/src/sinan/nodes/spec_challenge.py)

Role: Jiewen

Outputs:

- `spec_review.json`
- ambiguity risks appended into `risk_register`

### `brief_debate`

File: [src/sinan/nodes/brief_debate.py](/Users/chriss/Desktop/harness/src/sinan/nodes/brief_debate.py)

Role: debate moderator

Outputs:

- `brief_debate.json`
- aligned points
- remaining disagreements
- user question list

### `sinan_debrief`

File: [src/sinan/nodes/sinan_debrief.py](/Users/chriss/Desktop/harness/src/sinan/nodes/sinan_debrief.py)

Role: Sinan user clarification step

Behavior:

- renders a user-facing summary using the `sinan_interact` prompt
- asks each unresolved question via terminal input
- allows `skip` and empty answers
- if unresolved risks remain, asks the user to `proceed` or `abort`

Outputs:

- `user_supplements`
- risk-related audit entries

### `brief_compile`

File: [src/sinan/nodes/brief_compile.py](/Users/chriss/Desktop/harness/src/sinan/nodes/brief_compile.py)

Role: Qiyue

Outputs:

- `user_brief_form.json`
- normalized confirmed brief for architecture work

### `framework_design`

File: [src/sinan/nodes/framework_design.py](/Users/chriss/Desktop/harness/src/sinan/nodes/framework_design.py)

Role: framework specialist under Zonggong

Behavior:

- drafts the initial framework shape
- optionally consumes an `arch_revision_brief` on later rounds
- writes `framework_design.json` as a versioned artifact

### `subagent_review`

File: [src/sinan/nodes/subagent_review.py](/Users/chriss/Desktop/harness/src/sinan/nodes/subagent_review.py)

Role: 3 specialist reviewers

Specialists:

- memory
- handoff
- eval

Outputs:

- `subagent_reviews.json`
- `subagent_outputs.json`

Each specialist both designs its own module and critiques the current framework.

### `framework_adjust`

File: [src/sinan/nodes/framework_adjust.py](/Users/chriss/Desktop/harness/src/sinan/nodes/framework_adjust.py)

Role: framework revision pass

Behavior:

- reads the specialist reviews
- asks the framework agent to accept or reject feedback
- supports either a wrapped `adjusted_framework` response or a raw framework body

Outputs:

- `framework_adjustment.json`
- `framework_design_v2.json`
- updated `state["framework_design"]`

### `zonggong_integrate`

File: [src/sinan/nodes/zonggong_integrate.py](/Users/chriss/Desktop/harness/src/sinan/nodes/zonggong_integrate.py)

Role: Zonggong final integration

Behavior:

- merges the revised framework with memory, handoff, and eval outputs
- adds traceability fields back into the architecture pack
- archives `architecture_pack.json` on revision rounds

Outputs:

- `architecture_pack.json`

### `architecture_challenge`

File: [src/sinan/nodes/architecture_challenge.py](/Users/chriss/Desktop/harness/src/sinan/nodes/architecture_challenge.py)

Role: Nishen

Outputs:

- `architecture_review.json`
- architecture-related risk entries

### `approval_gate`

File: [src/sinan/nodes/approval_gate.py](/Users/chriss/Desktop/harness/src/sinan/nodes/approval_gate.py)

Role: Shoumen

Behavior:

- reads the architecture review and architecture summary
- computes `risk_level`
- stores `shoumen_reasoning`, `key_concerns`, and a checklist in `gate_flags`
- routes automatically on low risk, otherwise requires user approval

### `sinan_approval`

File: [src/sinan/nodes/sinan_approval.py](/Users/chriss/Desktop/harness/src/sinan/nodes/sinan_approval.py)

Role: final user review step

Behavior:

- prints architecture summary and review warnings
- collects one of `approve`, `reject`, or `request_changes`
- optionally collects freeform revision guidance

Outputs:

- `resume_payload = {"approval": ..., "user_intent": ...}`
- incremented `arch_reject_count` on negative outcomes

### `arch_revise`

File: [src/sinan/nodes/arch_revise.py](/Users/chriss/Desktop/harness/src/sinan/nodes/arch_revise.py)

Role: revision brief generator

Behavior:

- turns architecture-review findings and user rejection notes into actionable repair instructions

Outputs:

- `arch_revision_brief.json`

### `final_spec`

File: [src/sinan/nodes/final_spec.py](/Users/chriss/Desktop/harness/src/sinan/nodes/final_spec.py)

Outputs:

- `harness_design_draft.json`
- `harness_design_final.md`

This step also includes an artifact version summary when versioned artifacts exist.

## Artifact Persistence

Persistence behavior lives in [src/sinan/artifacts.py](/Users/chriss/Desktop/harness/src/sinan/artifacts.py).

### Per-Run Directory

Each execution writes into:

- `runs/<run_id>/`

### Files Commonly Produced

- `requirement_pack.json`
- `spec_review.json`
- `brief_debate.json`
- `user_brief_form.json`
- `framework_design.json`
- `framework_adjustment.json`
- `framework_design_v2.json`
- `subagent_reviews.json`
- `subagent_outputs.json`
- `architecture_pack.json`
- `architecture_review.json`
- `arch_revision_brief.json` when applicable
- `harness_design_draft.json`
- `harness_design_final.md`
- `decision_log.md`
- `progress_log.md`
- `run_state.yaml`
- `version_registry.json` when versioning is used

### Versioning

When `write_json(..., versioned=True)` is used and the target file already exists:

- the old file is archived as `<name>_vN.json`
- archive metadata is written to `version_registry.json`
- the current file path keeps the canonical non-versioned filename

Current versioned artifacts include at least:

- framework design outputs
- subagent review outputs
- architecture packs during revision cycles

## LLM Abstraction

The LLM adapter lives in [src/sinan/llm.py](/Users/chriss/Desktop/harness/src/sinan/llm.py).

### Implementations

- `MockLLMClient`
- `_OpenAIClient`
- `_AnthropicClient`

### Selection Logic

- no API key -> mock
- API key present -> attempt provider client
- provider import missing -> fallback to mock

Mock behavior is deterministic and keyword-triggered through [src/sinan/mock_responses.py](/Users/chriss/Desktop/harness/src/sinan/mock_responses.py).

## Testing Status

Current tests live in `tests/`:

- [tests/test_graph_smoke.py](/Users/chriss/Desktop/harness/tests/test_graph_smoke.py)
- [tests/test_e2e_mock.py](/Users/chriss/Desktop/harness/tests/test_e2e_mock.py)

Important current status:

- the mock end-to-end flow still exercises the main pipeline shape
- some smoke-test node assertions still reference legacy node names and need updating to match `framework_design`, `sinan_debrief`, and `sinan_approval`

## Known Drift And Legacy Files

A few files or expectations in the repository still reflect an older design stage.

Examples:

- legacy node names such as `wait_brief`, `wait_approval`, and `architecture_draft`
- older docs that described a simpler architecture layer
- tests that still assert legacy node names

If there is any conflict, treat [src/sinan/graph.py](/Users/chriss/Desktop/harness/src/sinan/graph.py) as the canonical representation of the current workflow.
