"""Artifact persistence — run directory creation, JSON/YAML/MD file writes + version management."""
from __future__ import annotations
import json
import shutil
from pathlib import Path
from typing import Any, Optional
import yaml


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
RUNS_DIR = PROJECT_ROOT / "runs"
_VERSION_REGISTRY = "version_registry.json"


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
    """Read ``state[key]`` if present; otherwise read ``runs/<run_id>/<filename>``.

    Implements the project's "files are the only handoff protocol" principle
    at node read time: prefer the hot in-memory state, but fall back to disk
    so that any node can be re-entered after a crash or invoked independently
    (e.g. via --from-design / --from-brief).

    Args:
        state: the LangGraph state dict (must contain "run_id").
        key:   state field name to look up.
        filename: artifact filename relative to runs/<run_id>/. Defaults to
                  ``"<key>.json"`` which matches the project convention.
        default: value returned when both state and file are missing/empty.
                 Defaults to ``{}`` for dict-shaped artifacts.

    Returns the state value, the loaded JSON, or ``default``.
    """
    value = state.get(key)
    if value:
        return value
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
    archive the old version before writing the new one."""
    run_dir = ensure_run_dir(run_id)
    path = run_dir / filename

    if versioned and path.exists():
        _archive_artifact(run_id, filename, version_note)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def _archive_artifact(run_id: str, filename: str, note: str = "") -> None:
    """Archive the existing artifact with a new version number."""
    from datetime import datetime, timezone
    run_dir = get_run_dir(run_id)
    current_path = run_dir / filename
    if not current_path.exists():
        return

    # Read current content for comparison
    with open(current_path, encoding="utf-8") as f:
        current_data = json.load(f)

    registry = _get_registry(run_id)
    base_name = _strip_version_suffix(filename.replace(".json", ""))

    # Assign next version number
    existing = registry.get(base_name, [])
    next_version = max([e["version"] for e in existing], default=0) + 1

    # Write archived copy
    archived_name = f"{base_name}_v{next_version}.json"
    archived_path = run_dir / archived_name
    with open(archived_path, "w", encoding="utf-8") as f:
        json.dump(current_data, f, indent=2, ensure_ascii=False)

    # Update registry — mark old current as non-current
    for e in existing:
        e["current"] = False

    # Add new entry
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry = {
        "version": next_version,
        "filename": archived_name,
        "current": False,
        "archived_at": timestamp,
        "note": note or f"Auto-archived before overwriting with v{next_version + 1}",
    }
    existing.append(entry)
    registry[base_name] = existing

    _save_registry(run_id, registry)


def write_yaml(run_id: str, filename: str, data: Any) -> Path:
    path = ensure_run_dir(run_id) / filename
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return path


def write_md(run_id: str, filename: str, content: str) -> Path:
    path = ensure_run_dir(run_id) / filename
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path


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

    with open(state_path, "w") as f:
        yaml.dump(state, f, default_flow_style=False, allow_unicode=True)


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
    with open(state_path, "w") as f:
        yaml.dump(state, f, default_flow_style=False, allow_unicode=True)


def append_decision_log(run_id: str, decision: dict) -> None:
    log_path = ensure_run_dir(run_id) / "decision_log.md"
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry = f"\n## [{timestamp}] {decision.get('phase', '?')} | {decision.get('type', 'decision')}\n\n"
    entry += f"**Decision:** {decision.get('content', '')}\n\n"
    if decision.get("rationale"):
        entry += f"**Rationale:** {decision['rationale']}\n\n"
    if decision.get("risks"):
        entry += f"**Risks:** {decision['risks']}\n\n"
    with open(log_path, "a") as f:
        f.write(entry)


def append_progress_log(run_id: str, phase: str, message: str) -> None:
    log_path = ensure_run_dir(run_id) / "progress_log.md"
    from datetime import datetime, timezone
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    entry = f"- [{timestamp}] **{phase}**: {message}\n"
    with open(log_path, "a") as f:
        f.write(entry)
