"""Validation helpers for LLM-produced and Python-assembled artifacts.

Schema strategy: only top-level required fields are enforced. Extra fields
are allowed (LLM outputs can carry additional context without failing).
Nested-shape validation is intentionally out of scope — schema is a guard
against silent field drift, not a full type system.

Reference: see CLAUDE.md "改动同步原则" — any new node that writes an
artifact must register its schema here in the same commit.
"""
from __future__ import annotations

import json
import re


_FENCE_RE = re.compile(
    r"^\s*```[a-zA-Z0-9_+\-]*\s*\n(?P<body>.*)```\s*$",
    re.DOTALL,
)


_REQUIRED_FIELDS = {
    # ── Requirement layer ──
    "requirement_pack": {
        "use_case_summary", "primary_goal", "stakeholders",
        "scope_inclusions", "scope_exclusions", "success_criteria",
        "assumptions", "known_constraints", "persona_qualities",
        "risk_tolerance",
    },
    "spec_review": {
        "ambiguities", "conflicts", "hidden_assumptions",
        "unverifiable_goals", "edge_cases", "challenge_score",
        "recommendation",
    },
    "brief_debate": {
        "tuopu_position", "jiewen_challenges", "tuopu_responses",
        "aligned_points", "remaining_disagreements", "user_questions",
    },
    "user_brief_form": {
        "confirmed_requirements", "rejected_suggestions",
        "supplementary_notes", "priority_order", "constraints_final",
        "sign_off_timestamp", "brief_version",
    },

    # ── Architecture layer ──
    "framework_design": {
        # core graph topology — must be present for downstream to plan
        "nodes", "edges", "entry_point",
    },
    "subagent_review_item": {
        # one entry inside subagent_reviews — schema for a single review report
        "agent_name", "incompatibilities", "missing_elements",
        "endorsed_elements", "summary",
    },
    "subagent_reviews": {
        # wrapper: must contain all three sub-agent reviews
        "memory", "handoff", "eval",
    },
    "subagent_outputs": {
        # wrapper: must contain all three sub-agent detailed designs
        "memory", "handoff", "eval",
    },
    "framework_adjustment": {
        # accepts either the new shape (with adjusted_framework wrapper) or
        # the legacy shape (where the dict itself IS the framework).
        # Required: at least feedback_responses OR nodes must be present.
        # Enforced via _validate_framework_adjustment below.
    },
    "architecture_pack": {
        "graph_description", "phase_sequence", "memory_module",
        "handoff_protocol", "eval_placements", "approval_gates",
        "failure_recovery", "risks_identified",
    },
    "architecture_review": {
        "over_engineering_flags", "handoff_gaps", "eval_gaps",
        "failure_mode_omissions", "cost_complexity_concerns",
        "challenge_score", "recommendation",
    },
    "arch_revision_brief": {
        # arch_revise compiles user feedback + reviewer findings into
        # actionable changes for the next framework_design round.
        "revision_focus", "must_fix", "preserve",
    },
    "harness_design_draft": {
        # cross-layer contract: architecture → coding. This is the most
        # important schema in the whole project. final_spec assembles it
        # from many architecture artifacts; planner consumes it.
        "version", "use_case", "primary_goal", "scope",
        "success_criteria", "test_cases", "graph", "phase_sequence",
        "memory_module", "handoff_protocol", "eval_placements",
        "state_schema",
    },

    # ── Coding layer ──
    "spec": {
        # planner's expansion of harness_design_draft; coding layer entry
        "name", "features", "success_criteria",
    },
    "sprint_contract": {
        # initial draft from sprint_plan
        "sprint_goals",
    },
    "sprint_negotiation": {
        # output of sprint_negotiate — evaluator's reply to sprint_plan
        "agreed", "summary",
    },
    "execution_plan": {
        # sprint_setup adds an execution plan on top of the contract
        "execution_order",
    },
    "implement_result": {
        "status", "files",
    },
    "evaluator_grade": {
        "overall_pass", "summary",
    },
    "fix_result": {
        # NOTE: ``verified`` is intentionally NOT in the schema. generator_fix
        # reads ``result.get("verified")`` and only falls back to sanity.passed
        # when the LLM omitted the field entirely. If we required it here,
        # LLMs that explicitly return ``verified: false`` (admitting they
        # didn't fix the bug) would still pass schema, but the code path
        # difference between "missing" and "false" matters — see
        # generator_fix.py for the full rule.
        "status", "files",
    },
    "bug_report": {
        "bugs", "total_bugs", "sprint_number",
    },
    "sprint_result": {
        "sprint_number", "completion_pct", "spec_complete",
    },
}


def parse_llm_json(raw: str, artifact_name: str) -> dict:
    """Strip markdown fences and parse a JSON-only LLM response."""
    text = raw.strip()
    m = _FENCE_RE.match(text)
    if m:
        text = m.group("body").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse {artifact_name}: {exc}") from exc

    if not isinstance(data, dict):
        raise ValueError(f"{artifact_name} must be a JSON object")

    return data


def validate_artifact(data: dict, artifact_name: str) -> dict:
    """Validate that the parsed artifact contains the required top-level fields.

    Artifacts not registered in _REQUIRED_FIELDS pass through unchecked
    (so the validator can be opt-in per artifact). For artifacts with
    custom rules (e.g. framework_adjustment), dispatch to a dedicated
    validator.
    """
    if artifact_name == "framework_adjustment":
        return _validate_framework_adjustment(data)

    required_fields = _REQUIRED_FIELDS.get(artifact_name)
    if not required_fields:
        return data

    missing = sorted(required_fields - set(data))
    if missing:
        raise ValueError(
            f"{artifact_name} is missing required fields: {', '.join(missing)}"
        )
    return data


def _validate_framework_adjustment(data: dict) -> dict:
    """framework_adjustment may come in two shapes: a wrapper dict with
    ``adjusted_framework`` + ``feedback_responses`` keys, or the framework
    itself (legacy). Accept either as long as something usable is there."""
    if "adjusted_framework" in data or "feedback_responses" in data:
        return data
    # legacy shape: must look like a framework_design at minimum
    if "nodes" in data and "edges" in data:
        return data
    raise ValueError(
        "framework_adjustment must contain either adjusted_framework / "
        "feedback_responses, or a framework_design-shaped dict with nodes + edges"
    )


def parse_and_validate_artifact(raw: str, artifact_name: str) -> dict:
    """Parse an LLM response and fail fast on schema violations."""
    data = parse_llm_json(raw, artifact_name)
    return validate_artifact(data, artifact_name)
