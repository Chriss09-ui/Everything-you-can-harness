"""Regression test for M13: subagent_review_node bails out fast on failure.

Validates the REAL node — not just a copy of the cancel pattern — so that any
future change to ``subagent_review.py`` that breaks the FIRST_EXCEPTION wiring
will fail this test. Earlier versions of this file tested a standalone
ThreadPoolExecutor snippet that had no connection to the node, so a broken
``subagent_review_node`` would still pass.

Strategy: monkeypatch ``_call_subagent`` with three controlled stubs (fast OK,
slow fail, very-slow OK), drive ``subagent_review_node`` end-to-end against a
tmp run dir, and assert it raises within well under the slow stub's runtime.
"""
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_subagent_review_node_fails_fast(tmp_path, monkeypatch):
    from sinan import artifacts as art
    monkeypatch.setattr(art, "RUNS_DIR", tmp_path / "runs")
    from sinan.nodes import subagent_review as mod

    call_log: list[tuple[str, float]] = []

    def fake_call_subagent(client, brief_text, framework_text, name, role, prompt_key):
        start = time.time()
        if name == "memory":
            call_log.append((name, time.time() - start))
            return {"design": {}, "review": {
                "agent_name": "memory",
                "incompatibilities": [],
                "missing_elements": [],
                "endorsed_elements": [],
                "summary": "fast ok",
            }}
        if name == "handoff":
            time.sleep(0.5)
            call_log.append((name, time.time() - start))
            raise RuntimeError("simulated handoff failure")
        if name == "eval":
            time.sleep(3.0)
            call_log.append((name, time.time() - start))
            return {"design": {}, "review": {
                "agent_name": "eval",
                "incompatibilities": [],
                "missing_elements": [],
                "endorsed_elements": [],
                "summary": "very slow ok",
            }}
        raise AssertionError(f"unexpected subagent: {name}")

    monkeypatch.setattr(mod, "_call_subagent", fake_call_subagent)
    monkeypatch.setattr(mod, "get_llm_client", lambda: object())

    state = {
        "run_id": "subagent_cancel_test",
        "user_brief_form": {"primary_goal": "x"},
        "framework_design": {"nodes": [], "edges": [], "entry_point": "x"},
        "artifact_versions": {},
    }

    art.ensure_run_dir(state["run_id"])

    start = time.time()
    with pytest.raises(RuntimeError, match="subagent failed during review"):
        mod.subagent_review_node(state)
    elapsed = time.time() - start

    # The slow stub sleeps 3.0s. If subagent_review_node were waiting on it,
    # elapsed would be ~3s. FIRST_EXCEPTION + cancel_futures should let us
    # exit shortly after the 0.5s failure fires.
    assert elapsed < 2.0, (
        f"subagent_review_node took {elapsed:.2f}s after a 0.5s failure; "
        f"expected < 2.0s. The slow subagent was likely waited on instead "
        f"of cancelled — check the FIRST_EXCEPTION + cancel_futures wiring."
    )
