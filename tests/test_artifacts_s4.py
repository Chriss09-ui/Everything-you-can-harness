"""Regression tests for load_state_or_file — specifically the S4 fix.

Before S4, the helper used ``if value:`` to decide whether state had the
artifact. Empty lists / dicts / 0 / False / "" all counted as "missing" and
caused the helper to silently fall back to disk. This file pins the new
"present-and-not-None" rule.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan.artifacts import (
    ensure_run_dir,
    get_run_dir,
    load_state_or_file,
    write_json,
)


def test_returns_explicit_empty_dict_over_disk(tmp_path, monkeypatch):
    """If state has {} for the key, return {} — don't read stale disk file."""
    from sinan import artifacts as art
    runs = tmp_path / "runs"
    monkeypatch.setattr(art, "RUNS_DIR", runs)

    run_id = "s4_empty_dict"
    ensure_run_dir(run_id)
    # Write stale data to disk
    write_json(run_id, "foo.json", {"stale": True})

    state = {"run_id": run_id, "foo": {}}
    got = load_state_or_file(state, "foo")
    assert got == {}, f"expected empty dict, got {got!r}"


def test_returns_explicit_empty_list_over_disk(tmp_path, monkeypatch):
    """If state has [] for the key, return [] — don't read stale disk file."""
    from sinan import artifacts as art
    runs = tmp_path / "runs"
    monkeypatch.setattr(art, "RUNS_DIR", runs)

    run_id = "s4_empty_list"
    ensure_run_dir(run_id)
    write_json(run_id, "bar.json", ["stale", "data"])

    state = {"run_id": run_id, "bar": []}
    got = load_state_or_file(state, "bar")
    assert got == [], f"expected empty list, got {got!r}"


def test_none_in_state_falls_through_to_disk(tmp_path, monkeypatch):
    """If state has explicit None, that's the make_initial_state placeholder —
    fall back to disk so resumes work."""
    from sinan import artifacts as art
    runs = tmp_path / "runs"
    monkeypatch.setattr(art, "RUNS_DIR", runs)

    run_id = "s4_none"
    ensure_run_dir(run_id)
    write_json(run_id, "baz.json", {"on": "disk"})

    state = {"run_id": run_id, "baz": None}
    got = load_state_or_file(state, "baz")
    assert got == {"on": "disk"}, f"expected disk data, got {got!r}"


def test_key_not_in_state_falls_through_to_disk(tmp_path, monkeypatch):
    """If the key isn't in state at all, fall back to disk."""
    from sinan import artifacts as art
    runs = tmp_path / "runs"
    monkeypatch.setattr(art, "RUNS_DIR", runs)

    run_id = "s4_missing"
    ensure_run_dir(run_id)
    write_json(run_id, "qux.json", {"from": "disk"})

    state = {"run_id": run_id}
    got = load_state_or_file(state, "qux")
    assert got == {"from": "disk"}, f"expected disk data, got {got!r}"


def test_no_state_no_disk_returns_default(tmp_path, monkeypatch):
    """No state, no disk → use default ({} if not given)."""
    from sinan import artifacts as art
    runs = tmp_path / "runs"
    monkeypatch.setattr(art, "RUNS_DIR", runs)

    run_id = "s4_default"
    ensure_run_dir(run_id)

    state = {"run_id": run_id}
    got = load_state_or_file(state, "ghost")
    assert got == {}, f"expected default {{}}, got {got!r}"

    got = load_state_or_file(state, "ghost", default=[])
    assert got == [], f"expected explicit default [], got {got!r}"
