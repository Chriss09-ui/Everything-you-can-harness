"""HarnessBuilderState — the central state schema for the Sinan workflow."""
from __future__ import annotations
from typing import TypedDict, Optional, Literal
from datetime import datetime, timezone


class GateFlags(TypedDict, total=False):
    challenge_passed: bool
    architecture_passed: bool
    needs_user_brief: bool
    risk_level: str
    flagged_risks: list[str]
    shoumen_reasoning: str
    key_concerns: list[str]
    checklist: dict


class HarnessBuilderState(TypedDict):
    # ── Meta ──
    run_id: str
    started_at: str
    current_phase: str

    # ── User Input ──
    user_raw_input: str
    user_supplements: list[Optional[str]]
    # user_brief_answers defaults to None so load_state_or_file can distinguish
    # "sinan_debrief hasn't run yet" (None → fall back to disk) from
    # "sinan_debrief ran but the user skipped every question" ([] → use []).
    user_brief_answers: Optional[list[dict]]

    # ── Core Artifacts ──
    requirement_pack: Optional[dict]
    spec_review: Optional[dict]
    brief_debate: Optional[dict]
    user_brief_form: Optional[dict]
    architecture_pack: Optional[dict]
    architecture_review: Optional[dict]
    arch_revision_brief: Optional[dict]
    harness_design_draft: Optional[dict]

    # ── Framework Debate (Architecture Layer) ──
    framework_design: Optional[dict]           # Round 1: Framework 初始输出
    subagent_reviews: Optional[dict]           # Round 2: 子代理评审报告
    subagent_outputs: Optional[dict]           # Round 2: 子代理详细模块设计
    framework_adjustments: Optional[dict]      # Round 3: Framework 调整记录

    # ── Gatekeeping ──
    gate_flags: GateFlags

    # ── Scribe ──
    decision_log: list[dict]
    progress_log: list[dict]
    artifact_versions: dict[str, str]

    # ── Flow Control ──
    pending_interrupt: Optional[
        Literal["user_brief", "user_approval"]
    ]
    interrupted_by: Optional[str]
    resume_payload: Optional[dict]
    arch_reject_count: int

    # ── Risk ──
    risk_register: list[dict]

    # ── Messages ──
    messages: list[dict]


def make_initial_state(run_id: str) -> HarnessBuilderState:
    return HarnessBuilderState(
        run_id=run_id,
        started_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        current_phase="INTAKE",
        user_raw_input="",
        user_supplements=[],
        user_brief_answers=None,
        requirement_pack=None,
        spec_review=None,
        brief_debate=None,
        user_brief_form=None,
        architecture_pack=None,
        architecture_review=None,
        arch_revision_brief=None,
        harness_design_draft=None,
        framework_design=None,
        subagent_reviews=None,
        subagent_outputs=None,
        framework_adjustments=None,
        gate_flags=GateFlags(
            challenge_passed=False,
            architecture_passed=False,
            needs_user_brief=False,
            risk_level="unknown",
            flagged_risks=[],
            shoumen_reasoning="",
            key_concerns=[],
            checklist={},
        ),
        decision_log=[],
        progress_log=[],
        artifact_versions={},
        pending_interrupt=None,
        interrupted_by=None,
        resume_payload=None,
        arch_reject_count=0,
        risk_register=[],
        messages=[],
    )
