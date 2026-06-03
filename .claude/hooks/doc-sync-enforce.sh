#!/usr/bin/env bash
# PreToolUse hook on Bash: enforce CLAUDE.md "改动同步原则".
# Detects `git commit` and inspects staged files.
# If staged set contains sinan source that requires doc sync, but no matching
# doc file is also staged, return decision:block — the commit will not execute.
#
# Exempt (CLAUDE.md:48): prompts.py / mock_responses.py / pure tests / pure docs.
# Bypass: there is no bypass. CLAUDE.md forbids --no-verify. If you genuinely
# disagree, edit this script temporarily or revert via `git reset HEAD~1`.

set -u

# Read tool_input.command from stdin JSON.
input=$(cat)
cmd=$(printf '%s' "$input" | jq -r '.tool_input.command // empty' 2>/dev/null)
[ -z "${cmd:-}" ] && exit 0

# Only act on `git commit ...` invocations (skip git add / push / etc.).
case "$cmd" in
  *git[\ _]commit*|*git\ -C\ *commit*) ;;
  *) exit 0 ;;
esac

# Grab staged files (only makes sense for git commit).
staged=$(git diff --cached --name-only 2>/dev/null)
if [ -z "$staged" ]; then
  exit 0
fi

# Accumulate expected doc paths across all triggering code files.
expected_docs=""

add_expected() {
  local docs="$1"
  for d in $docs; do
    case " $expected_docs " in
      *" $d "*) ;;
      *) expected_docs="$expected_docs $d" ;;
    esac
  done
}

# Accumulate which code files triggered.
triggered=""

# Classify each staged path.
while IFS= read -r f; do
  case "$f" in
    src/sinan/nodes/*.py)
      # Skip __init__ / pure non-node modules.
      case "$f" in
        src/sinan/nodes/__init__.py) continue ;;
      esac
      base=$(basename "$f" .py)
      case "$base" in
        intake|sinan_debrief|brief_debate|brief_compile|spec_expansion|spec_challenge)
          add_expected "src/sinan/nodes/NODES.md docs/requirement_layer.md"
          ;;
        framework_design|subagent_review|framework_adjust|zonggong_integrate|\
        architecture_challenge|approval_gate|final_spec|sinan_approval|arch_revise)
          add_expected "src/sinan/nodes/NODES.md docs/architecture_layer.md"
          ;;
        *)
          add_expected "src/sinan/nodes/NODES.md"
          ;;
      esac
      triggered="$triggered\n  - $f"
      ;;
    src/sinan/coding/nodes/*.py)
      add_expected "src/sinan/coding/NODES.md docs/coding_layer.md"
      triggered="$triggered\n  - $f"
      ;;
    src/sinan/graph.py)
      add_expected "src/sinan/nodes/NODES.md docs/architecture_layer.md docs/requirement_layer.md docs/sinan_流程图_v2.md"
      triggered="$triggered\n  - $f"
      ;;
    src/sinan/coding/graph.py)
      add_expected "src/sinan/coding/NODES.md docs/coding_layer.md"
      triggered="$triggered\n  - $f"
      ;;
    src/sinan/state.py)
      add_expected "docs/architecture_layer.md docs/requirement_layer.md"
      triggered="$triggered\n  - $f"
      ;;
    src/sinan/coding/state.py)
      add_expected "docs/coding_layer.md"
      triggered="$triggered\n  - $f"
      ;;
    src/sinan/validation.py)
      add_expected "src/sinan/nodes/NODES.md tests/test_validation.py src/sinan/coding/NODES.md"
      triggered="$triggered\n  - $f"
      ;;
    # Everything else (prompts.py / mock_responses.py / tests/* / docs/* /
    # run artifacts / frontend / .github / .claude) is exempt or out of scope.
  esac
done <<< "$staged"

# No triggering code → allow commit (e.g. pure test, pure doc, pure prompt).
[ -z "$triggered" ] && exit 0

# Check whether ANY expected doc is also staged.
synced=0
for doc in $expected_docs; do
  if printf '%s\n' "$staged" | grep -qxF "$doc"; then
    synced=1
    break
  fi
done

if [ "$synced" -eq 1 ]; then
  # Commit is OK — doc appears synced. Silent allow.
  exit 0
fi

# Build the block reason.
expected_bullets=""
for doc in $expected_docs; do
  [ -n "$expected_bullets" ] && expected_bullets="$expected_bullets"$'\n'
  expected_bullets="$expected_bullets  ✓ $doc"
done

reason=$(printf '🚫 文档未同步 — 已阻断 git commit。

按 CLAUDE.md「改动同步原则」："任何改动代码的 PR/commit，必须在同一个 commit 内同步更新对应合约文档。"

本次 commit 改了以下代码：%b

按速查表，至少需要同时 stage 以下文档之一（按改动类型多选）：
%b

当前 staged 列表里没有这些文件。

▼ 怎么解除阻断：
  1. 编辑对应文档（NODES.md / layer guide / 流程图 / validation）。
  2. git add <那些文档>
  3. 重新 git commit

▼ 如果本次确实是纯 typo / 纯 refactor 不影响契约：
  本 hook 不允许绕过。请把 commit 拆小到只含被豁免的文件（prompts.py /
  mock_responses.py / tests/），或在 PR 描述里显式说明并人工 review。
' "$triggered" "$expected_bullets")

jq -nc --arg r "$reason" '{decision:"block",reason:$r}'
exit 0
