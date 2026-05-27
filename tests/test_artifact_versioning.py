"""Regression test for the versioned write_json archiving rule.

Previously ``_archive_artifact`` allocated ``next_version = max+1`` for the
archive AND ``_register_current`` allocated another ``max+1`` for the new live
file. After two writes the registry contained three entries (v1 stale, v2
archive, v3 live), and the archived file's version number was one larger than
the data it contained. This test pins the corrected semantics: archived
version == version the data already had.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from sinan.artifacts import (
    ensure_run_dir,
    get_artifact_summary,
    get_artifact_versions,
    get_run_dir,
    write_json,
)


def test_two_versioned_writes_produce_two_entries(tmp_path, monkeypatch):
    from sinan import artifacts as art
    monkeypatch.setattr(art, "RUNS_DIR", tmp_path / "runs")

    run_id = "vers_two"
    ensure_run_dir(run_id)

    write_json(run_id, "design.json", {"v": 1}, versioned=True)
    write_json(run_id, "design.json", {"v": 2}, versioned=True)

    versions = get_artifact_versions(run_id, "design")
    assert [e["version"] for e in versions] == [2, 1], (
        f"after two writes, registry should have exactly [v2-current, v1-archive]; got {versions}"
    )

    current = [e for e in versions if e.get("current")]
    assert len(current) == 1 and current[0]["version"] == 2, (
        f"the live entry must be v2, got {current}"
    )

    archived = [e for e in versions if not e.get("current")]
    assert len(archived) == 1 and archived[0]["version"] == 1, (
        f"the archive must be v1 (the data it actually holds); got {archived}"
    )
    assert archived[0]["filename"] == "design_v1.json", archived[0]


def test_archived_file_content_matches_its_version(tmp_path, monkeypatch):
    """design_v1.json must hold the v1 payload, design_v2.json the v2 payload."""
    import json
    from sinan import artifacts as art
    monkeypatch.setattr(art, "RUNS_DIR", tmp_path / "runs")

    run_id = "vers_content"
    ensure_run_dir(run_id)

    write_json(run_id, "design.json", {"v": 1}, versioned=True)
    write_json(run_id, "design.json", {"v": 2}, versioned=True)
    write_json(run_id, "design.json", {"v": 3}, versioned=True)

    run_dir = get_run_dir(run_id)
    assert json.loads((run_dir / "design.json").read_text()) == {"v": 3}
    assert json.loads((run_dir / "design_v1.json").read_text()) == {"v": 1}
    assert json.loads((run_dir / "design_v2.json").read_text()) == {"v": 2}


def test_summary_reports_correct_current_version(tmp_path, monkeypatch):
    from sinan import artifacts as art
    monkeypatch.setattr(art, "RUNS_DIR", tmp_path / "runs")

    run_id = "vers_summary"
    ensure_run_dir(run_id)

    write_json(run_id, "design.json", {"v": 1}, versioned=True)
    write_json(run_id, "design.json", {"v": 2}, versioned=True)
    write_json(run_id, "design.json", {"v": 3}, versioned=True)

    summary = get_artifact_summary(run_id)["design"]
    assert summary["current_version"] == 3, summary
    assert summary["total_versions"] == 3, summary
    assert summary["versions"] == [1, 2, 3], summary
