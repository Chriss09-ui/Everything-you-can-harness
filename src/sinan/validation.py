"""Validation helpers for LLM-produced artifacts."""
from __future__ import annotations

import json


_REQUIRED_FIELDS = {
    "requirement_pack": {
        "use_case_summary",
        "primary_goal",
        "stakeholders",
        "scope_inclusions",
        "scope_exclusions",
        "success_criteria",
        "assumptions",
        "known_constraints",
        "persona_qualities",
        "risk_tolerance",
    },
    "spec_review": {
        "ambiguities",
        "conflicts",
        "hidden_assumptions",
        "unverifiable_goals",
        "edge_cases",
        "challenge_score",
        "recommendation",
    },
    "brief_debate": {
        "tuopu_position",
        "jiewen_challenges",
        "tuopu_responses",
        "aligned_points",
        "remaining_disagreements",
        "user_questions",
    },
    "user_brief_form": {
        "confirmed_requirements",
        "rejected_suggestions",
        "supplementary_notes",
        "priority_order",
        "constraints_final",
        "sign_off_timestamp",
        "brief_version",
    },
}


def parse_llm_json(raw: str, artifact_name: str) -> dict:
    """Strip markdown fences and parse a JSON-only LLM response."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse {artifact_name}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{artifact_name} must be a JSON object")

    return data


def validate_artifact(data: dict, artifact_name: str) -> dict:
    """Validate that the parsed artifact contains the required top-level fields."""
    required_fields = _REQUIRED_FIELDS.get(artifact_name)
    if not required_fields:
        return data

    missing = sorted(required_fields - set(data))
    if missing:
        raise ValueError(
            f"{artifact_name} is missing required fields: {', '.join(missing)}"
        )
    return data


def parse_and_validate_artifact(raw: str, artifact_name: str) -> dict:
    """Parse the LLM response and fail fast on invalid requirement-layer artifacts."""
    data = parse_llm_json(raw, artifact_name)
    return validate_artifact(data, artifact_name)
