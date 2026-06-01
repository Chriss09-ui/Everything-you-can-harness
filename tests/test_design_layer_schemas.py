"""Schema validation coverage for ALL production artifacts.

The original ``test_validation.py`` covers 6 of 23 schemas. The other 17 are
production-citical: a drift between a node's prompt, its reader's
expectations, and the schema enforced here would silently drop field values
or pass garbage downstream. This file covers the gap.

For each registered artifact we pin two things:
  - ``test_<name>_accepts_minimal_real_shape`` — passes validation when
    populated with the minimum fields a real LLM output / Python-assembled
    payload would carry.
  - ``test_<name>_rejects_missing_<field>`` — fails validation with a
    clear "missing required fields" error when each required field is
    absent. This is the regression net: if someone removes a field from
    ``_REQUIRED_FIELDS`` by mistake, the corresponding acceptance test will
    still document it was expected; the rejection tests confirm the schema
    matters.
"""
import pytest

from sinan.validation import validate_artifact


# ── Requirement-layer schemas (gap-fill) ────────────────────────────────────


def test_brief_debate_accepts_real_shape():
    validate_artifact({
        "tuopu_position": "p", "jiewen_challenges": [],
        "tuopu_responses": [], "aligned_points": [],
        "remaining_disagreements": [], "user_questions": [],
    }, "brief_debate")


def test_brief_debate_rejects_missing_field():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"tuopu_position": "x"}, "brief_debate")


def test_user_brief_form_accepts_real_shape():
    validate_artifact({
        "confirmed_requirements": [], "rejected_suggestions": [],
        "supplementary_notes": "", "priority_order": [],
        "constraints_final": [], "sign_off_timestamp": "t",
        "brief_version": "1.0",
    }, "user_brief_form")


def test_user_brief_form_rejects_missing_field():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"confirmed_requirements": []}, "user_brief_form")


# ── Architecture-layer schemas (gap-fill) ───────────────────────────────────


def test_framework_design_accepts_real_shape():
    validate_artifact({
        "nodes": [], "edges": [], "entry_point": "s",
    }, "framework_design")


def test_framework_design_rejects_missing_entry_point():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"nodes": [], "edges": []}, "framework_design")


def test_subagent_reviews_accepts_three_agents():
    validate_artifact({
        "memory": {"agent_name": "memory"},
        "handoff": {"agent_name": "handoff"},
        "eval": {"agent_name": "eval"},
    }, "subagent_reviews")


def test_subagent_reviews_rejects_missing_agent():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"memory": {}, "handoff": {}}, "subagent_reviews")


def test_subagent_outputs_accepts_three_agents():
    validate_artifact({"memory": {}, "handoff": {}, "eval": {}}, "subagent_outputs")


def test_subagent_outputs_rejects_missing_agent():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"memory": {}, "handoff": {}}, "subagent_outputs")


def test_subagent_review_item_accepts_real_shape():
    validate_artifact({
        "agent_name": "memory", "incompatibilities": [],
        "missing_elements": [], "endorsed_elements": [],
        "summary": "ok",
    }, "subagent_review_item")


def test_subagent_review_item_rejects_missing_field():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"agent_name": "x"}, "subagent_review_item")


def test_architecture_pack_accepts_real_shape():
    validate_artifact({
        "graph_description": "g", "phase_sequence": [],
        "memory_module": {}, "handoff_protocol": {},
        "eval_placements": {}, "approval_gates": [],
        "failure_recovery": "r", "risks_identified": [],
    }, "architecture_pack")


def test_architecture_pack_rejects_missing_field():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({
            "graph_description": "g", "phase_sequence": [],
        }, "architecture_pack")


def test_architecture_review_accepts_real_shape():
    validate_artifact({
        "over_engineering_flags": [], "handoff_gaps": [],
        "eval_gaps": [], "failure_mode_omissions": [],
        "cost_complexity_concerns": [], "challenge_score": 3,
        "recommendation": "pass",
    }, "architecture_review")


def test_architecture_review_rejects_missing_field():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({
            "over_engineering_flags": [], "handoff_gaps": [],
        }, "architecture_review")


# ── Coding-layer schemas (gap-fill) ─────────────────────────────────────────
# These protect the coding layer too, even though we're not changing the
# coding nodes themselves. Schemas are the architecture→coding and
# coding→coding contract; schema drift breaks both layers.


def test_sprint_contract_accepts_minimal():
    validate_artifact({"sprint_goals": []}, "sprint_contract")


def test_sprint_contract_rejects_empty():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({}, "sprint_contract")


def test_sprint_negotiation_accepts_real_shape():
    validate_artifact({"agreed": True, "summary": "ok"}, "sprint_negotiation")


def test_sprint_negotiation_rejects_missing():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"agreed": True}, "sprint_negotiation")


def test_execution_plan_accepts_real_shape():
    validate_artifact({"execution_order": ["a", "b"]}, "execution_plan")


def test_execution_plan_rejects_missing():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({}, "execution_plan")


def test_implement_result_accepts_real_shape():
    validate_artifact({"status": "implemented", "files": []}, "implement_result")


def test_implement_result_rejects_missing():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"status": "x"}, "implement_result")


def test_evaluator_grade_accepts_real_shape_with_empty_bugs():
    # Bugs is required even when empty: an absent key would silently turn
    # total_bugs=0 and skip the fix loop on real bugs. Pin the contract.
    validate_artifact({
        "overall_pass": True, "summary": "ok", "bugs": [],
    }, "evaluator_grade")


def test_evaluator_grade_rejects_missing_bugs():
    with pytest.raises(ValueError, match="missing required fields.*bugs"):
        validate_artifact({
            "overall_pass": True, "summary": "ok",
        }, "evaluator_grade")


def test_fix_result_accepts_real_shape():
    # NOTE: ``verified`` intentionally NOT required — generator_fix uses
    # presence/absence to branch (see test_fix_result_verified).
    validate_artifact({"status": "fixed", "files": []}, "fix_result")


def test_fix_result_rejects_missing_status():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"files": []}, "fix_result")


def test_bug_report_accepts_real_shape():
    validate_artifact({
        "bugs": [], "total_bugs": 0, "sprint_number": 1,
    }, "bug_report")


def test_bug_report_rejects_missing():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"bugs": []}, "bug_report")


def test_sprint_result_accepts_real_shape():
    validate_artifact({
        "sprint_number": 1, "completion_pct": 0,
        "spec_complete": False,
    }, "sprint_result")


def test_sprint_result_rejects_missing():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"sprint_number": 1}, "sprint_result")


def test_sinan_debrief_display_accepts_with_display_field():
    validate_artifact({"display": {"header": "x"}}, "sinan_debrief_display")


def test_sinan_debrief_display_rejects_missing_display():
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact({"header": "x"}, "sinan_debrief_display")


def test_unknown_artifact_passes_through():
    """Artifacts not in _REQUIRED_FIELDS are allowed — pin this contract so
    callers can opt-in to validation without it being a hard requirement."""
    validate_artifact({"foo": "bar"}, "totally_unknown_artifact_name")
