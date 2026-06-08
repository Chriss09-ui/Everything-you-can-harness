# Coding Layer — Node Contract Reference

> 本文档是研发层开发规范。每个 node 模块遵循统一的 **Agent Handoff Contract**（代理交接契约），
> 明确"谁写什么、谁读什么"，使模型能快速上手而无需细读实现代码。

---

## 交接协议核心原则

### 原则 1：磁盘文件是跨 Session / 跨层的交接协议

**在单次 graph 调用内**，节点之间用 LangGraph 的 state 传递（`sprint_contract`、`evaluator_grade`、`bug_report` 等）。
**跨 Session、跨层、崩溃恢复**只能靠 `runs/<run_id>/` 下的文件，因为 state 不持久。

| 阶段 | 写入文件（交出） | 读取文件（接收） |
|------|-----------------|-----------------|
| planner | — | `harness_design_draft.json` (设计层→研发层入口，state 空时走 `load_state_or_file()`) |
| session_init (Sprint 1) | `claude-progress.txt`, `init.sh`, `feature_list.json`, git init | — |
| session_setup (每轮) | — | `claude-progress.txt`, `feature_list.json`, `git log`, pwd |
| commit_feature | `feature_list.json`, `claude-progress.txt`, git commit | — |
| sprint_negotiate | `sprint_contract.json` | — |
| evaluator_qa | `evaluator_grade.json` | — |
| evaluator_bugs | `bug_report.json` | — |
| generator_fix | 修复的文件 | — |
| implement_feature | 实现文件 | — |
| sprint_complete | `sprint_result.json` | — |

> **状态-或-磁盘 helper**：跨层交接（如 planner 读 `harness_design_draft`）统一走 `sinan.artifacts.load_state_or_file()`，
> 它先读 state、再回退到 `runs/<run_id>/<key>.json`。
> 跨 Session 的 harness/ 文件（feature_list、claude-progress 等）由对应节点直接读 disk，没有 state 影子。

### 原则 2：每个 Node 最多做一件事

- `implement_feature`：只实现，不测试，不提交
- `test_feature`：只运行测试，不修改代码
- `commit_feature`：只标记 + 提交，不决定下一步

### 原则 3：路由决策写在 graph.py，不写在 node 里

条件路由逻辑（if/else）集中在 graph 的 router 函数中，node 内部不包含路由分支。

### 原则 4：Node 永远返回完整 state dict

即使只改了一个字段，也返回整个 `state`，LangGraph 会自动合并。

---

## Node 合约模板

```python
"""<node_name> — <一句话描述>.

Agent: <Planner|Generator|Evaluator|Initializer>
Loop:  <Sprint|Session|Feature|Fix>

Reads:
    state["field"]  — 说明
    <artifact_file> — 说明（从磁盘读取）

Writes:
    state["field"]  — 说明
    <artifact_file> — 说明（写入磁盘）

Routes:
    → next_node  when <condition>
"""
```

---

## 26 Node 合约

### 1. planner

| 属性 | 值 |
|------|------|
| Agent | Planner（Claude Agent SDK，零工具，纯结构化输出） |
| Loop | Sprint (入口) |
| Reads | `harness_design_draft` (state, 优先) / `runs/<run_id>/harness_design_draft.json` (磁盘 fallback) |
| Writes | `spec`, `feature_list`, `current_phase` |
| Artifacts | `spec.json` |
| Routes | → `sprint_plan` (linear) |

> **跨层交接**：planner 是设计层 → 研发层的入口。优先从 state 读 draft；state 为空时从磁盘读，
> 让研发层可以独立启动（CLI 的 `--from-design <run_id>`）。

### 2. sprint_plan

| 属性 | 值 |
|------|------|
| Agent | Generator（Claude Agent SDK，零工具，纯结构化输出） |
| Loop | Sprint |
| Reads | `feature_list`, `bug_report` |
| Writes | `sprint_contract`, `current_phase` |
| Artifacts | `sprint_contract.json` (versioned) |
| Routes | → `sprint_negotiate` (linear) |

### 3. sprint_negotiate

| 属性 | 值 |
|------|------|
| Agent | Evaluator（Claude Agent SDK，零工具，纯结构化输出） |
| Loop | Sprint (协商 ≤3 轮) |
| Reads | `sprint_contract`, `negotiate_round` |
| Writes | `sprint_contract`, `negotiate_round` |
| Artifacts | `sprint_contract.json` (versioned) |
| Routes | → `sprint_setup` (agreed=true 或 round>3) / → `sprint_plan` (disagreed) |

### 4. sprint_setup

| 属性 | 值 |
|------|------|
| Agent | Generator（Claude Agent SDK，零工具，纯结构化输出） |
| Loop | Sprint |
| Reads | `sprint_contract`, `spec` |
| Writes | `sprint_contract` (加 execution_plan), `fix_loop_count=0` |
| Artifacts | `sprint_contract.json` (versioned) |
| Routes | → `session_init` (linear) |

### 5. session_init (协调器)

| 属性 | 值 |
|------|------|
| Agent | Initializer |
| Loop | Session (入口) |
| Reads | `sprint_number`, `session_number` |
| Writes | `_is_first_init`, `current_phase` |
| Artifacts | (无 — 委托) |
| Routes | → `init_parallel` (Sprint 1) / → `session_setup_entry` (后续 Sprint) |

> **协调器**：本身不写文件，通过 Send API 扇出到 5 个并行 init 节点（Sprint 1）或直接跳到 session_setup_entry（后续 Sprint）。

### 6–10. init_parallel (5 个并行节点，fan-out via Send)

| 节点 | 职责 | 写入文件 |
|------|------|---------|
| `init_progress` | 写 `claude-progress.txt` | `harness/claude-progress.txt` |
| `init_script` | 写 `init.sh` | `harness/init.sh` |
| `init_feature_list` | 写 `feature_list.json` | `harness/feature_list.json` |
| `init_git` | git init + src/ 目录 | `harness/.git/` |
| `init_loop_entry` | 写决策日志 | (无文件) |

所有 5 个节点扇入到 `session_setup_entry`。

### 11. session_setup_entry (协调器)

| 属性 | 值 |
|------|------|
| Agent | Initializer |
| Loop | Session |
| Reads | — |
| Writes | `current_phase` |
| Artifacts | (无 — 委托) |
| Routes | → 4 个并行读节点 (fan-out via Send) |

### 12–15. READ_PARALLEL (4 个并行节点，fan-out via Send)

| 节点 | 职责 | 写入 state |
|------|------|----------|
| `read_pwd` | 获取当前目录 | `session_context["pwd"]` |
| `read_progress` | 读进度文件 | `session_context["progress"]` |
| `read_feature_list` | 读 feature 列表 | `session_context["feature_list"]`, `feature_list` |
| `read_git_log` | 读 git 历史 | `session_context["git_history"]`, `messages` |

所有 4 个节点扇入到 `session_setup_exit`。

### 16. session_setup_exit

| 属性 | 值 |
|------|------|
| Agent | Initializer |
| Loop | Session |
| Reads | `session_context` (合并后) |
| Writes | `messages`, `current_phase` |
| Artifacts | 运行 `init.sh` |
| Routes | → `sanity_check` (linear) |

> **扇入点**：`session_context` 由 4 个并行节点各写一个 key，经 reducer 合并后完整可用。

### 17. sanity_check

| 属性 | 值 |
|------|------|
| Agent | Evaluator |
| Loop | Session |
| Reads | — |
| Writes | `sanity_pass`, `test_result` |
| Artifacts | (无) |
| Routes | → `pick_feature` (pass) / → `bug_triage` (fail, ≤2 次) / → `pick_feature` (cap reached) |

### 18. bug_triage

| 属性 | 值 |
|------|------|
| Agent | Evaluator |
| Loop | Session |
| Reads | `last_good_commit`, `git diff` |
| Writes | `triage_result`, `sanity_retry_count++` (only when revert fails / no last_good) |
| Artifacts | 可能 `git reset --hard last_good_commit` |
| Routes | → `sanity_check` (linear, 不重读文件) |

> **注意**：不再重读上下文文件，直接返回 `sanity_check`。
> **Retry 计数器规则**：revert 后 diff 干净（恢复成功） → **不**计 retry 配额；
> revert 后 diff 还在 / 没 last_good_commit / 工作树本来就很干净 → 计 1 次（真 bug）。

### 19. pick_feature

| 属性 | 值 |
|------|------|
| Agent | Generator |
| Loop | Feature (入口) |
| Reads | `feature_list`, `sprint_contract` |
| Writes | `current_feature_id`, `current_feature_status`, `feature_retry_count=0` |
| Artifacts | (无) |
| Routes | → `implement_feature` (有 feature) / → `evaluator_qa` (无 feature) |

### 20. implement_feature

| 属性 | 值 |
|------|------|
| Agent | Generator（Claude Agent SDK，自主工具调用） |
| Loop | Feature |
| Reads | `current_feature_id`, `feature_list`, `spec` |
| Writes | `implement_result`, `feature_retry_count++`, `session_progress_count++` |
| Artifacts | Generator agent 用 Read/Write/Edit/Bash/Glob/Grep **自己**把实现文件写进 `harness/`（不再由 Python `write_text`） |
| Routes | → `test_feature` (linear) |

> **交接点：** agent 写进 `harness/` 的文件是 `test_feature` 的测试对象。
> **执行模型：** 节点起一个 `cwd=harness/`、工具集收敛为 Generator 工具的 SDK agent，
> agent 自主迭代到产出符合 `implement_result` schema 的最终 JSON；节点取 `structured_output`
> 后照常 `validate_artifact`。安全边界由 agent seam 的 `cwd` + `allowed_tools`（经
> `permission_mode="dontAsk"` 强制：不在清单的工具直接 deny）+ PreToolUse hook
> （复用 `assert_safe_llm_write_target`）保证。**已知限制**：本节点开了 Bash，故 hook 拦不住
> shell 重定向逃逸——硬隔离留给部署期容器，本地可信运行接受残余风险（详见 `agent.py` 模块 docstring）。

### 21. test_feature

| 属性 | 值 |
|------|------|
| Agent | Evaluator |
| Loop | Feature |
| Reads | `current_feature_id` |
| Writes | `test_result` |
| Artifacts | (无) |
| Routes | → `commit_feature` (pass 或 retry≥2) / → `implement_feature` (fail, retry<2) |

### 22. commit_feature

| 属性 | 值 |
|------|------|
| Agent | Generator |
| Loop | Feature |
| Reads | `current_feature_id`, `feature_list` |
| Writes | `feature_list` (更新 passes/blocked), `current_feature_id=None` |
| Artifacts | `feature_list.json`, `claude-progress.txt`, git commit |
| Routes | → `pick_feature` (有剩余) / → `evaluator_qa` (sprint 完成) |

> **交接点：** 写入 `feature_list.json` 是 `pick_feature` 下轮循环的输入契约。
> 测试通过标 `passes=True`；retry 用尽仍失败则标 `blocked=True, passes=False` —— 代码仍 git-commit 保
> 留进度，但 `sprint_complete` 不会把 blocked 计入"完成"，`pick_feature` 在本 sprint 内不再选它。

### 23. evaluator_qa

| 属性 | 值 |
|------|------|
| Agent | Evaluator（Claude Agent SDK，**只读**工具：Read/Glob/Grep） |
| Loop | Sprint (review) |
| Reads | `feature_list`, `harness_design_draft.test_cases`（通过 testing.run_qa_eval 读）, `harness/` 源码（Evaluator agent 直接读） |
| Writes | `evaluator_grade` |
| Artifacts | `evaluator_grade.json` (versioned) |
| Routes | → `sprint_complete` (pass) / → `evaluator_bugs` (fail) |

> **评测模型：Runner + Evaluator agent 双轨**。
> - `testing.run_qa_eval` 用 `subprocess + timeout(60s)` 真跑 `harness/main.py`，对照每条 test_case 的 `expected_output_keys` 检查 stdout JSON。结果是 ground truth。
> - 如果 runner 看到 expected_to_pass=True 的用例真的失败了，**强制覆盖** Evaluator agent 的 overall_pass=False。
> - 如果 runner 跑不起来（没 main.py、没 test_cases、超时等），返回中性 `overall_pass=True + runner_results=[]`，**让 Evaluator agent 接管评分**，不会触发无限 fix 循环。
> - Evaluator agent 用只读工具（Read/Glob/Grep）真审阅 `harness/` 代码 + runner 报告，综合打 4 维软指标分（可读性、模块化、错误处理等）。**只读 = 它判但不改，与写代码的 Generator 保持独立**。
>
> **交接点：** `evaluator_grade.json` 是 `evaluator_bugs` 和 `generator_fix` 的输入契约。

### 25. evaluator_bugs

| 属性 | 值 |
|------|------|
| Agent | Evaluator |
| Loop | Fix |
| Reads | `evaluator_grade` |
| Writes | `bug_report` |
| Artifacts | `bug_report.json` (versioned) |
| Routes | → `generator_fix` (always) |

> **交接点：** `bug_report.json` 是 `generator_fix` 的输入契约。

### 26. generator_fix

| 属性 | 值 |
|------|------|
| Agent | Generator（Claude Agent SDK，自主工具调用） |
| Loop | Fix (≤2 轮) |
| Reads | `bug_report` |
| Writes | `fix_result`, `fix_loop_count++` |
| Artifacts | Generator agent 用 Read/Write/Edit/Bash/Glob/Grep **自己**把修复文件写进 `harness/` 并自跑测试（不再由 Python `write_text`） |
| Routes | → `evaluator_qa` (自测通过或 fix≥2) / → `generator_fix` (自测失败) |

> **执行模型：** 节点起一个 `cwd=harness/` 的 Generator SDK agent 自主修复+自测，产出符合
> `fix_result` schema 的最终 JSON；节点取 `structured_output` 后 `validate_artifact`。
> 另：节点仍跑确定性 `run_sanity_check`（只查 src/+main.py 在不在），并保留 `verified` 缺省回退规则。

### 27. sprint_complete

| 属性 | 值 |
|------|------|
| Agent | — (orchestrator, 无 LLM) |
| Loop | Sprint (出口) |
| Reads | `feature_list`, `evaluator_grade`, `sprint_number` |
| Writes | `sprint_result`，并重置所有 per-sprint 计数 (sprint_number++, session_number=1, negotiate_round=1, fix_loop_count=0, feature_retry_count=0, sanity_retry_count=0, sprint_contract=None, evaluator_grade=None, fix_result=None, current_feature_*=None, test_result=None, implement_result=None, triage_result=None, _is_first_init=False)。**`bug_report` 不重置** — sprint_plan 把它当作"上一轮 bug 上下文"消费 |
| Artifacts | `sprint_result.json` (versioned) |
| Routes | → END (spec_complete) / → `sprint_plan` (继续下一轮) |

---

## 路由函数规范

路由函数定义在 `graph.py`，每个条件路由对应一个 `_<source>_router` 函数：

```python
def _<source>_router(state: CodingState) -> str:
    """Route: <source> → <target_a> | <target_b>.

    Condition:
        → target_a  when <condition>
        → target_b  when <condition>
    """
    ...
```

---

## 新增 Node 时的检查清单

- [ ] 按上方模板写 docstring（Agent / Loop / Reads / Writes / Artifacts / Routes）
- [ ] 只做一件事，不混入其他职责
- [ ] 交接文件写入 `harness/` 目录
- [ ] 在 `NODES.md` 中注册
- [ ] 在 `graph.py` 中添加 node 和 edge
- [ ] 添加 mock response（测试用）
- [ ] 跑 `pytest` 确认不破坏现有流
