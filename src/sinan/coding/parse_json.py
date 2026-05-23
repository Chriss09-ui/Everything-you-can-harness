"""Shared JSON parsing utility for the coding harness."""
from __future__ import annotations
import json


def _parse_json(raw: str, artifact_name: str) -> dict:
    """Strip markdown fences and parse JSON."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].startswith("```") else lines[1:])
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        return {
            "error": f"Failed to parse {artifact_name}",
            "raw": raw[:500],
            "parse_error": str(e),
        }
