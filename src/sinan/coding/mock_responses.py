"""Mock LLM responses for the coding harness (testing only)."""
from __future__ import annotations
import json
from sinan.llm import MockLLMClient


def register_coding_mock_responses() -> None:
    MockLLMClient.register("Planner（规划者）", json.dumps({
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
    }, ensure_ascii=False))

    MockLLMClient.register("Sprint 目标", json.dumps({
        "sprint_goals": [
            {"feature_id": "feat_001", "acceptance_criteria": ["src/ 目录存在"]},
            {"feature_id": "feat_002", "acceptance_criteria": ["状态模块可导入"]},
        ],
        "priority_order": ["feat_001", "feat_002"],
        "estimated_sessions": 1,
    }, ensure_ascii=False))

    MockLLMClient.register("Sprint Negotiator", json.dumps({
        "agreed": True,
        "accepted_features": ["feat_001"],
        "rejected_features": [],
        "modification_requests": [],
        "summary": "Sprint 目标已达成一致",
    }, ensure_ascii=False))

    MockLLMClient.register("执行方案", json.dumps({
        "execution_order": ["feat_001"],
        "strategy": "先实现基础结构",
    }, ensure_ascii=False))

    # Generator's mock writes files under harness/ root. ``main.py`` MUST be
    # at harness/main.py (not harness/src/main.py) so the e2e runner can find
    # it; the runner's sanity check and smoke test both look there.
    MockLLMClient.register("请实现以下功能", json.dumps({
        "status": "implemented",
        "files": [
            {"path": "main.py", "content": "import json\nprint(json.dumps({'ok': True}))\n",
             "action": "create"},
            {"path": "src/__init__.py", "content": "", "action": "create"},
        ],
        "summary": "Feature implemented via mock",
    }, ensure_ascii=False))

    # (The "自评" mock was for the now-deleted generator_review self-eval node.
    # Removing it; if you reintroduce a self-eval node, re-add a mock here.)

    MockLLMClient.register("质量评估", json.dumps({
        "functionality": 8,
        "product_depth": 7,
        "visual_quality": 7,
        "code_quality": 8,
        "overall_pass": True,
        "summary": "Sprint 目标全部达成",
        "bugs": [],
    }, ensure_ascii=False))

    MockLLMClient.register("Bug 修复", json.dumps({
        "status": "fixed",
        "files": [
            {"path": "src/state.py", "content": "# patched\n", "action": "modify"},
        ],
        "self_test_passed": True,
        "summary": "Bugs fixed via mock",
    }, ensure_ascii=False))
