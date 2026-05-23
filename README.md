# 司南 Harness Builder

A LangGraph-driven meta-harness for turning natural-language product ideas into a reviewed agentic harness design.

## What It Does

司南不是直接替用户执行任务的 agent。
它的职责是把一段模糊需求，经过多阶段扩展、质疑、用户确认、架构设计与风险审查，产出一份可继续实现的 harness 设计稿。

当前实现聚焦于“设计流程工程化”而不是“自动写代码”。

## Current Workflow

The code currently runs the following pipeline:

1. `INTAKE` — collect the user's raw idea
2. `SPEC_EXPANSION` — Tuopu expands it into a structured requirement pack
3. `SPEC_CHALLENGE` — Jiewen critiques the requirement pack
4. `BRIEF_DEBATE` — debate aligns agreements and unresolved questions
5. `SINAN_DEBRIEF` — Sinan asks the user to answer core questions
6. `BRIEF_COMPILE` — Qiyue compiles a confirmed user brief
7. `FRAMEWORK_DESIGN` — framework agent drafts the first architecture skeleton
8. `SUBAGENT_REVIEW` — memory, handoff, and eval specialists review the framework
9. `FRAMEWORK_ADJUST` — framework agent revises based on the reviews
10. `ZONGGONG_INTEGRATE` — Zonggong integrates the framework and specialist outputs
11. `ARCHITECTURE_CHALLENGE` — Nishen critiques the architecture
12. `APPROVAL_GATE` — Shoumen decides whether the user must review the design
13. `SINAN_APPROVAL` — user approves, rejects, or requests changes when needed
14. `ARCH_REVISE` — Sinan translates rejection feedback into a revision brief
15. `FINAL_SPEC` — final design draft is compiled and written to disk

If the user rejects the architecture, the graph loops back from `ARCH_REVISE` to `FRAMEWORK_DESIGN`.
The retry cap is currently 2 rejection rounds.

## Quick Start

```bash
# 1. Create and activate a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the CLI from the repo root
PYTHONPATH=src python -m sinan.cli
```

Why `PYTHONPATH=src` is needed: this repository uses a `src/` layout and is not currently packaged with a `pyproject.toml` or editable install step.

## LLM Mode

The runtime chooses between mock and real LLMs through [src/sinan/llm.py](/Users/chriss/Desktop/harness/src/sinan/llm.py).

- No API key set: uses the built-in `MockLLMClient`
- `OPENAI_API_KEY` or `ANTHROPIC_API_KEY` set: attempts to use a real provider client
- If the expected SDK import is unavailable: falls back to the mock client

For local experimentation, copy `.env.example` to `.env` and set the relevant API key.

## Project Structure

```text
src/sinan/
  artifacts.py          # Run directories, artifact writes, version registry
  cli.py                # Terminal entrypoint
  graph.py              # LangGraph assembly and routing
  llm.py                # Mock/OpenAI/Anthropic adapter
  mock_responses.py     # Deterministic mock outputs for tests and local runs
  prompts.py            # Role-specific system prompts
  state.py              # HarnessBuilderState schema
  nodes/
    intake.py
    spec_expansion.py
    spec_challenge.py
    brief_debate.py
    sinan_debrief.py
    brief_compile.py
    framework_design.py
    subagent_review.py
    framework_adjust.py
    zonggong_integrate.py
    architecture_challenge.py
    approval_gate.py
    sinan_approval.py
    arch_revise.py
    final_spec.py

tests/
  test_graph_smoke.py   # Smoke coverage for graph and state
  test_e2e_mock.py      # Mock end-to-end pipeline run

runs/<run_id>/          # Per-run artifacts and logs
```

## Main Artifacts

A typical run writes these files into `runs/<run_id>/`:

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
- `arch_revision_brief.json` when a revision round is triggered
- `harness_design_draft.json`
- `harness_design_final.md`
- `decision_log.md`
- `progress_log.md`
- `run_state.yaml`
- `version_registry.json` when versioned artifacts are archived

## Testing

Run tests from the repository root with the virtualenv interpreter:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Note: the current test suite includes legacy node-name assertions that do not yet match the graph implementation. The core mock pipeline test still provides useful coverage.

## Scope

Current scope:

- structured requirement expansion
- requirement critique and debate
- human-in-the-loop clarification
- architecture drafting with specialist review
- architecture critique and approval routing
- final design artifact generation

Out of scope for the current implementation:

- code generation
- shell execution in the designed harness
- sandbox orchestration
- production persistence beyond local files
- long-term memory infrastructure
