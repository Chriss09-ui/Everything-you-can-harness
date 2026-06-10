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
    r"```[a-zA-Z0-9_+\-]*\s*\n(?P<body>.*?)```",
    re.DOTALL,
)
"""
Non-greedy (``.*?``) so that when an LLM returns multiple fenced blocks
(common pattern: an example fence followed by the real JSON fence), the
regex matches the FIRST complete fence rather than spanning from the
first opening to the last closing.

If the LLM tags the JSON block specifically (`` ```json ``), prefer that
one — heuristic via ``_JSON_FENCE_RE`` below.
"""
_JSON_FENCE_RE = re.compile(
    r"```json\s*\n(?P<body>.*?)```",
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
    "sinan_debrief_display": {
        # LLM-controlled UI payload consumed by sinan_debrief_node before
        # prompting the user. Without ``display`` the node silently shows
        # nothing and proceeds; without ``user_questions`` / ``aligned_points``
        # / ``remaining_disagreements`` the user gets no context for the
        # inputs they're being asked for. Validate the wrapper so a
        # malformed LLM response fails fast instead of producing a blank UI.
        "display",
    },
    "user_brief_form": {
        # NOTE: ``sign_off_timestamp`` and ``brief_version`` are system-set
        # metadata (the LLM cannot accurately produce the current UTC time, and
        # the version is a hardcoded constant). brief_compile stamps both
        # values AFTER validation, so they're intentionally absent from the
        # required set — requiring them here would force the LLM to invent a
        # plausible-but-wrong timestamp that the code would then NOT overwrite.
        "confirmed_requirements", "rejected_suggestions",
        "supplementary_notes", "priority_order", "constraints_final",
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
        # revision_round is the round *this brief is asking Zonggong to apply*
        # — equals arch_reject_count at the time arch_revise runs. Required
        # because zonggong_integrate uses it to label archive versions.
        "revision_summary", "specific_issues", "preserve_points",
        "revision_round",
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
        # ``bugs`` is required even though it may be an empty list: the
        # downstream evaluator_bugs reads ``grade.get("bugs", [])`` and
        # an absent key would silently produce ``total_bugs=0`` → fix loop
        # skipped → real regressions dropped on the floor. An empty list is
        # a legitimate grade ("QA passed, no bugs"); an absent key is not.
        "overall_pass", "summary", "bugs",
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


def _strip_trailing_commas(s: str) -> str:
    """Remove trailing commas (",}" / ",]") that sit OUTSIDE string literals.

    Smaller/faster LLMs emit them often; strict ``json.loads`` rejects them.
    This is string-aware: it tracks whether the scanner is inside a JSON string
    (honouring backslash escapes), so a literal ``", }"`` inside a value is left
    untouched. Only a comma followed — after optional whitespace — by ``}`` or
    ``]`` while outside a string is dropped.
    """
    out: list[str] = []
    in_str = False
    esc = False
    n = len(s)
    for i, ch in enumerate(s):
        if in_str:
            out.append(ch)
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            out.append(ch)
            continue
        if ch == ",":
            j = i + 1
            while j < n and s[j] in " \t\r\n":
                j += 1
            if j < n and s[j] in "}]":
                continue  # drop the trailing comma
        out.append(ch)
    return "".join(out)


def parse_llm_json(raw: str, artifact_name: str) -> dict:
    """Strip markdown fences and parse a JSON-only LLM response.

    Tolerates leading/trailing prose ("Here is the JSON:\n```json\n...\n```\n
    Let me know…") — extract a fenced JSON block if present, otherwise try
    the whole text.

    Prefers a `` ```json ``-tagged fence when present (LLMs commonly tag
    the real JSON block while using untagged or other-language fences for
    example code). Falls back to the first fenced block of any language.

    Refuses to silently return a half-parsed object by raising
    ``ValueError`` on any failure.
    """
    text = raw.strip()
    # Prefer a ```json```-tagged block.
    m = _JSON_FENCE_RE.search(text)
    if not m:
        # Fallback to any fenced block (non-greedy matches the FIRST
        # complete fence, not a greedy span across multiple fences).
        m = _FENCE_RE.search(text)
    if m:
        text = m.group("body").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # LLMs (especially smaller/faster models) frequently emit trailing
        # commas before } or ]. Retry once with a string-aware repair before
        # giving up — the repair only removes commas OUTSIDE string literals,
        # so a literal ", }" inside a value is never corrupted. If the repaired
        # text still doesn't parse, surface the ORIGINAL error (more honest
        # about what the LLM actually produced).
        repaired = _strip_trailing_commas(text)
        if repaired == text:
            raise ValueError(f"Failed to parse {artifact_name}: {exc}") from exc
        try:
            data = json.loads(repaired)
        except json.JSONDecodeError:
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
    ``adjusted_framework`` (optionally + ``feedback_responses``), or the
    framework itself (legacy). Either way the payload MUST carry a usable
    framework — ``feedback_responses`` alone is insufficient because the
    downstream node extracts ``adjusted_framework`` (or falls back to the
    whole dict) and writes it as the next ``framework_design.json``. A
    feedback-only payload would silently produce a framework with no
    nodes/edges, corrupting the architecture pipeline downstream.
    """
    af = data.get("adjusted_framework")
    if isinstance(af, dict) and "nodes" in af and "edges" in af:
        return data
    # legacy shape: dict itself IS the framework_design
    if "nodes" in data and "edges" in data:
        return data
    raise ValueError(
        "framework_adjustment must contain a usable framework: either an "
        "``adjusted_framework`` dict with nodes + edges, or a top-level "
        "framework_design-shaped dict with nodes + edges. ``feedback_responses`` "
        "alone is not sufficient."
    )


def parse_and_validate_artifact(raw: str, artifact_name: str) -> dict:
    """Parse an LLM response and fail fast on schema violations."""
    data = parse_llm_json(raw, artifact_name)
    return validate_artifact(data, artifact_name)


# Tool-use input schemas with EXPLICIT field types. minimal_schema (derived
# from _REQUIRED_FIELDS) only guarantees top-level key presence — and under
# tool use that lets the model "legally" fill an array-shaped field with a JSON
# *string* (observed: incompatibilities came back as a 955-char string of
# serialized JSON). For artifacts whose field types matter (displayed/consumed
# downstream), pin the types here so the model is forced to emit real arrays.
_TOOL_SCHEMAS = {
    "subagent_review_item": {
        "type": "object",
        "properties": {
            "agent_name": {"type": "string"},
            "incompatibilities": {"type": "array"},
            "missing_elements": {"type": "array"},
            "endorsed_elements": {"type": "array"},
            "summary": {"type": "string"},
        },
        "required": ["agent_name", "incompatibilities", "missing_elements",
                     "endorsed_elements", "summary"],
        "additionalProperties": True,
    },
}


def minimal_schema(artifact_name: str) -> dict:
    """Return a JSON Schema for use as a tool-use ``input_schema``.

    Prefers an explicit typed schema from ``_TOOL_SCHEMAS`` (field types pinned
    so the model can't fill an array field with a string). Falls back to a
    minimal schema derived from ``_REQUIRED_FIELDS`` — object + top-level
    required keys, nested shapes left open (same philosophy as
    ``validate_artifact``). Artifacts with neither (e.g. the per-sub-agent
    design steps) yield an open object schema: still forces the structured tool
    path (killing text malformations) without constraining content.
    """
    explicit = _TOOL_SCHEMAS.get(artifact_name)
    if explicit is not None:
        return explicit
    required = sorted(_REQUIRED_FIELDS.get(artifact_name) or [])
    return {
        "type": "object",
        "properties": {k: {} for k in required},
        "required": required,
        "additionalProperties": True,
    }
