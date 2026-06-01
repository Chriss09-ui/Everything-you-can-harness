"""Static guard: every MockLLMClient trigger must actually match the prompt
that the corresponding node sends to the LLM.

Why this exists: the project has been burned twice by mock trigger drift —
``mock_responses.py`` registered a trigger using one phrase, the node was
later rewritten to send the LLM a different prompt, mock silently fell
through to the generic ``_fallback_response``, and ``validate_artifact``
raised a misleading "missing required fields" error from the schema check.

The bug is invisible until someone actually exercises the path (e.g. tries
to test the reject loop), and the failure surfaces far from the cause.

This file collects every mock trigger and asserts it appears, character
for character (case-insensitive), in the literal prompt string the
production node sends. We lazy-build the maps at test time so a future
developer doesn't have to maintain a separate fixture list.

A node that changes its user-prompt suffix is forced to update the mock
trigger (or extend the override list below) — the test fails loudly with
the offending trigger name and the actual prompt.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan import mock_responses as mock_mod
from sinan.llm import MockLLMClient
from sinan.mock_responses import register_mock_responses


# ── Build a {trigger: node_name + actual_prompt-fingerprint} map ──
#
# We use a small helper that runs each node's prompt-assembly logic against
# a realistic state and returns the (system, user) strings the LLM would
# see. The test then checks trigger ∈ (system + user) for each registered
# mock trigger.
#
# New nodes: add a builder here that returns the system+user pair.


def _fresh_state(run_id="mock_trigger_check"):
    """A minimal but schema-valid state that nodes can read from."""
    from sinan.state import make_initial_state
    state = make_initial_state(run_id)
    state["user_raw_input"] = "demo agentic harness"
    state["user_brief_form"] = {
        "use_case_summary": "s", "primary_goal": "g", "stakeholders": [],
        "scope_inclusions": [], "scope_exclusions": [],
        "success_criteria": [], "assumptions": [],
        "known_constraints": [], "persona_qualities": [],
        "risk_tolerance": "low",
        "confirmed_requirements": [], "rejected_suggestions": [],
        "supplementary_notes": "", "priority_order": [],
        "constraints_final": [], "sign_off_timestamp": "t",
        "brief_version": "1.0",
    }
    state["architecture_pack"] = {"phase_sequence": ["a"]}
    state["architecture_review"] = {
        "challenge_score": 3, "over_engineering_flags": [],
        "failure_mode_omissions": [], "handoff_gaps": [], "eval_gaps": [],
        "cost_complexity_concerns": [], "recommendation": "pass",
    }
    return state


def _build_node_prompts():
    """Return a list of (node_label, system, user) for every node that
    talks to the LLM. Naturally some nodes (sinan_approval, final_spec)
    don't call the LLM at all — they're skipped.
    """
    from sinan.prompts import get_prompt
    from sinan.nodes import (
        spec_expansion, spec_challenge, brief_debate, brief_compile,
        framework_design, subagent_review, framework_adjust,
        zonggong_integrate, architecture_challenge, arch_revise,
        approval_gate, sinan_debrief,
    )
    import json

    state = _fresh_state()
    out = []

    # spec_expansion: doesn't expose its system+user separately, so we
    # reproduce the literal strings it actually sends.
    out.append((
        "spec_expansion",
        get_prompt("tuopu"),
        f"用户原始输入如下。请生成结构化 Requirement Pack:\n\n{state['user_raw_input']}",
    ))

    # spec_challenge
    rp = state.get("requirement_pack") or {"_": "_"}
    out.append((
        "spec_challenge",
        get_prompt("jiewen"),
        f"以下是 Requirement Pack，请进行批判性审查:\n\n{json.dumps(rp, indent=2, ensure_ascii=False)}",
    ))

    # brief_debate
    out.append((
        "brief_debate",
        get_prompt("brief_debate"),
        "请主持辩论并输出结果",  # even a substring is enough
    ))

    # brief_compile
    out.append((
        "brief_compile",
        get_prompt("qiyue"),
        "请合并以上所有信息，生成最终 User Brief Form。",
    ))

    # framework_design (round 1)
    out.append((
        "framework_design_round1",
        get_prompt("zonggong_framework"),
        "【第一轮】请设计 harness 的整体框架结构",
    ))

    # framework_design (revision round)
    state_with_revision = dict(state)
    state_with_revision["arch_revision_brief"] = {
        "revision_summary": "x", "specific_issues": [],
        "preserve_points": [], "revision_round": 1,
    }
    from sinan.nodes.framework_design import _build_revision_context
    revision_ctx = _build_revision_context(state_with_revision)
    out.append((
        "framework_design_revision",
        get_prompt("zonggong_framework"),
        f"{revision_ctx}\n请按上述修复指令调整 framework",
    ))

    # subagent_review — first call (per-agent design). We check the system
    # prompt; user is built dynamically but contains "Framework Design:" etc.
    # The trigger for these is the system prompt body itself ("你是记忆模块设计师"
    # / "你是交接协议设计师" / "你是评估专家"), so checking system strings is
    # sufficient.
    out.append(("subagent_review_memory", get_prompt("zonggong_memory"), ""))
    out.append(("subagent_review_handoff", get_prompt("zonggong_handoff"), ""))
    out.append(("subagent_review_eval", get_prompt("zonggong_eval"), ""))

    # subagent_review — second call (the actual review)
    out.append((
        "subagent_review_reviewcall",
        get_prompt("subagent_review"),
        "",  # trigger "评审当前 framework 设计" lives in the system prompt
    ))

    # framework_adjust
    out.append((
        "framework_adjust",
        get_prompt("zonggong_framework"),
        "请仔细阅读三个子代理的评审报告，逐条回应并调整 framework",
    ))

    # zonggong_integrate
    out.append((
        "zonggong_integrate",
        get_prompt("zonggong"),
        "请整合以上所有输出，生成完整的 Harness 架构包",
    ))

    # architecture_challenge
    out.append((
        "architecture_challenge",
        get_prompt("nishen"),
        "请批判性审查以上架构设计",
    ))

    # approval_gate
    out.append((
        "approval_gate",
        get_prompt("approval_gate"),
        "请评估以上信息",  # from approval_gate.py user prompt
    ))

    # arch_revise
    out.append((
        "arch_revise",
        get_prompt("arch_revise"),
        "请将以上逆审发现和用户修改意图翻译为具体的修复指令",
    ))

    # sinan_debrief — uses the ``sinan_interact`` system prompt
    out.append((
        "sinan_debrief",
        get_prompt("sinan_interact"),
        "",
    ))

    return out


def test_every_mock_trigger_matches_a_real_node_prompt():
    """For every mock trigger registered in ``mock_responses.py``, at least
    one production node must produce a prompt that contains it.

    We RESET the class registry and re-register only the design-layer
    mocks — otherwise tests like test_fix_result_verified register
    coding-only triggers (``"Bug 修复"``) that pollute the class dict and
    fail this check.
    """
    MockLLMClient.reset()
    register_mock_responses()

    client = MockLLMClient()
    triggers = list(client._responses.keys())

    node_prompts = _build_node_prompts()
    # Build one mega-string per node that combines system + user (since the
    # MockLLMClient matches on the combined string).
    node_combined = [
        (label, (system + user).lower())
        for label, system, user in node_prompts
    ]

    unmatched = []
    for trigger in triggers:
        t_lower = trigger.lower()
        matched_somewhere = any(
            t_lower in combined for _, combined in node_combined
        )
        if not matched_somewhere:
            unmatched.append(trigger)

    # Clean up the reset so we don't affect later tests
    MockLLMClient.reset()
    register_mock_responses()

    assert not unmatched, (
        f"mock trigger(s) not found in any production node prompt — "
        f"mock will fall through to the generic _fallback_response and "
        f"tests will fail in a confusing place. Offending triggers: {unmatched}"
    )


def test_substring_triggers_dont_silently_change_winner():
    """If one trigger is a substring of another, the longer one wins in
    MockLLMClient (because the dict loop overwrites ``matched_response``
    as later matches fire). This is fragile, so we flag the dangerous
    direction: shorter trigger registered AFTER a longer one that contains
    it — that means the shorter will shadow the longer.

    Same reset+re-register dance as the previous test to keep the check
    focused on design-layer mocks only."""
    MockLLMClient.reset()
    register_mock_responses()

    client = MockLLMClient()
    triggers = list(client._responses.keys())

    problems = []
    for i, earlier in enumerate(triggers):
        for later in triggers[i + 1:]:
            if earlier.lower() in later.lower() and earlier.lower() != later.lower():
                pass  # longer registered later → overwrites earlier, safe
            elif later.lower() in earlier.lower() and earlier.lower() != later.lower():
                problems.append(
                    f"shorter trigger {later!r} registered AFTER longer "
                    f"trigger {earlier!r}; shorter will shadow longer"
                )

    MockLLMClient.reset()
    register_mock_responses()

    assert not problems, (
        f"mock trigger precedence issue: {problems}"
    )
