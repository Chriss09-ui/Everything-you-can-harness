"""generator_fix — Generator fixes bugs, self-tests before re-submitting.

Agent: Generator
Loop:  Fix (≤2 rounds)

Reads:
    state["bug_report"]     — bug list from evaluator
    state["sprint_number"]  — current sprint
    state["fix_loop_count"] — current fix attempt

Writes:
    state["fix_result"]     — {status, files, self_test_passed, summary}
    state["fix_loop_count"] — incremented
    state["current_phase"]  — "GENERATOR_FIX"

Artifacts:
    writes patched files to harness/ per LLM output

Routes:
    → evaluator_qa   when self-test pass or fix_count≥2
    → generator_fix  when self-test fail and fix_count<2 (self-loop)
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from ..testing import run_sanity_check
from sinan.llm import get_llm_client
from ..parse_json import _parse_json
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


def generator_fix_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    fix_count = state.get("fix_loop_count", 0)
    update_run_state(state["run_id"], "GENERATOR_FIX")
    append_progress_log(state["run_id"], "GENERATOR_FIX",
        f"Sprint {sprint}: Generator fixing bugs (attempt {fix_count})")

    client = get_llm_client()
    system = get_coding_prompt("coding_generator")

    bug_report = state.get("bug_report") or {}
    bugs = bug_report.get("bugs", [])
    harness_dir = get_run_dir(state["run_id"]) / "harness"

    user = (
        f"Sprint {sprint} Bug 修复（修复轮次 {fix_count}）：\n\n"
        f"Bug 报告：\n{json.dumps(bugs, indent=2, ensure_ascii=False)}\n\n"
        f"项目目录：{harness_dir}\n\n"
        f"请修复上述 bug，确保修复不引入新的问题。修复完成后运行测试验证。\n\n"
        f"输出 JSON：{{\"status\": \"fixed\", \"files\": [{{\"path\": \"...\", \"content\": \"...\", \"action\": \"modify\"}}], \"summary\": \"...\"}}"
    )

    raw = client.generate(system, user)
    result = _parse_json(raw, "generator_fix")

    for f in result.get("files", []):
        target = harness_dir / f["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(f["content"])

    # Self-test after fix
    sanity = run_sanity_check(state["run_id"])
    result["self_test_passed"] = sanity.passed

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
    })
    finalize_phase(state["run_id"])

    return state
