"""Git operation wrappers using subprocess."""
from __future__ import annotations
import subprocess
from pathlib import Path
from typing import Optional
from ..artifacts import get_run_dir, append_progress_log


def _run_git(run_id: str, *args: str, cwd: Optional[Path] = None) -> subprocess.CompletedProcess:
    """Run a git command in the harness project directory."""
    if cwd is None:
        cwd = get_run_dir(run_id) / "harness"
    try:
        result = subprocess.run(
            ["git"] + list(args),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, 1, "", "git command timed out")
    except FileNotFoundError:
        return subprocess.CompletedProcess(args, 1, "", "git not found")


def git_init(run_id: str) -> str:
    """Initialize a git repository in the harness project directory."""
    harness_dir = get_run_dir(run_id) / "harness"
    harness_dir.mkdir(parents=True, exist_ok=True)
    result = _run_git(run_id, "init", cwd=harness_dir)
    msg = result.stdout.strip() or result.stderr.strip() or "git init done"
    append_progress_log(run_id, "GIT", f"Initialized git repo: {msg}")
    return msg


def git_commit(run_id: str, message: str) -> str:
    """Commit current changes with the given message."""
    # Stage all files
    _run_git(run_id, "add", "-A")
    result = _run_git(run_id, "commit", "-m", message)
    msg = result.stdout.strip() or result.stderr.strip()
    append_progress_log(run_id, "GIT", f"git commit: {message[:60]}")
    return msg


def git_diff(run_id: str) -> str:
    """Return the diff of uncommitted changes."""
    result = _run_git(run_id, "diff", "--stat")
    return result.stdout.strip()


def git_status(run_id: str) -> str:
    """Return git status summary."""
    result = _run_git(run_id, "status", "--short")
    return result.stdout.strip()


def git_log(run_id: str, n: int = 5) -> str:
    """Return the last n commits as a summary string."""
    result = _run_git(
        run_id,
        "log", f"--oneline", f"-{n}",
        "--format=%h %s (%an)",
    )
    return result.stdout.strip()


def git_revert(run_id: str, ref: str) -> str:
    """Revert to the given git ref (commit hash or branch)."""
    result = _run_git(run_id, "revert", "--no-commit", ref)
    msg = result.stdout.strip() or result.stderr.strip()
    _run_git(run_id, "revert", "--abort")  # abort the revert merge, just check status
    # Actually do a reset instead
    result = _run_git(run_id, "reset", "--hard", ref)
    msg = result.stdout.strip()
    append_progress_log(run_id, "GIT", f"Reverted to {ref}: {msg}")
    return msg


def git_save_good_commit(run_id: str, state: dict) -> None:
    """Save the current HEAD as last_good_commit."""
    result = _run_git(run_id, "rev-parse", "HEAD")
    if result.returncode == 0:
        state["last_good_commit"] = result.stdout.strip()
        append_progress_log(run_id, "GIT", f"Saved good commit: {state['last_good_commit'][:7]}")
