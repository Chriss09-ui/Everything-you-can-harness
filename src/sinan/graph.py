"""LangGraph workflow assembly for 司南 Harness Builder."""
from __future__ import annotations
from langgraph.graph import StateGraph, END
from .state import HarnessBuilderState
from .nodes import (
    spec_expansion,
    spec_challenge,
    brief_debate,
    brief_compile,
    framework_design,
    subagent_review,
    framework_adjust,
    zonggong_integrate,
    architecture_challenge,
    arch_revise,
    approval_gate,
    sinan_debrief,
    sinan_approval,
    final_spec,
)


def build_graph() -> StateGraph:
    """Build and return the full Sinan StateGraph (requirement + architecture layers)."""
    g = _register_all_nodes(StateGraph(HarnessBuilderState))

    g.set_entry_point("spec_expansion")

    # ── 需求层：拓谱 → 诘问 → 辩论 → 用户表单 → 契约 ──
    g.add_edge("spec_expansion", "spec_challenge")
    g.add_edge("spec_challenge", "brief_debate")
    g.add_edge("brief_debate", "sinan_debrief")
    g.add_edge("sinan_debrief", "brief_compile")
    g.add_edge("brief_compile", "framework_design")

    _wire_architecture_edges(g)
    return g


def build_architecture_graph() -> StateGraph:
    """Build a graph that skips the requirement layer.

    Use when the user_brief_form is already on disk (e.g. via
    `python -m sinan.cli --from-brief <run_id>`) — entry point is
    framework_design, so the architecture layer runs against the
    pre-existing brief without re-prompting the user.
    """
    g = _register_all_nodes(StateGraph(HarnessBuilderState))
    g.set_entry_point("framework_design")
    _wire_architecture_edges(g)
    return g


def _register_all_nodes(g: StateGraph) -> StateGraph:
    """Register every design-layer node on the graph."""
    g.add_node("spec_expansion", _wrap(spec_expansion.spec_expansion_node))
    g.add_node("spec_challenge", _wrap(spec_challenge.spec_challenge_node))
    g.add_node("brief_debate", _wrap(brief_debate.brief_debate_node))
    g.add_node("brief_compile", _wrap(brief_compile.brief_compile_node))

    # ── Architecture layer: framework debate (4-step) ──
    g.add_node("framework_design", _wrap(framework_design.framework_design_node))
    g.add_node("subagent_review", _wrap(subagent_review.subagent_review_node))
    g.add_node("framework_adjust", _wrap(framework_adjust.framework_adjust_node))
    g.add_node("zonggong_integrate", _wrap(zonggong_integrate.zonggong_integrate_node))

    # ── Architecture review & gate ──
    g.add_node("architecture_challenge", _wrap(architecture_challenge.architecture_challenge_node))
    g.add_node("arch_revise", _wrap(arch_revise.arch_revise_node))
    g.add_node("approval_gate", _wrap(approval_gate.approval_gate_node))

    # ── User interaction ──
    g.add_node("sinan_debrief", _wrap(sinan_debrief.sinan_debrief_node))
    g.add_node("sinan_approval", _wrap(sinan_approval.sinan_approval_node))

    # ── Final output ──
    g.add_node("final_spec", _wrap(final_spec.final_spec_node))
    return g


def _wire_architecture_edges(g: StateGraph) -> None:
    """Wire all architecture-layer edges (shared by full and architecture-only graphs)."""
    g.add_edge("framework_design", "subagent_review")
    g.add_edge("subagent_review", "framework_adjust")
    g.add_edge("framework_adjust", "zonggong_integrate")
    g.add_edge("zonggong_integrate", "architecture_challenge")
    g.add_edge("architecture_challenge", "approval_gate")
    g.add_edge("arch_revise", "framework_design")

    # ── 守门路由：基于 risk_level ──
    g.add_conditional_edges(
        "approval_gate",
        _approval_gate_router,
        {
            "sinan_approval": "sinan_approval",
            "final_spec": "final_spec",
        },
    )

    # ── 用户审批结果路由 ──
    g.add_conditional_edges(
        "sinan_approval",
        _approval_outcome_router,
        {
            "arch_revise": "arch_revise",
            "final_spec": "final_spec",
        },
    )

    # ── 终态 ──
    g.add_edge("final_spec", END)


def _wrap(fn):
    """Wrap a node function so it receives and returns state dicts."""
    def wrapper(state: HarnessBuilderState) -> dict:
        return fn(state)
    return wrapper


def _approval_gate_router(state: HarnessBuilderState) -> str:
    """Route based on Shoumen's risk_level: low = auto-pass, else = user approval."""
    risk_level = state.get("gate_flags", {}).get("risk_level", "high")
    if risk_level == "low":
        return "final_spec"
    return "sinan_approval"


def _approval_outcome_router(state: HarnessBuilderState) -> str:
    """Handle user approval/reject/request_changes outcome."""
    payload = state.get("resume_payload") or {}
    choice = payload.get("approval", "")

    reject_count = state.get("arch_reject_count", 0)
    if choice in ("reject", "request_changes") and reject_count >= 2:
        raise RuntimeError(
            f"Architecture rejected {reject_count} times. "
            "Maximum retry limit reached. Please review the design manually."
        )

    if choice == "approve":
        return "final_spec"
    return "arch_revise"


def compile_graph() -> StateGraph:
    """Compile the full pipeline (requirement + architecture layers)."""
    return build_graph().compile()


def compile_architecture_graph() -> StateGraph:
    """Compile a graph that enters at framework_design (for --from-brief)."""
    return build_architecture_graph().compile()
