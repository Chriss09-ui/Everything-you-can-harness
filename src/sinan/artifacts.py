"""Artifact persistence — run directory creation, JSON/YAML/MD file writes + version management."""
from __future__ import annotations
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Optional
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = PROJECT_ROOT / "runs"
_VERSION_REGISTRY = "version_registry.json"

# run_id may originate from CLI --from-brief / --from-design, so treat it as
# untrusted. ``../``, absolute paths, or hidden-dot prefixes would let a user
# escape ``runs/<run_id>/`` and read/write arbitrary locations. Lock to a
# conservative character set; everything else is rejected at the entry point
# instead of getting quietly joined past ``RUNS_DIR``.
import re as _re
_RUN_ID_RE = _re.compile(r"^[A-Za-z0-9_-]+$")


def _validate_run_id(run_id: str) -> None:
    if not isinstance(run_id, str) or not _RUN_ID_RE.match(run_id):
        raise ValueError(
            f"invalid run_id {run_id!r}: must be non-empty and match "
            f"{_RUN_ID_RE.pattern}"
        )

# Basenames that LLM-driven writes (implement_feature, generator_fix) must
# NEVER overwrite. ``init.sh`` is the acute risk: it is written by init_script
# from a hardcoded template and later executed via ``bash init.sh`` in
# session_setup. If an LLM could route ``{"path": "init.sh", "content": ...}``
# through implement_feature's path-traversal guard, the next sprint's session
# init would run attacker-controlled bash. Blocking the overwrite at the
# write-target layer (rather than the LLM input layer) is deterministic.
_CRITICAL_HARNESS_FILES = frozenset({
    "init.sh",
})


def assert_safe_llm_write_target(harness_dir: Path, rel_path: str) -> Path:
    """Resolve and guard an LLM-supplied write path inside a run's harness dir.

    Raises ``RuntimeError`` when:
      - the resolved path escapes ``harness_dir`` (path traversal)
      - the basename is in ``_CRITICAL_HARNESS_FILES`` (init.sh etc.)

    Returns the resolved ``Path`` on success. Callers should ``mkdir -p`` the
    parent before writing.
    """
    resolved = (harness_dir / rel_path).resolve()
    if not resolved.is_relative_to(harness_dir.resolve()):
        raise RuntimeError(f"Blocked path traversal: {rel_path!r}")
    if resolved.name in _CRITICAL_HARNESS_FILES:
        raise RuntimeError(
            f"Blocked write to critical harness file: {rel_path!r}"
        )
    return resolved


# ── Version Registry helpers ────────────────────────────────────────────────


def _get_registry(run_id: str) -> dict:
    path = get_run_dir(run_id) / _VERSION_REGISTRY
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def _save_registry(run_id: str, registry: dict) -> None:
    path = get_run_dir(run_id) / _VERSION_REGISTRY
    with open(path, "w", encoding="utf-8") as f:
        json.dump(registry, f, indent=2, ensure_ascii=False)


def _strip_version_suffix(name: str) -> str:
    """Strip _v<N> suffix from filename to get base name."""
    import re
    return re.sub(r"_v\d+$", "", name)


def get_artifact_versions(run_id: str, artifact_name: str) -> list[dict]:
    """Return all versions of an artifact, newest first."""
    registry = _get_registry(run_id)
    entries = registry.get(artifact_name, [])
    return sorted(entries, key=lambda x: x.get("version", 0), reverse=True)


def get_current_artifact(run_id: str, artifact_name: str) -> Optional[dict]:
    """Return the current (non-versioned) artifact if it exists."""
    registry = _get_registry(run_id)
    entry = registry.get(artifact_name, [])
    for e in entry:
        if e.get("current"):
            path = get_run_dir(run_id) / e["filename"]
            if path.exists():
                with open(path, encoding="utf-8") as f:
                    return json.load(f)
    return None


def load_state_or_file(
    state: dict,
    key: str,
    filename: Optional[str] = None,
    default: Any = None,
) -> Any:
    """Read ``state[key]`` if present and not None; otherwise read disk.

    Implements the project's "files are the only handoff protocol" principle
    at node read time: prefer the hot in-memory state, but fall back to disk
    so that any node can be re-entered after a crash or invoked independently
    (e.g. via --from-design / --from-brief).

    Presence rule (revised from the old truthy-check):
      - ``key`` not in state           → fall through to disk
      - ``state[key]`` is ``None``     → fall through to disk (matches the
        ``make_initial_state`` convention that ``None`` means "never produced
        by any node in this run")
      - ``state[key]`` is any other value (including ``{}``, ``[]``, ``""``,
        or ``False``) → return it. The node explicitly wrote that value.

    The old ``if value:`` check treated falsy-but-present values (especially
    empty lists/dicts that a node had legitimately written) as "missing" and
    silently read stale disk content. The new rule uses ``is not None`` so an
    upstream that produces empty still wins over disk.

    Args:
        state: the LangGraph state dict (must contain "run_id").
        key:   state field name to look up.
        filename: artifact filename relative to runs/<run_id>/. Defaults to
                  ``"<key>.json"`` which matches the project convention.
        default: value returned when both state and file are missing/empty.
                 Defaults to ``{}`` for dict-shaped artifacts.

    Returns the state value, the loaded JSON, or ``default``.
    """
    if key in state and state[key] is not None:
        return state[key]
    run_id = state.get("run_id")
    if not run_id:
        return {} if default is None else default
    fname = filename or f"{key}.json"
    path = get_run_dir(run_id) / fname
    if path.exists():
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {} if default is None else default


def get_artifact_summary(run_id: str) -> dict:
    """Return a summary of all artifacts and their version counts."""
    registry = _get_registry(run_id)
    summary = {}
    for artifact, entries in registry.items():
        summary[artifact] = {
            "total_versions": len(entries),
            "current_version": next((e["version"] for e in entries if e.get("current")), None),
            "versions": sorted([e["version"] for e in entries]),
        }
    return summary


# ── Core artifact I/O ──────────────────────────────────────────────────────


def get_run_dir(run_id: str) -> Path:
    _validate_run_id(run_id)
    return RUNS_DIR / run_id


def ensure_run_dir(run_id: str) -> Path:
    path = get_run_dir(run_id)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _load_yaml_mapping(path: Path) -> dict:
    """Load a YAML mapping, tolerating malformed state files from previous runs."""
    try:
        with open(path, encoding="utf-8") as f:
            loaded = yaml.safe_load(f) or {}
    except (yaml.YAMLError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def write_json(
    run_id: str,
    filename: str,
    data: Any,
    versioned: bool = False,
    version_note: str = "",
) -> Path:
    """Write a JSON artifact. If versioned=True and the file already exists,
    archive the old version before writing the new one.

    Uses atomic-rename so a crash mid-write leaves the previous version intact
    instead of a truncated file (rare in practice but unrecoverable when it
    happens — the next node would JSONDecodeError on the half-file).
    """
    run_dir = ensure_run_dir(run_id)
    path = run_dir / filename

    if versioned and path.exists():
        _archive_artifact(run_id, filename, version_note)

    _atomic_write_json(path, data)

    if versioned:
        # Register the new un-versioned file as the current version, so
        # get_current_artifact / get_artifact_summary can locate it. Previously
        # this step was missing — the registry only had archived entries with
        # current=False, so callers couldn't tell which version was "live".
        _register_current(run_id, filename)
    return path


def _register_current(run_id: str, filename: str) -> None:
    """Record the un-versioned file as the live current version in the registry."""
    from datetime import datetime, timezone
    registry = _get_registry(run_id)
    base_name = _strip_version_suffix(filename.replace(".json", ""))
    existing = registry.get(base_name, [])
    next_version = max([e["version"] for e in existing], default=0) + 1
    # If an older "current" entry already exists, demote it.
    for e in existing:
        if e.get("current") and e["filename"] == filename:
            # Already registered as current; nothing to do.
            return
    # Drop any stale current flag from prior entries.
    for e in existing:
        if e.get("current"):
            e["current"] = False
    existing.append({
        "version": next_version,
        "filename": filename,
        "current": True,
        "registered_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "note": "Live version",
    })
    registry[base_name] = existing
    _save_registry(run_id, registry)


def _atomic_write_json(path: Path, data: Any) -> None:
    """Write data as JSON to path atomically: write to tmp, then os.replace."""
    fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup; ignore failures (the replace-or-raise contract
        # is what matters).
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def _archive_artifact(run_id: str, filename: str, note: str = "") -> None:
    """Archive the existing live artifact under its already-assigned version.

    The old data on disk was registered as v(N) by the previous
    ``_register_current`` call. We keep that version number on the archive copy
    (renaming the live filename to ``<base>_v<N>.json``) and demote the
    registry entry to ``current=False``. The follow-up ``_register_current``
    then assigns v(N+1) to the new live file. Each write increments the
    version exactly once — the archived version number always matches the
    contents.

    Fallback: if no current entry exists in the registry (an un-tracked file
    that's being archived for the first time), we assign the next available
    version number rather than failing.
    """
    from datetime import datetime, timezone
    run_dir = get_run_dir(run_id)
    current_path = run_dir / filename
    if not current_path.exists():
        return

    with open(current_path, encoding="utf-8") as f:
        current_data = json.load(f)

    registry = _get_registry(run_id)
    base_name = _strip_version_suffix(filename.replace(".json", ""))
    existing = registry.get(base_name, [])

    current_entry = next(
        (e for e in existing if e.get("current") and e["filename"] == filename),
        None,
    )
    if current_entry is not None:
        archived_version = current_entry["version"]
    else:
        archived_version = max([e["version"] for e in existing], default=0) + 1

    archived_name = f"{base_name}_v{archived_version}.json"
    archived_path = run_dir / archived_name
    with open(archived_path, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2, ensure_ascii=False)

    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    if current_entry is not None:
        # Mutate in place: same version number, new filename, no longer current.
        current_entry["filename"] = archived_name
        current_entry["current"] = False
        current_entry["archived_at"] = timestamp
        if note:
            current_entry["note"] = note
    else:
        for e in existing:
            e["current"] = False
        existing.append({
            "version": archived_version,
            "filename": archived_name,
            "current": False,
            "archived_at": timestamp,
            "note": note or "Auto-archived (untracked predecessor)",
        })
        registry[base_name] = existing

    _save_registry(run_id, registry)


def write_yaml(run_id: str, filename: str, data: Any) -> Path:
    path = ensure_run_dir(run_id) / filename
    _atomic_write(path, lambda f: yaml.dump(data, f, default_flow_style=False, allow_unicode=True))
    return path


def write_md(run_id: str, filename: str, content: str) -> Path:
    path = ensure_run_dir(run_id) / filename
    _atomic_write(path, lambda f: f.write(content))
    return path


def _atomic_write(path: Path, writer) -> None:
    """Generic atomic-write helper: writer is called with an open file handle."""
    fd, tmp_path = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            writer(f)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def update_run_state(run_id: str, phase: str, **kwargs) -> None:
    """Append/update phase entry in run_state.yaml."""
    state_path = ensure_run_dir(run_id) / "run_state.yaml"
    if state_path.exists():
        state = _load_yaml_mapping(state_path)
    else:
        state = {
            "run_id": run_id,
            "started_at": "",
            "phase_history": [],
            "gate_status": {"spec_gate": {}, "arch_gate": {}},
            "artifact_versions": {},
        }

    state["current_phase"] = phase
    from datetime import datetime, timezone
    state["last_updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    if "started_at" in kwargs:
        state["started_at"] = kwargs["started_at"]

    # Append phase history entry
    entry = {
        "phase": phase,
        "entered_at": state["last_updated"],
        "exited_at": None,
        "status": "in_progress",
    }
    # Mark previous entry as completed
    for h in state.get("phase_history", []):
        if h.get("status") == "in_progress":
            h["exited_at"] = state["last_updated"]
            h["status"] = "completed"
    state.setdefault("phase_history", []).append(entry)

    _atomic_write(
        state_path,
        lambda f: yaml.dump(state, f, default_flow_style=False, allow_unicode=True),
    )


def finalize_phase(run_id: str) -> None:
    """Mark current phase as completed."""
    state_path = get_run_dir(run_id) / "run_state.yaml"
    if not state_path.exists():
        return
    state = _load_yaml_mapping(state_path)
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    for h in state.get("phase_history", []):
        if h.get("status") == "in_progress":
            h["exited_at"] = now
            h["status"] = "completed"
            break
    _atomic_write(
        state_path,
        lambda f: yaml.dump(state, f, default_flow_style=False, allow_unicode=True),
    )


def append_decision_log(run_id: str, decision: dict) -> None:
    log_path = ensure_run_dir(run_id) / "decision_log.md"
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry = f"\n## [{timestamp}] {decision.get('phase', '?')} | {decision.get('type', 'decision')}\n\n"
    entry += f"**Decision:** {decision.get('content', '')}\n\n"
    if decision.get("rationale"):
        entry += f"**Rationale:** {decision['rationale']}\n\n"
    if decision.get("risks"):
        # ``risks`` may be a list of strings or dicts. Render as markdown
        # bullets instead of the Python repr (``['a', 'b']``) which no
        # human reader can scan.
        risks = decision["risks"]
        if isinstance(risks, list):
            entry += "**Risks:**\n\n"
            for r in risks:
                if isinstance(r, dict):
                    item = r.get("item") or r.get("description") or ""
                else:
                    item = str(r)
                entry += f"- {item}\n"
            entry += "\n"
        else:
            entry += f"**Risks:** {risks}\n\n"
    with open(log_path, "a") as f:
        f.write(entry)


def append_progress_log(run_id: str, phase: str, message: str) -> None:
    log_path = ensure_run_dir(run_id) / "progress_log.md"
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry = f"- [{timestamp}] **{phase}**: {message}\n"
    with open(log_path, "a") as f:
        f.write(entry)
