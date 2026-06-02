"""arch_revise — 司南将逆审的结构化发现翻译为总工的修复指令。

Agent: 司南 (翻译者)
Layer: 架构层

Reads:
    state["architecture_review"]  — from architecture_challenge
    state["architecture_pack"]  — current architecture
    state["resume_payload"]    — user's modification intent (if any)

Writes:
    state["arch_revision_brief"]  — structured fix instructions for Zonggong
    state["current_phase"]        — "ARCH_REVISE"
    state["artifact_versions"]    — records arch_revision_brief version

Artifacts:
    arch_revision_brief.json

Routes:
    → framework_design  (linear, 重入四步辩论)
"""
from __future__ import annotations
import json
from ..state import HarnessBuilderState
from ..llm import get_llm_client
from ..prompts import get_prompt
from ..artifacts import (
    write_json, update_run_state, append_progress_log,
    append_decision_log, finalize_phase, load_state_or_file,
    get_current_artifact,
)
from ..validation import parse_llm_json, validate_artifact


def arch_revise_node(state: HarnessBuilderState) -> dict:
    update_run_state(state["run_id"], "ARCH_REVISE")
    append_progress_log(state["run_id"], "ARCH_REVISE", "Generating revision brief for Zonggong")

    client = get_llm_client()
    system = get_prompt("arch_revise")

    arch = load_state_or_file(state, "architecture_pack")
    review = load_state_or_file(state, "architecture_review")
    brief = load_state_or_file(state, "user_brief_form")
    # revision_round 取「state 计数」与「磁盘已有 revision_brief 最高 round + 1」
    # 的较大值。`--from-brief` 入口会通过 _count_arch_rejects 恢复 state 计数；
    # 但其他重入路径（直接 invoke graph、cli 跳过入口、未来加的中间恢复点）
    # 可能不恢复 state 计数，导致这里回到 0、与磁盘上已有的 revision_brief 序列
    # 冲突。取 max(disk_max + 1, state_count) 保证 revision_round 严格大于上轮。
    revision_round = max(
        state.get("arch_reject_count", 0),
        _max_revision_round_on_disk(state["run_id"]) + 1,
    )
    resume = state.get("resume_payload") or {}
    user_intent = resume.get("user_intent", "")

    # Strip the traceability fields zonggong_integrate embedded in the pack.
    # Otherwise the prompt dumps 3x the relevant tokens for ``subagent_outputs``
    # + ``framework_design`` + ``design_trace``; the reviser only needs
    # to see the actual architecture decisions.
    arch_for_prompt = {
        k: v for k, v in arch.items()
        if k not in ("subagent_outputs", "framework_design", "design_trace")
    }

    user = (
        f"【第 {revision_round} 轮逆审发现 — 这是第 {revision_round} 次被拒绝后的修复】\n"
        f"逆审评分: {review.get('challenge_score', '?')}/10\n"
        f"建议: {review.get('recommendation', '?')}\n\n"
        f"过度设计警告:\n"
        + ("\n".join(f"  - {f}" for f in review.get("over_engineering_flags", [])) or "  （无）") + "\n\n"
        f"交接缺口:\n"
        + ("\n".join(f"  - {g}" for g in review.get("handoff_gaps", [])) or "  （无）") + "\n\n"
        f"评估缺口:\n"
        + ("\n".join(f"  - {e}" for e in review.get("eval_gaps", [])) or "  （无）") + "\n\n"
        f"未覆盖失败模式:\n"
        + ("\n".join(f"  - {f}" for f in review.get("failure_mode_omissions", [])) or "  （无）") + "\n\n"
        f"复杂度关注:\n"
        + ("\n".join(f"  - {c}" for c in review.get("cost_complexity_concerns", [])) or "  （无）") + "\n\n"
        f"【上版架构设计】\n{json.dumps(arch_for_prompt, indent=2, ensure_ascii=False)}\n\n"
        f"【用户需求契约】\n{json.dumps(brief, indent=2, ensure_ascii=False)}\n\n"
        f"【用户在拒绝时提供的修改方向】\n{user_intent or '（用户未提供额外说明）'}\n\n"
        "请将以上逆审发现和用户修改意图翻译为具体的修复指令。"
    )

    raw = client.generate(system, user)
    revision_brief = parse_llm_json(raw, "arch_revision_brief")

    # revision_round is the round *this brief is asking Zonggong to apply*.
    # It equals arch_reject_count (incremented by sinan_approval before this
    # node runs), so first rejection → revision_round=1. Attached AFTER
    # parsing the LLM output because the LLM doesn't know this value; we
    # then validate the assembled artifact (schema requires revision_round).
    revision_brief["revision_round"] = revision_round
    validate_artifact(revision_brief, "arch_revision_brief")

    write_json(state["run_id"], "arch_revision_brief.json", revision_brief, versioned=True)
    state["arch_revision_brief"] = revision_brief
    state["current_phase"] = "ARCH_REVISE"
    state["artifact_versions"]["arch_revision_brief"] = "1.0"

    issues = revision_brief.get("specific_issues", [])
    append_progress_log(
        state["run_id"], "ARCH_REVISE",
        f"Generated revision brief with {len(issues)} specific issues for Zonggong"
    )
    append_decision_log(state["run_id"], {
        "phase": "ARCH_REVISE",
        "type": "revision_brief_generated",
        "content": f"Generated revision brief: {revision_brief.get('revision_summary', '')}",
        "rationale": f"Translated Nishen's {len(issues)} findings into actionable fix instructions for Zonggong",
        "issues": [i.get("issue") for i in issues],
    })
    finalize_phase(state["run_id"])

    return state


def _max_revision_round_on_disk(run_id: str) -> int:
    """Return the highest revision_round seen in any arch_revision_brief on disk.

    Falls back to 0 when no prior brief exists (first reject) or when reading
    fails (corrupt / partial write). Used as a floor for revision_round so
    that a re-entry path which doesn't restore ``state["arch_reject_count"]``
    still produces a revision_round that's strictly greater than any prior
    round's — keeping the on-disk sequence monotonically increasing.
    """
    saved = get_current_artifact(run_id, "arch_revision_brief")
    if not isinstance(saved, dict):
        return 0
    try:
        return int(saved.get("revision_round") or 0)
    except (TypeError, ValueError):
        return 0
