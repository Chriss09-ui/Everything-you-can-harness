"""agent_trace — 结构化 LLM 调用可观测日志。

每次 LLMClient.generate 调一次 trace_llm_call，append 一行 JSON 到
runs/<run_id>/agent_trace.jsonl。Append-only + 单行写：中断也不会破坏历史。

不在此模块做并发同步（节点串行执行，append 原子性由 OS 写入保证）。
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .artifacts import RUNS_DIR

_TRACELOG_FILENAME = "agent_trace.jsonl"
# 超过此大小则截断 raw_response（保留首尾各 _RAW_KEEP_BYTES 字节）
_RAW_TRUNCATE_BYTES = 50 * 1024
_RAW_KEEP_BYTES = 20 * 1024


def _truncate(value: Optional[str], limit: int = _RAW_TRUNCATE_BYTES) -> tuple[Any, bool]:
    if value is None:
        return None, False
    encoded = value.encode("utf-8", errors="replace")
    if len(encoded) <= limit:
        return value, False
    head = encoded[:_RAW_KEEP_BYTES].decode("utf-8", errors="replace")
    tail = encoded[-_RAW_KEEP_BYTES:].decode("utf-8", errors="replace")
    return f"{head}\n...<truncated {len(encoded) - 2*_RAW_KEEP_BYTES} bytes>...\n{tail}", True


def _trace_path(run_id: str) -> Path:
    if not run_id or not all(c.isalnum() or c in "-_" for c in run_id):
        raise ValueError(f"invalid run_id for trace: {run_id!r}")
    return RUNS_DIR / run_id / _TRACELOG_FILENAME


def trace_llm_call(
    *,
    run_id: Optional[str],
    agent_role: Optional[str],
    model: Optional[str],
    provider: Optional[str],
    attempt: int,
    system_prompt: Optional[str],
    user_prompt: Optional[str],
    raw_response: Optional[str],
    status: str,
    latency_ms: Optional[int] = None,
    parsed_artifact: Optional[str] = None,
    finish_reason: Optional[str] = None,
    error: Optional[str] = None,
    node: Optional[str] = None,
    layer: Optional[str] = None,
) -> Optional[str]:
    """Append a single JSONL event to runs/<run_id>/agent_trace.jsonl.

    Returns the trace_id (UUID4 str) on success, or None when run_id is
    missing/empty (i.e. caller did not opt into tracing — the LLM still
    ran normally, we just didn't record it).
    """
    if not run_id:
        return None

    raw_resp, raw_truncated = _truncate(raw_response)
    user_prompt_trunc, _ = _truncate(user_prompt, limit=200 * 1024)
    system_prompt_trunc, _ = _truncate(system_prompt, limit=200 * 1024)

    trace_id = uuid.uuid4().hex
    event: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "run_id": run_id,
        "trace_id": trace_id,
        "node": node,
        "agent_role": agent_role,
        "layer": layer,
        "model": model,
        "provider": provider,
        "attempt": attempt,
        "status": status,
        "latency_ms": latency_ms,
        "system_prompt": system_prompt_trunc,
        "user_prompt": user_prompt_trunc,
        "raw_response": raw_resp,
        "raw_response_truncated": raw_truncated,
        "parsed_artifact": parsed_artifact,
        "finish_reason": finish_reason,
        "error": error,
    }
    path = _trace_path(run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(event, ensure_ascii=False)
    # Best-effort write: trace failure must NOT break the LLM call.
    try:
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError as exc:
        # Print to stderr so the operator at least knows tracing broke.
        import sys
        print(f"[agent_trace] WARN: failed to write {path}: {exc}", file=sys.stderr)
    return trace_id
