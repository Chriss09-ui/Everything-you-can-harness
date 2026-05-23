"""Validation tests for requirement-layer artifacts."""
import pytest

from sinan.validation import parse_and_validate_artifact


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
