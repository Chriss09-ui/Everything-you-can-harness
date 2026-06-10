"""Validation tests for artifact schemas across all three layers."""
import json
import pytest

from sinan.validation import (
    parse_and_validate_artifact, parse_llm_json, validate_artifact,
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
    # Wrapped framework must have nodes + edges (validator now enforces
    # structural completeness on the inner framework too).
    data = {
        "adjusted_framework": {"nodes": [], "edges": []},
        "feedback_responses": [],
    }
    validate_artifact(data, "framework_adjustment")


def test_framework_adjustment_accepts_legacy_framework_shape():
    data = {"nodes": [], "edges": []}
    validate_artifact(data, "framework_adjustment")


def test_framework_adjustment_rejects_garbage():
    with pytest.raises(ValueError, match="framework_adjustment must contain"):
        validate_artifact({"status": "mock_response"}, "framework_adjustment")


def test_framework_adjustment_rejects_feedback_only():
    """``feedback_responses`` alone is not enough — the validator must also
    require a usable framework structure. Previously this slipped through,
    and framework_adjust then fell back to writing the feedback-only dict
    as the next ``framework_design.json``, silently corrupting downstream
    nodes that read ``.get("nodes", [])`` and got empty lists.
    """
    data = {"feedback_responses": [{"feedback": "x", "response": "accepted"}]}
    with pytest.raises(ValueError, match="framework_adjustment must contain"):
        validate_artifact(data, "framework_adjustment")


def test_framework_adjustment_rejects_adjusted_framework_without_edges():
    """The wrapper case also needs the inner framework to have nodes + edges
    — otherwise framework_adjust writes a partial framework_design to disk."""
    data = {"adjusted_framework": {"nodes": []}}  # missing edges
    with pytest.raises(ValueError, match="framework_adjustment must contain"):
        validate_artifact(data, "framework_adjustment")


# ── user_brief_form schema — sign_off_timestamp & brief_version are system-set ──


def test_user_brief_form_passes_without_metadata_fields():
    """``sign_off_timestamp`` and ``brief_version`` are now stamped by the
    system (brief_compile) after validation, NOT supplied by the LLM. They
    must NOT be in the required-field set, otherwise an LLM that correctly
    omits them gets rejected before the system can fill them in."""
    data = {
        "confirmed_requirements": [], "rejected_suggestions": [],
        "supplementary_notes": "", "priority_order": [],
        "constraints_final": [],
        # No sign_off_timestamp, no brief_version — system fills these in.
    }
    # Must NOT raise.
    validate_artifact(data, "user_brief_form")


# ── Coding layer: spec contract from planner ──

def test_spec_requires_features():
    with pytest.raises(ValueError, match="missing required fields.*features"):
        validate_artifact({"name": "x", "success_criteria": []}, "spec")


# ── Architecture layer: arch_revision_brief schema ──
# Pin that the schema matches what the prompt actually asks the LLM to produce
# AND what the consumer nodes (framework_design / arch_revise / zonggong_integrate)
# actually read. Drift here means either:
#   - LLM gets a prompt asking for X but schema requires Y → parse always fails
#   - Consumer code reads field A but schema enforces B → field silently absent

def test_arch_revision_brief_accepts_real_prompt_output():
    """Real-shape output from the arch_revise prompt must pass validation
    once the node-attached revision_round is present. The LLM doesn't know
    the reject count, so arch_revise attaches it after parsing; we mirror
    that assembly here."""
    data = {
        "revision_summary": "shrink over-engineering",
        "specific_issues": [
            {"issue": "x", "in_previous_design": "y", "fix_instruction": "z"}
        ],
        "preserve_points": ["artifact-based handoff"],
        "revision_round": 1,
    }
    validate_artifact(data, "arch_revision_brief")


def test_arch_revision_brief_rejects_legacy_field_names():
    """If someone reverts the schema to the old `revision_focus/must_fix/preserve`
    names (which the prompt does NOT produce), validation must fail on real
    LLM output. This protects against the schema/prompt drift we fixed."""
    data = {
        "revision_focus": "shrink over-engineering",
        "must_fix": ["item1"],
        "preserve": ["artifact-based handoff"],
    }
    with pytest.raises(ValueError, match="missing required fields"):
        validate_artifact(data, "arch_revision_brief")


# ── LLM JSON parsing tolerance ──


def test_parse_llm_json_strips_fenced_block_with_surrounding_prose():
    """Real LLMs often wrap JSON in a fenced block with chatty prose before
    and after. The previous ``^...$`` regex required the fences to span the
    whole string, so a trailing "Let me know if…" line broke parsing. We now
    locate the first `` ```...``` `` block anywhere in the text."""
    raw = (
        "Here is the requirement pack:\n"
        "```json\n"
        '{"primary_goal": "g", "use_case_summary": "u", "stakeholders": [], '
        '"scope_inclusions": [], "scope_exclusions": [], "success_criteria": [], '
        '"assumptions": [], "known_constraints": [], "persona_qualities": [], '
        '"risk_tolerance": "medium"}\n'
        "```\n"
        "Let me know if you'd like any adjustments.\n"
    )
    data = parse_llm_json(raw, "requirement_pack")
    assert data["primary_goal"] == "g"


def test_parse_llm_json_plain_json_still_works():
    """No fence — just JSON — should still parse (the common case)."""
    data = parse_llm_json('{"primary_goal": "g"}', "framework_design")
    assert data["primary_goal"] == "g"


def test_parse_llm_json_prefers_json_tagged_block_when_multiple_fences():
    """When the LLM returns multiple fenced blocks (typical pattern: an
    example in TS / Python first, then the real JSON), the parser must
    pick the JSON-tagged block, not whatever comes first.

    Before the fix: the greedy ``.*`` regex spanned the first opening
    fence to the LAST closing fence, producing a body that contained
    the example code + prose + real-JSON-prefix → parse failed. Now the
    parser prefers `` ```json `` and falls back to the first non-greedy
    fence match.
    """
    raw = (
        "Here's an example in TypeScript:\n"
        "```typescript\n"
        "const x = { foo: 'bar' };\n"
        "```\n\n"
        "But the real JSON is:\n"
        "```json\n"
        '{"primary_goal": "g", "use_case_summary": "u", "stakeholders": [], '
        '"scope_inclusions": [], "scope_exclusions": [], "success_criteria": [], '
        '"assumptions": [], "known_constraints": [], "persona_qualities": [], '
        '"risk_tolerance": "medium"}\n'
        "```\n"
        "Let me know!"
    )
    data = parse_llm_json(raw, "requirement_pack")
    assert data["primary_goal"] == "g", (
        f"parser picked the wrong fence or none — got {data}"
    )


def test_parse_llm_json_untagged_fence_still_works_after_fix():
    """A single untagged fence around JSON must still parse. (Regression
    guard: don't ONLY prefer `` ```json `` — keep the fallback working.)"""
    raw = (
        "Result:\n"
        "```\n"
        '{"primary_goal": "g"}\n'
        "```\n"
    )
    data = parse_llm_json(raw, "framework_design")
    assert data["primary_goal"] == "g"


def test_parse_llm_json_tolerates_trailing_comma():
    """Smaller/faster LLMs emit trailing commas before } or ]; strict json
    rejects them. parse_llm_json must repair and parse rather than crash the
    whole pipeline on one malformed sub-agent reply (observed live with
    deepseek-v4-flash producing a trailing comma in an eval review)."""
    raw = '{"a": 1, "b": [1, 2,], "c": {"d": 3,},}'
    data = parse_llm_json(raw, "framework_design")
    assert data == {"a": 1, "b": [1, 2], "c": {"d": 3}}


def test_parse_llm_json_trailing_comma_repair_preserves_string_commas():
    """The trailing-comma repair is string-aware: a literal ", ]" / ", }"
    INSIDE a string value must survive untouched."""
    raw = '{"note": "items, ] and more, }", "list": [1,],}'
    data = parse_llm_json(raw, "framework_design")
    assert data["note"] == "items, ] and more, }"
    assert data["list"] == [1]


def test_minimal_schema_from_required_fields():
    """minimal_schema builds a tool-use input_schema from _REQUIRED_FIELDS:
    object + top-level required + open nested shapes."""
    from sinan.validation import minimal_schema
    s = minimal_schema("subagent_review_item")
    assert s["type"] == "object"
    assert s["additionalProperties"] is True
    assert set(s["required"]) == {
        "agent_name", "incompatibilities", "missing_elements",
        "endorsed_elements", "summary",
    }
    assert set(s["properties"]) == set(s["required"])


def test_minimal_schema_open_for_unregistered():
    """An artifact with no required-fields entry (e.g. a sub-agent design step)
    yields an open object schema — still forces the structured tool path, but
    constrains no content."""
    from sinan.validation import minimal_schema
    s = minimal_schema("zonggong_memory")
    assert s["type"] == "object"
    assert s["required"] == []
    assert s["additionalProperties"] is True
