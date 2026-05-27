"""End-to-end mock test for the coding harness."""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan.coding.state import make_coding_state
from sinan.coding.graph import compile_coding_graph
from sinan.coding.mock_responses import register_coding_mock_responses
from sinan.artifacts import ensure_run_dir, get_run_dir


def test_coding_e2e_happy_path(monkeypatch):
    """Full coding pipeline with mock LLM: planner → sprint_complete → END."""
    register_coding_mock_responses()

    # Patch git operations at every import site
    import sinan.coding.git as git_mod
    monkeypatch.setattr(git_mod, "git_init", lambda run_id: "git initialized")
    monkeypatch.setattr(git_mod, "git_commit", lambda run_id, msg: "committed")
    monkeypatch.setattr(git_mod, "git_log", lambda run_id, n=5: "abc123 feat_001")
    monkeypatch.setattr(git_mod, "git_diff", lambda run_id: "")
    monkeypatch.setattr(git_mod, "git_status", lambda run_id: "")
    monkeypatch.setattr(git_mod, "git_save_good_commit", lambda run_id, state: None)

    # Patch from-import references in node modules
    import sinan.coding.nodes.init_git as ig_mod
    monkeypatch.setattr(ig_mod, "git_init", lambda run_id: "git initialized")
    import sinan.coding.nodes.read_git_log as rgl_mod
    monkeypatch.setattr(rgl_mod, "git_log", lambda run_id, n=5: "abc123 feat_001")
    import sinan.coding.nodes.commit_feature as cf_mod
    monkeypatch.setattr(cf_mod, "git_commit", lambda run_id, msg: "committed")
    monkeypatch.setattr(cf_mod, "git_save_good_commit", lambda run_id, state: None)
    import sinan.coding.nodes.bug_triage as bt_mod
    monkeypatch.setattr(bt_mod, "git_diff", lambda run_id: "")
    monkeypatch.setattr(bt_mod, "git_revert", lambda run_id, ref: "reverted")
    monkeypatch.setattr(bt_mod, "git_status", lambda run_id: "")

    # Patch subprocess.run so the runner-cum-test harness doesn't actually
    # spawn python3 against our mock main.py. Return a CompletedProcess with
    # exit 0 and a JSON-yielding stdout so _evaluate_case sees a clean pass.
    import subprocess
    from subprocess import CompletedProcess
    def _fake_run(*args, **kwargs):
        return CompletedProcess(args=args, returncode=0, stdout='{"ok": true}', stderr="")
    monkeypatch.setattr(subprocess, "run", _fake_run)

    # Patch input() for any interactive prompts
    monkeypatch.setattr("builtins.input", lambda p="": "done")

    run_id = f"test_coding_e2e_{uuid.uuid4().hex[:8]}"
    ensure_run_dir(run_id)

    # A valid harness_design_draft carries the full schema (see
    # sinan/validation.py _REQUIRED_FIELDS["harness_design_draft"]). The
    # planner now enforces it strictly — a hand-rolled fixture that's missing
    # any required field would surface as a ValueError from the schema guard.
    draft = {
        "version": "1.0",
        "use_case": "Test coding harness",
        "primary_goal": "Test coding harness",
        "scope": {"inclusions": [], "exclusions": []},
        "success_criteria": ["smoke test passes"],
        "test_cases": [],
        "graph": {"nodes": [], "edges": [], "entry_point": "start", "end_state": "END"},
        "phase_sequence": ["plan", "implement", "review"],
        "memory_module": {},
        "handoff_protocol": {},
        "eval_placements": {},
        "state_schema": {"required_fields": []},
    }

    state = make_coding_state(run_id, draft)
    graph = compile_coding_graph()

    # Run the graph through the happy path
    # Since mocks are registered by trigger keywords, we need to simulate
    # the flow by manually stepping through key states
    final = graph.invoke(state)

    # Final state MUST be either the end of the happy path (SPRINT_COMPLETE),
    # or queued for the next sprint (EVALUATOR_QA just finished). If it's
    # anything earlier, the pipeline has regressed and silently broken.
    assert final["current_phase"] in {
        "SPRINT_COMPLETE",       # any sprint finished
        "EVALUATOR_QA",          # just finished grading, about to complete
    }, f"unexpected final phase: {final['current_phase']}"

    # Spec MUST be present — planner is the first coding-layer node, so if it
    # didn't run, nothing else makes sense.
    assert final.get("spec") is not None, "planner did not produce spec"

    # Run directory must exist (sanity).
    run_dir = get_run_dir(run_id)
    assert run_dir.exists()
