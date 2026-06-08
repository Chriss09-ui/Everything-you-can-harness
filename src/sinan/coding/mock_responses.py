"""Mock agent responses for the coding harness (testing only).

All 7 coding-layer LLM nodes now run through the Claude Agent SDK seam, so the
mocks live on MockAgentRunner. Each entry maps a trigger substring to the
agent's structured output; the two code-writing nodes also carry ``files`` —
the side-effects a real agent's Write tool would produce.
"""
from __future__ import annotations
from sinan.agent import MockAgentRunner


def register_coding_mock_responses() -> None:
    # The 4 planning nodes now run through the agent seam with zero tools
    # (pure structured output). Registration ORDER matters: sprint_setup's
    # prompt contains both "Sprint 目标" and "执行方案"; MockAgentRunner takes
    # the LAST matching trigger, so "执行方案" must be registered after
    # "Sprint 目标" to win for sprint_setup while "Sprint 目标" still wins for
    # sprint_plan (whose prompt lacks "执行方案").
    MockAgentRunner.register("Planner（规划者）", {
        "name": "Test Harness",
        "description": "A test harness project",
        "tech_stack": ["Python", "LangGraph"],
        "project_structure": {"src": "source code", "tests": "test files"},
        "features": [
            {"id": "feat_001", "name": "基础项目结构", "description": "创建标准项目目录结构",
             "priority": 1, "depends_on": [], "acceptance_criteria": ["src/ 目录存在"], "passes": False},
            {"id": "feat_002", "name": "状态管理", "description": "实现状态管理模块",
             "priority": 2, "depends_on": ["feat_001"], "acceptance_criteria": ["状态模块可导入"], "passes": False},
        ],
        "success_criteria": ["项目可正常启动", "测试通过率 100%"],
    })

    MockAgentRunner.register("Sprint 目标", {
        "sprint_goals": [
            {"feature_id": "feat_001", "acceptance_criteria": ["src/ 目录存在"]},
            {"feature_id": "feat_002", "acceptance_criteria": ["状态模块可导入"]},
        ],
        "priority_order": ["feat_001", "feat_002"],
        "estimated_sessions": 1,
    })

    MockAgentRunner.register("Sprint Negotiator", {
        "agreed": True,
        "accepted_features": ["feat_001"],
        "rejected_features": [],
        "modification_requests": [],
        "summary": "Sprint 目标已达成一致",
    })

    MockAgentRunner.register("执行方案", {
        "execution_order": ["feat_001"],
        "strategy": "先实现基础结构",
    })

    # implement_feature now runs as a real agent (Claude Agent SDK). The mock
    # agent both (a) returns the structured report and (b) reproduces the file
    # side-effects a real agent's Write tool would make. ``main.py`` MUST be at
    # harness/main.py (not harness/src/main.py) so the e2e runner can find it;
    # the runner's sanity check and smoke test both look there.
    MockAgentRunner.register(
        "请在当前项目目录中实现以下功能",
        output={
            "status": "implemented",
            "files": [
                {"path": "main.py", "action": "create"},
                {"path": "src/__init__.py", "action": "create"},
            ],
            "summary": "Feature implemented via mock agent",
        },
        files=[
            {"path": "main.py",
             "content": "import json\nprint(json.dumps({'ok': True}))\n"},
            {"path": "src/__init__.py", "content": ""},
        ],
    )

    # (The "自评" mock was for the now-deleted generator_review self-eval node.
    # Removing it; if you reintroduce a self-eval node, re-add a mock here.)

    # evaluator_qa now runs as a read-only agent. No file side-effects (the
    # judge only reads); just the structured grade.
    MockAgentRunner.register(
        "质量评估",
        output={
            "functionality": 8,
            "product_depth": 7,
            "visual_quality": 7,
            "code_quality": 8,
            "overall_pass": True,
            "summary": "Sprint 目标全部达成",
            "bugs": [],
        },
    )

    # generator_fix now runs as a real agent. Mock returns the structured
    # report and reproduces the patched-file side-effect.
    MockAgentRunner.register(
        "请在当前项目目录中修复",
        output={
            "status": "fixed",
            "files": [{"path": "src/state.py", "action": "modify"}],
            "verified": True,
            "summary": "Bugs fixed via mock agent",
        },
        files=[{"path": "src/state.py", "content": "# patched\n"}],
    )
