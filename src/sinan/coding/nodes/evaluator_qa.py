"""evaluator_qa — Evaluator reviews runner results + code and grades 4 dimensions.

Agent: Evaluator
Loop:  Sprint (review)

Reads:
    state["feature_list"]  — features with pass/fail status
    state["sprint_number"] — current sprint

Writes:
    state["evaluator_grade"] — {functionality, product_depth, visual_quality, code_quality, overall_pass, bugs}
    state["current_phase"]   — "EVALUATOR_QA"

Artifacts:
    evaluator_grade.json  — versioned QA report

Routes:
    → sprint_complete  when overall_pass=true
    → evaluator_bugs   when overall_pass=false
"""
from __future__ import annotations
import json
from dataclasses import asdict
from ..state import CodingState
from ..prompts import get_coding_prompt
from ..testing import run_qa_eval
from sinan.llm import get_llm_client
from sinan.validation import parse_and_validate_artifact
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)


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

    # Step 2: LLM evaluator reviews the SAME code base plus the runner results.
    # The runner's hard data feeds the prompt so the LLM can't "be nice" about
    # objective failures.
    client = get_llm_client()
    system = get_coding_prompt("coding_evaluator")

    feature_list = state.get("feature_list") or {}
    features = feature_list.get("features", [])
    passing = [f for f in features if f.get("passes")]

    user = (
        f"请对 Sprint {sprint} 的交付物进行质量评估。\n\n"
        f"已完成的功能：\n{json.dumps(passing, indent=2, ensure_ascii=False)}\n\n"
        f"★ Runner 真跑报告（ground truth，overall_pass={qa_result.overall_pass}）：\n"
        f"{qa_result.summary}\n\n"
        f"各测试用例详情：\n{json.dumps(qa_result.runner_results, indent=2, ensure_ascii=False)}\n\n"
        f"请基于以上硬数据 + 你审阅代码的判断，综合打分。"
    )

    raw = client.generate(system, user)
    grade = parse_and_validate_artifact(raw, "evaluator_grade")

    # Merge: runner's verdict takes precedence over LLM's "overall_pass" ONLY
    # when runner actually ran and saw failures. Otherwise LLM is the final
    # authority.
    if runner_saw_failures:
        if grade.get("overall_pass"):
            append_progress_log(state["run_id"], "EVALUATOR_QA",
                "Overriding LLM overall_pass=True because runner saw failures")
        grade["overall_pass"] = False
    elif grade.get("overall_pass") is None:
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
    })
    finalize_phase(state["run_id"])

    return state
