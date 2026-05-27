"""Validation tests for artifact schemas across all three layers."""
import json
import pytest

from sinan.validation import (
    parse_and_validate_artifact, validate_artifact,
)


def test_parse_and_validate_requirement_pack_success():
    raw = """{
      "use_case_summary": "summary",
      "primary_goal": "goal",
      "stakeholders": [],
      "scope_inclusions": [],
      "scope_exclusions": [],
      "success_criteria": [],
      "assumptions": [],
      "known_constraints": [],
      "persona_qualities": [],
      "risk_tolerance": "medium"
    }"""

    parsed = parse_and_validate_artifact(raw, "requirement_pack")
    assert parsed["primary_goal"] == "goal"


def test_parse_and_validate_requirement_pack_missing_field():
    raw = """{
      "use_case_summary": "summary",
      "primary_goal": "goal"
    }"""

    with pytest.raises(ValueError, match="missing required fields"):
        parse_and_validate_artifact(raw, "requirement_pack")


def test_parse_and_validate_spec_review_invalid_json():
    raw = "{"

    with pytest.raises(ValueError, match="Failed to parse spec_review"):
        parse_and_validate_artifact(raw, "spec_review")


# ── Cross-layer contract: harness_design_draft (architecture → coding) ──

def _minimal_harness_design_draft() -> dict:
    return {
        "version": "1.0",
        "use_case": "x", "primary_goal": "x",
        "scope": {"inclusions": [], "exclusions": []},
        "success_criteria": [], "test_cases": [], "graph": {},
        "phase_sequence": [], "memory_module": {},
        "handoff_protocol": {}, "eval_placements": {},
        "state_schema": {},
    }


def test_harness_design_draft_complete_passes():
    validate_artifact(_minimal_harness_design_draft(), "harness_design_draft")


def test_harness_design_draft_missing_graph_fails():
    draft = _minimal_harness_design_draft()
    del draft["graph"]
    with pytest.raises(ValueError, match="missing required fields.*graph"):
        validate_artifact(draft, "harness_design_draft")


# ── Architecture layer: framework_adjustment dual-shape acceptance ──

def test_framework_adjustment_accepts_new_shape():
    data = {"adjusted_framework": {"nodes": []}, "feedback_responses": []}
    validate_artifact(data, "framework_adjustment")


def test_framework_adjustment_accepts_legacy_framework_shape():
    data = {"nodes": [], "edges": []}
    validate_artifact(data, "framework_adjustment")


def test_framework_adjustment_rejects_garbage():
    with pytest.raises(ValueError, match="framework_adjustment must contain"):
        validate_artifact({"status": "mock_response"}, "framework_adjustment")


# ── Coding layer: spec contract from planner ──

def test_spec_requires_features():
    with pytest.raises(ValueError, match="missing required fields.*features"):
        validate_artifact({"name": "x", "success_criteria": []}, "spec")
