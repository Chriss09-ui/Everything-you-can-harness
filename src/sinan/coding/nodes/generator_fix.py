"""generator_fix — Generator fixes bugs, self-tests before re-submitting.

Agent: Generator (Claude Agent SDK — autonomous tool use)
Loop:  Fix (≤2 rounds)

Reads:
    state["bug_report"]     — bug list from evaluator
    state["sprint_number"]  — current sprint
    state["fix_loop_count"] — current fix attempt

Writes:
    state["fix_result"]     — agent's report {status, files, verified, self_test_passed, summary}
    state["fix_loop_count"] — incremented
    state["current_phase"]  — "GENERATOR_FIX"

Artifacts:
    patched files written into harness/ by the Generator agent itself
    (Read/Write/Edit/Bash/Glob/Grep), sandboxed to cwd=harness/ — NOT by
    Python write_text.

Routes:
    → evaluator_qa   when self-test pass or fix_count≥2
    → generator_fix  when self-test fail and fix_count<2 (self-loop)
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from ..testing import run_sanity_check
from sinan.agent import get_agent_runner
from sinan.validation import validate_artifact
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


# Agent's final structured report. ``verified`` is intentionally optional (see
# the verified-fallback rule below); validate_artifact only requires status+files.
_FIX_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string"},
        "files": {"type": "array", "items": {"type": "object"}},
        "verified": {"type": "boolean"},
        "summary": {"type": "string"},
    },
    "required": ["status", "files"],
    "additionalProperties": True,
}

_GENERATOR_TOOLS = ["Read", "Write", "Edit", "Bash", "Glob", "Grep"]


def generator_fix_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    fix_count = state.get("fix_loop_count", 0)
    update_run_state(state["run_id"], "GENERATOR_FIX")
    append_progress_log(state["run_id"], "GENERATOR_FIX",
        f"Sprint {sprint}: Generator fixing bugs (attempt {fix_count})")

    runner = get_agent_runner()
    system = get_coding_prompt("coding_generator")

    bug_report = state.get("bug_report") or {}
    bugs = bug_report.get("bugs", [])
    harness_dir = get_run_dir(state["run_id"]) / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)  # agent's cwd must exist

    user = (
        f"Sprint {sprint} Bug 修复（修复轮次 {fix_count}）。\n\n"
        f"请在当前项目目录中修复以下 bug。你可以使用 Read/Write/Edit/Bash/Glob/Grep "
        f"工具直接修改文件并运行测试验证——所有改动都在当前项目目录内完成，确保修复不引入新问题。\n\n"
        f"Bug 报告：\n{json.dumps(bugs, indent=2, ensure_ascii=False)}\n\n"
        f"修复并自测完成后，用 JSON 汇报：\n"
        f"{{\"status\": \"fixed\", \"verified\": true|false, \"files\": [{{\"path\": \"...\", \"action\": \"modify\"}}], \"summary\": \"...\"}}"
    )

    # The agent patches files itself and runs its own tests inside harness/
    # (sandboxed by the seam), then returns the report.
    agent_result = runner.run(
        system=system,
        prompt=user,
        cwd=harness_dir,
        allowed_tools=_GENERATOR_TOOLS,
        schema=_FIX_RESULT_SCHEMA,
    )
    result = agent_result.parse("fix_result")
    validate_artifact(result, "fix_result")

    # Self-test after fix. ``run_sanity_check`` only verifies that the
    # harness still has src/ + main.py — it does NOT check the bug was fixed.
    # So we only fall back to sanity.passed when the LLM omitted ``verified``
    # entirely. If the LLM explicitly returned ``verified: false`` (admitted
    # it didn't fix the bug) we honour that signal — overwriting it with
    # "files still exist" would let bugs slip past the fix loop.
    sanity = run_sanity_check(state["run_id"])
    result["self_test_passed"] = sanity.passed
    if "verified" not in result:
        result["verified"] = sanity.passed

    state["fix_result"] = result
    state["fix_loop_count"] = fix_count + 1
    state["current_phase"] = "GENERATOR_FIX"

    if sanity.passed:
        append_progress_log(state["run_id"], "GENERATOR_FIX",
            f"Self-test passed after fix")
    else:
        append_progress_log(state["run_id"], "GENERATOR_FIX",
            f"Self-test failed: {sanity.errors}")

    append_decision_log(state["run_id"], {
        "phase": "GENERATOR_FIX",
        "type": "bug_fix_attempt",
        "content": f"Sprint {sprint} fix attempt {fix_count}: {result.get('status', '?')}",
        "rationale": f"Self-test: {'passed' if sanity.passed else 'failed'}",
        "agent_cost_usd": agent_result.total_cost_usd,
        "agent_turns": agent_result.num_turns,
    })
    finalize_phase(state["run_id"])

    return state
