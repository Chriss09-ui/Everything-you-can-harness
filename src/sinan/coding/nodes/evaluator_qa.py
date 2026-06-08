"""evaluator_qa — Evaluator reviews runner results + code and grades 4 dimensions.

Agent: Evaluator (Claude Agent SDK — READ-ONLY tool use)
Loop:  Sprint (review)

Reads:
    state["feature_list"]  — features with pass/fail status
    state["sprint_number"] — current sprint
    harness/ source code   — the Evaluator agent reads it directly (Read/Glob/Grep)

Writes:
    state["evaluator_grade"] — {functionality, product_depth, visual_quality, code_quality, overall_pass, bugs}
    state["current_phase"]   — "EVALUATOR_QA"

Artifacts:
    evaluator_grade.json  — versioned QA report

Routes:
    → sprint_complete  when overall_pass=true
    → evaluator_bugs   when overall_pass=false

Independence: the Evaluator agent gets READ-ONLY tools (no Write/Edit/Bash) so
it cannot mutate the code it judges — keeping it cleanly separate from the
Generator that writes it. Execution ground truth comes from the deterministic
``run_qa_eval`` runner, which still overrides the LLM's overall_pass on failure.
"""
from __future__ import annotations
import json
from ..state import CodingState
from ..prompts import get_coding_prompt
from ..testing import run_qa_eval
from sinan.agent import get_agent_runner
from sinan.validation import validate_artifact
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, get_run_dir,
)


# Read-only tool set: the judge inspects code but cannot change or run it.
_EVALUATOR_TOOLS = ["Read", "Glob", "Grep"]

# Evaluator's structured grade. Required mirrors validate_artifact("evaluator_grade").
_EVALUATOR_GRADE_SCHEMA = {
    "type": "object",
    "properties": {
        "overall_pass": {"type": "boolean"},
        "summary": {"type": "string"},
        "bugs": {"type": "array", "items": {"type": "object"}},
        "functionality": {"type": "number"},
        "product_depth": {"type": "number"},
        "visual_quality": {"type": "number"},
        "code_quality": {"type": "number"},
    },
    "required": ["overall_pass", "summary", "bugs"],
    "additionalProperties": True,
}


def evaluator_qa_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    update_run_state(state["run_id"], "EVALUATOR_QA")
    append_progress_log(state["run_id"], "EVALUATOR_QA", f"Sprint {sprint}: Running QA evaluation")

    # Step 1: Runner objectively runs main.py against every test_case in the
    # design draft. The runner's verdict is ground truth — if it reports any
    # expected_to_pass case that failed, the LLM evaluator MUST set
    # overall_pass=false (the prompt enforces this).
    qa_result = run_qa_eval(state["run_id"], {})
    # Runner is ground truth ONLY when it actually ran (runner_results non-empty).
    # When the runner skipped (no test_cases or no main.py), it sets
    # overall_pass=True with runner_results=[] as a neutral signal — we defer
    # to the LLM evaluator in that case.
    runner_ran = bool(qa_result.runner_results)
    runner_saw_failures = runner_ran and not qa_result.overall_pass

    # Step 2: Evaluator agent reviews the SAME code base plus the runner
    # results. It reads the actual source (Read/Glob/Grep) — a capability the
    # old single-completion node lacked — but cannot modify or run it. The
    # runner's hard data feeds the prompt so the agent can't "be nice" about
    # objective failures.
    runner = get_agent_runner()
    system = get_coding_prompt("coding_evaluator")

    feature_list = state.get("feature_list") or {}
    features = feature_list.get("features", [])
    passing = [f for f in features if f.get("passes")]
    harness_dir = get_run_dir(state["run_id"]) / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)

    user = (
        f"请对 Sprint {sprint} 的交付物进行质量评估。请用 Read/Glob/Grep 工具审阅当前项目目录中的"
        f"实际代码后再打分（你只能读，不能改动或运行代码）。\n\n"
        f"已完成的功能：\n{json.dumps(passing, indent=2, ensure_ascii=False)}\n\n"
        f"★ Runner 真跑报告（ground truth，overall_pass={qa_result.overall_pass}）：\n"
        f"{qa_result.summary}\n\n"
        f"各测试用例详情：\n{json.dumps(qa_result.runner_results, indent=2, ensure_ascii=False)}\n\n"
        f"请基于以上硬数据 + 你审阅代码的判断，综合打分。"
    )

    agent_result = runner.run(
        system=system,
        prompt=user,
        cwd=harness_dir,
        allowed_tools=_EVALUATOR_TOOLS,
        schema=_EVALUATOR_GRADE_SCHEMA,
    )
    grade = agent_result.parse("evaluator_grade")
    validate_artifact(grade, "evaluator_grade")

    # Merge: runner's verdict takes precedence over LLM's "overall_pass" ONLY
    # when runner actually ran and saw failures. Otherwise LLM is the final
    # authority.
    if runner_saw_failures:
        if grade.get("overall_pass"):
            append_progress_log(state["run_id"], "EVALUATOR_QA",
                "Overriding LLM overall_pass=True because runner saw failures")
        grade["overall_pass"] = False
    elif "overall_pass" not in grade:
        grade["overall_pass"] = qa_result.overall_pass

    write_json(state["run_id"], "evaluator_grade.json", grade, versioned=True)
    state["evaluator_grade"] = grade
    state["current_phase"] = "EVALUATOR_QA"

    func_score = grade.get("functionality", 0)
    prod_score = grade.get("product_depth", 0)
    vis_score = grade.get("visual_quality", 0)
    code_score = grade.get("code_quality", 0)

    append_progress_log(state["run_id"], "EVALUATOR_QA",
        f"QA scores: func={func_score} prod={prod_score} vis={vis_score} code={code_score} | runner={qa_result.summary}")
    append_decision_log(state["run_id"], {
        "phase": "EVALUATOR_QA",
        "type": "qa_complete",
        "content": f"Sprint {sprint} QA: {grade.get('summary', '')}",
        "rationale": f"Runner: {qa_result.summary}; LLM scores: func={func_score}, prod={prod_score}, vis={vis_score}, code={code_score}",
        "agent_cost_usd": agent_result.total_cost_usd,
        "agent_turns": agent_result.num_turns,
    })
    finalize_phase(state["run_id"])

    return state
