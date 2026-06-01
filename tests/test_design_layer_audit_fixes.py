"""Regression tests for design-layer audit fixes (H1 / H3 / H4 / M1).

These pin behaviors that were buggy or fragile before the fixes:

  - H1: ``architecture_challenge`` previously concat'd new arch_risk entries
    onto ``risk_register`` every revision round, accumulating stale risks
    the architect had already fixed. We run 3 reject rounds and verify
    the post-run register only carries ONE round of arch_risk entries
    (not 3×).

  - H3: ``sinan_debrief_node`` previously called
    ``display.get("user_questions")`` without checking that ``display``
    was a dict. Schema only required the key, not the shape. With a
    string-valued ``display`` from the LLM, the node crashed. Verify it
    now degrades to an empty UI instead of raising.

  - H4: ``sinan_debrief_node`` question prompt used ``input()`` without
    an EOFError handler — non-interactive env (CI, piped stdin) crashed.
    Verify it now treats EOF as a skip and continues.

  - M1: ``append_decision_log`` previously wrote the risks list as Python
    repr (``"['a', 'b']"``) into the markdown log. Now renders as bullets.
"""
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


# ── H1: revision loop hygiene on risk_register ─────────────────────────────


def test_arch_challenge_drops_prior_arch_risks_before_appending(monkeypatch):
    """Unit-test that architecture_challenge drops its own type=arch_risk entries
    from risk_register before appending the new round. Does NOT run the full
    graph (which requires many LLM calls and is slow on M4)."""
    from unittest.mock import MagicMock
    from sinan.nodes import architecture_challenge
    from sinan.state import make_initial_state

    run_id = f"audit_h1u_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state["run_id"] = run_id
    # Pre-populate: 2 existing arch_risk entries (simulating 2 prior rounds)
    # + 1 ambiguity entry (spec_challenge's, must survive).
    state["risk_register"] = [
        {"type": "arch_risk", "item": "old risk round 1"},
        {"type": "arch_risk", "item": "old risk round 2"},
        {"type": "ambiguity", "item": "goal unclear"},
    ]

    # Mock LLM → returns a minimal architecture_review with arch_risk tags.
    mock_llm = MagicMock()
    mock_llm.generate.return_value = __import__("json").dumps({
        "over_engineering_flags": ["new flag"],
        "handoff_gaps": [],
        "eval_gaps": [],
        "failure_mode_omissions": [],
        "cost_complexity_concerns": [],
        "challenge_score": 5,
        "recommendation": "proceed",
    })
    monkeypatch.setattr(
        "sinan.nodes.architecture_challenge.get_llm_client",
        lambda: mock_llm,
    )
    monkeypatch.setattr(
        "sinan.nodes.architecture_challenge.get_prompt",
        lambda _: "system",
    )
    # Mock file writes so we don't need a real run dir on disk for the test.
    monkeypatch.setattr(
        "sinan.nodes.architecture_challenge.write_json",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "sinan.nodes.architecture_challenge.update_run_state",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "sinan.nodes.architecture_challenge.append_progress_log",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "sinan.nodes.architecture_challenge.append_decision_log",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "sinan.nodes.architecture_challenge.finalize_phase",
        lambda *a, **kw: None,
    )

    result = architecture_challenge.architecture_challenge_node(state)

    # The two prior arch_risks must be gone; the new round's risks must be present.
    arch_risks = [r for r in result["risk_register"] if r["type"] == "arch_risk"]
    assert len(arch_risks) == 1, (
        f"expected 1 arch_risk (new round only), got {len(arch_risks)}: {arch_risks}"
    )
    assert arch_risks[0]["item"] == "new flag"

    # spec_challenge ambiguity must survive.
    ambiguity = [r for r in result["risk_register"] if r["type"] == "ambiguity"]
    assert len(ambiguity) == 1
    assert ambiguity[0]["item"] == "goal unclear"


# ── H3: sinan_debrief display type guard ───────────────────────────────────


def test_sinan_debrief_handles_string_display(monkeypatch):
    """If LLM returns ``{"display": "text"}``, sinan_debrief should degrade
    to an empty UI instead of AttributeError. The flow continues to brief_debate
    downstream so we just need to survive the call and write progress."""
    from sinan.state import make_initial_state
    from sinan.nodes import sinan_debrief
    from sinan.artifacts import append_progress_log
    from sinan.llm import MockLLMClient

    # Register a malformed response keyed off part of the prompt
    import json
    MockLLMClient.register("司南与用户", json.dumps({"display": "bad shape"},
                                                    ensure_ascii=False))

    run_id = f"audit_h3_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state["brief_debate"] = {
        "aligned_points": [],
        "remaining_disagreements": [],
        "user_questions": [],
    }
    state["run_id"] = run_id

    # Provide enough empty inputs so the (empty) question loop and proceed
    # gate don't hang. Since display.user_questions is empty after coercion,
    # the question loop is skipped; proceed/skip paths use these.
    inputs = iter(["proceed"])
    monkeypatch.setattr("builtins.input", lambda p="": next(inputs))

    # Should not raise AttributeError on .get(...) of a string.
    out = sinan_debrief.sinan_debrief_node(state)
    assert "user_brief_answers" in out
    assert out["user_brief_answers"] == []  # no questions shown → no answers


# ── H4: sinan_debrief EOF tolerance on question input ─────────────────────


def test_sinan_debrief_eof_on_question_treated_as_skip(monkeypatch):
    """input() raising EOFError on the question prompt should be treated as
    a skip rather than crashing."""
    import json
    from sinan.state import make_initial_state
    from sinan.nodes import sinan_debrief
    from sinan.llm import MockLLMClient

    MockLLMClient.register("司南与用户", json.dumps({
        "display": {
            "header": "test",
            "user_questions": ["q1", "q2"],
            "aligned_points": [],
            "remaining_disagreements": [],
            "question_instruction": "skip",
        }
    }, ensure_ascii=False))

    run_id = f"audit_h4u_{uuid.uuid4().hex[:6]}"
    state = make_initial_state(run_id)
    state["brief_debate"] = {
        "aligned_points": [],
        "remaining_disagreements": [],
        "user_questions": ["q1", "q2"],
    }
    state["run_id"] = run_id

    call_count = [0]

    def fake_input(prompt=""):
        call_count[0] += 1
        # call 1, 2 → EOF on questions; call 3 → "proceed"; rest → ""
        if call_count[0] <= 2:
            raise EOFError()
        if call_count[0] == 3:
            return "proceed"
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    # Also mock all the file I/O that sinan_debrief does.
    monkeypatch.setattr(
        "sinan.nodes.sinan_debrief.append_progress_log",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "sinan.nodes.sinan_debrief.append_decision_log",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "sinan.nodes.sinan_debrief.finalize_phase",
        lambda *a, **kw: None,
    )
    monkeypatch.setattr(
        "sinan.nodes.sinan_debrief.update_run_state",
        lambda *a, **kw: None,
    )

    out = sinan_debrief.sinan_debrief_node(state)
    answers = out["user_brief_answers"]
    # Two questions, both EOF → both skipped.
    assert len(answers) == 2
    assert all(a["status"] == "skipped" for a in answers)
    # The proceed gate was reached (call_count >= 3 means we got past the
    # EOFError handlers and into the choice prompt).
    assert call_count[0] >= 3


# ── M1: decision_log risks rendered as bullets, not repr ───────────────────


def test_decision_log_renders_risk_list_as_bullets(tmp_path):
    """append_decision_log should render ``risks=[...]`` as one bullet per
    item, not ``"['a', 'b']"``."""
    from sinan.artifacts import append_decision_log, ensure_run_dir
    from sinan.llm import MockLLMClient  # noqa: F401  — keep import habit

    # Use a real run dir so we can read back the log. We bypass the run_id
    # validator indirectly: append_decision_log calls ensure_run_dir which
    # validates run_id format. Use a uuid-like name.
    run_id = f"audit_m1_{uuid.uuid4().hex[:6]}"
    ensure_run_dir(run_id)
    try:
        append_decision_log(run_id, {
            "phase": "TEST",
            "type": "decision",
            "content": "test entry",
            "risks": ["risk-a", "risk-b"],
        })
        from sinan.artifacts import get_run_dir
        log_text = (get_run_dir(run_id) / "decision_log.md").read_text()
        # Bullet form: each risk on its own line prefixed with "- ".
        assert "- risk-a" in log_text, (
            f"expected bullets, got: {log_text!r}"
        )
        assert "- risk-b" in log_text, (
            f"expected bullets, got: {log_text!r}"
        )
        # Python repr form should NOT be present.
        assert "['risk-a'," not in log_text
    finally:
        import shutil
        from sinan.artifacts import RUNS_DIR
        shutil.rmtree(RUNS_DIR / run_id, ignore_errors=True)


def test_decision_log_renders_dict_risks(tmp_path):
    """If risks are dicts (spec_challenge writes dicts with item/risk fields),
    bullet should show the ``item`` field."""
    import shutil
    from sinan.artifacts import append_decision_log, ensure_run_dir, get_run_dir
    from sinan.artifacts import RUNS_DIR

    run_id = f"audit_m1d_{uuid.uuid4().hex[:6]}"
    ensure_run_dir(run_id)
    try:
        append_decision_log(run_id, {
            "phase": "TEST",
            "type": "decision",
            "content": "dict risks",
            "risks": [
                {"item": "goal unclear", "risk_if_unaddressed": "scope creep"},
                {"item": "no test suite"},
            ],
        })
        log_text = (get_run_dir(run_id) / "decision_log.md").read_text()
        assert "- goal unclear" in log_text
        assert "- no test suite" in log_text
    finally:
        shutil.rmtree(RUNS_DIR / run_id, ignore_errors=True)
