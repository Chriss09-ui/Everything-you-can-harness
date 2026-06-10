"""node_roles — 每个 LLM 调用节点的 (role, layer) 标签表。

需求层先建（5 个 node）。架构层 7 个 node 留给那位在改架构层代码的同事——
本表按需增量追加，不一次全列。

约定：
  - key: 与 LangGraph node 名一致（也即 state 里 current_phase 的值）
  - role: 人话角色名，写入 agent_trace.jsonl 的 agent_role 字段
  - layer: 顶层分组，目前固定 requirement / architecture
"""
from __future__ import annotations
from typing import TypedDict


class NodeRole(TypedDict):
    role: str
    layer: str


NODE_ROLES: dict[str, NodeRole] = {
    # 需求层
    "spec_expansion":    {"role": "tuopu",         "layer": "requirement"},
    "spec_challenge":    {"role": "jiewen",        "layer": "requirement"},
    "brief_debate":      {"role": "moderator",     "layer": "requirement"},
    "sinan_debrief":     {"role": "sinan_interact", "layer": "requirement"},
    "brief_compile":     {"role": "qiyue",         "layer": "requirement"},
}


def lookup(node: str) -> dict:
    """Return {'role': ..., 'layer': ...} for a node, or unknowns."""
    return NODE_ROLES.get(node, {"role": "unknown", "layer": "unknown"})
