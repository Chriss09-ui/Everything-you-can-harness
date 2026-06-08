#!/usr/bin/env bash
# PostToolUse hook: warn when editing sinan source without planning doc sync.
# Reads {tool_input.file_path} from stdin, emits a JSON additionalContext
# reminder naming the exact files that CLAUDE.md's "改动同步原则" table
# requires. Stdout JSON → injected back to model. Silent for unrelated paths.

set -u

f=$(jq -r '.tool_input.file_path // empty' 2>/dev/null)
[ -z "${f:-}" ] && exit 0

msg=""

case "$f" in
  */src/sinan/coding/graph.py)
    msg="刚改了 src/sinan/coding/graph.py。按 CLAUDE.md 「改动同步原则」必须同步：src/sinan/coding/NODES.md（Routes 列）+ docs/coding_layer.md（ASCII 流程图、Router 计数、State 字段表）。"
    ;;
  */src/sinan/coding/*.py)
    msg="刚改了研发层文件 ${f}。按 CLAUDE.md 「改动同步原则」必须同步：src/sinan/coding/NODES.md（Reads/Writes/Artifacts/Routes）+ docs/coding_layer.md（节点清单、Artifact 清单）。"
    ;;
  */src/sinan/state.py)
    msg="刚改了 src/sinan/state.py。按 CLAUDE.md 「改动同步原则」必须同步：docs/requirement_layer.md + docs/architecture_layer.md 的「State 字段」表（含字段名、类型、谁写、谁读）。"
    ;;
  */src/sinan/graph.py)
    msg="刚改了 src/sinan/graph.py。按 CLAUDE.md 「改动同步原则」必须同步：src/sinan/nodes/NODES.md（路由函数规范块、原则 1 表）+ docs/sinan_流程图_v2.md（ASCII 流程图、Router 计数、死循环保险丝）+ 涉及层的指南文档。"
    ;;
  */src/sinan/validation.py)
    msg="刚改了 src/sinan/validation.py。按 CLAUDE.md 「改动同步原则」必须同步：src/sinan/nodes/NODES.md（涉及 artifact schema 的行）+ tests/test_validation.py（_REQUIRED_FIELDS 测试）。"
    ;;
  # 需求层 nodes
  */src/sinan/nodes/intake.py|\
  */src/sinan/nodes/sinan_debrief.py|\
  */src/sinan/nodes/brief_debate.py|\
  */src/sinan/nodes/brief_compile.py|\
  */src/sinan/nodes/spec_expansion.py|\
  */src/sinan/nodes/spec_challenge.py)
    msg="刚改了需求层 node ${f}。按 CLAUDE.md 「改动同步原则」必须同步：src/sinan/nodes/NODES.md（该节点的 Reads/Writes/Artifacts/Routes 行 + 原则 1 表）+ docs/requirement_layer.md（节点清单、ASCII 流程图、State 字段、Artifact 清单）。"
    ;;
  # 架构层 nodes
  */src/sinan/nodes/framework_design.py|\
  */src/sinan/nodes/subagent_review.py|\
  */src/sinan/nodes/framework_adjust.py|\
  */src/sinan/nodes/zonggong_integrate.py|\
  */src/sinan/nodes/architecture_challenge.py|\
  */src/sinan/nodes/approval_gate.py|\
  */src/sinan/nodes/final_spec.py|\
  */src/sinan/nodes/sinan_approval.py|\
  */src/sinan/nodes/arch_revise.py)
    msg="刚改了架构层 node ${f}。按 CLAUDE.md 「改动同步原则」必须同步：src/sinan/nodes/NODES.md（该节点的 Reads/Writes/Artifacts/Routes 行 + 原则 1 表）+ docs/architecture_layer.md（节点清单、ASCII 流程图、State 字段、中间产物表、路由规范）。"
    ;;
esac

if [ -n "$msg" ]; then
  jq -nc --arg m "$msg" '{hookSpecificOutput:{hookEventName:"PostToolUse",additionalContext:$m}}'
fi
exit 0
