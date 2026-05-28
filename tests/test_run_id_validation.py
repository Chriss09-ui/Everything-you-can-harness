"""Regression test for run_id path traversal (S2 round-2 audit).

``run_id`` originates from CLI --from-brief / --from-design arguments, so it's
untrusted user input. Before this fix, ``get_run_dir("../etc")`` resolved to
``<repo>/runs/../etc = <repo>/etc`` — letting the CLI read / write outside
``runs/`` entirely. The fix enforces ``^[A-Za-z0-9_-]+$`` at the entry point
so the path join can never escape.
"""
import pytest

from sinan.artifacts import ensure_run_dir, get_run_dir


@pytest.mark.parametrize("bad", [
    "../etc",
    "..",
    "./foo",
    "/tmp/abs",
    "foo/bar",
    "foo\\bar",
    ".hidden",
    "",
    "has space",
    "has/slash",
])
def test_get_run_dir_rejects_traversal(bad):
    with pytest.raises(ValueError, match="invalid run_id"):
        get_run_dir(bad)


@pytest.mark.parametrize("good", [
    "run_abc123",
    "run-foo",
    "USER_RUN_2025",
    "a",
    "x_1-y_2",
])
def test_get_run_dir_accepts_well_formed(good):
    assert get_run_dir(good).name == good


def test_ensure_run_dir_rejects_traversal():
    with pytest.raises(ValueError, match="invalid run_id"):
        ensure_run_dir("../escape")
