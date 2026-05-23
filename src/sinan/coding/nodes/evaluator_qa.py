"""evaluator_qa — Evaluator runs Playwright QA, grades 4 dimensions.

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
from ..state import CodingState
from ..prompts import get_coding_prompt
from ..testing import run_qa_eval
from sinan.llm import get_llm_client
from ..parse_json import _parse_json
from sinan.artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase,
)


def evaluator_qa_node(state: CodingState) -> dict:
    sprint = state.get("sprint_number", 1)
    update_run_state(state["run_id"], "EVALUATOR_QA")
    append_progress_log(state["run_id"], "EVALUATOR_QA", f"Sprint {sprint}: Running QA evaluation")

    # Run automated QA first
    qa_result = run_qa_eval(state["run_id"], {})

    # Then get LLM-based evaluation
    client = get_llm_client()
    system = get_coding_prompt("coding_evaluator")

    feature_list = state.get("feature_list") or {}
    features = feature_list.get("features", [])
    passing = [f for f in features if f.get("passes")]

    user = (
        f"请对 Sprint {sprint} 的交付物进行质量评估。\n\n"
        f"已完成的功能：\n{json.dumps(passing, indent=2, ensure_ascii=False)}\n\n"
        f"自动化测试结果：\n{json.dumps(qa_result.__dict__, indent=2, ensure_ascii=False)}\n\n"
        f"请用 Playwright 实际测试运行中的应用，检查 UI、API、数据库状态，并打分。"
    )

    raw = client.generate(system, user)
    grade = _parse_json(raw, "evaluator_qa")

    # Merge automated result with LLM evaluation
    if grade.get("overall_pass") is None:
        grade["overall_pass"] = qa_result.overall_pass

    write_json(state["run_id"], "evaluator_grade.json", grade, versioned=True)
    state["evaluator_grade"] = grade
    state["current_phase"] = "EVALUATOR_QA"

    func_score = grade.get("functionality", 0)
    prod_score = grade.get("product_depth", 0)
    vis_score = grade.get("visual_quality", 0)
    code_score = grade.get("code_quality", 0)

    append_progress_log(state["run_id"], "EVALUATOR_QA",
        f"QA scores: func={func_score} prod={prod_score} vis={vis_score} code={code_score}")
    append_decision_log(state["run_id"], {
        "phase": "EVALUATOR_QA",
        "type": "qa_complete",
        "content": f"Sprint {sprint} QA: {grade.get('summary', '')}",
        "rationale": f"Scores: func={func_score}, prod={prod_score}, vis={vis_score}, code={code_score}",
    })
    finalize_phase(state["run_id"])

    return state
