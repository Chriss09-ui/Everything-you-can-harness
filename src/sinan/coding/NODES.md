# Coding Layer — Node Contract Reference

> 本文档是研发层开发规范。每个 node 模块遵循统一的 **Agent Handoff Contract**（代理交接契约），
> 明确"谁写什么、谁读什么"，使模型能快速上手而无需细读实现代码。

---

## 交接协议核心原则

### 原则 1：磁盘文件是 Agent 间的唯一交接协议

Agent 之间**不通过 state 传递信息**。所有跨 Agent 的信息共享通过文件进行：

| 阶段 | 写入文件（交出） | 读取文件（接收） |
|------|-----------------|-----------------|
| session_init (Sprint 1) | `claude-progress.txt`, `init.sh`, `feature_list.json`, git init | — |
| session_setup (每轮) | — | `claude-progress.txt`, `feature_list.json`, `git log`, pwd |
| commit_feature | `feature_list.json`, `claude-progress.txt`, git commit | — |
| sprint_negotiate | `sprint_contract.json` | — |
| evaluator_qa | `evaluator_grade.json` | — |
| evaluator_bugs | `bug_report.json` | — |
| generator_fix | 修复的文件 | — |
| implement_feature | 实现文件 | — |
| sprint_complete | `sprint_result.json` | — |

> **为什么不用 state？** LangGraph 的 state 在节点间合并，但两个 Session 之间 state 不持久。
> 文件是跨 Session 恢复上下文的唯一途径。

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

## 27 Node 合约

### 1. planner

| 属性 | 值 |
|------|------|
| Agent | Planner |
| Loop | Sprint (入口) |
| Reads | `harness_design_draft` (state) |
| Writes | `spec`, `feature_list`, `current_phase` |
| Artifacts | `spec.json` |
| Routes | → `sprint_plan` (linear) |

### 2. sprint_plan

| 属性 | 值 |
|------|------|
| Agent | Generator |
| Loop | Sprint |
| Reads | `feature_list`, `bug_report` |
| Writes | `sprint_contract`, `current_phase` |
| Artifacts | `sprint_contract.json` (versioned) |
| Routes | → `sprint_negotiate` (linear) |

### 3. sprint_negotiate

| 属性 | 值 |
|------|------|
| Agent | Evaluator |
| Loop | Sprint (协商 ≤3 轮) |
| Reads | `sprint_contract`, `negotiate_round` |
| Writes | `sprint_contract`, `negotiate_round` |
| Artifacts | `sprint_contract.json` (versioned) |
| Routes | → `sprint_setup` (agreed=true 或 round>3) / → `sprint_plan` (disagreed) |

### 4. sprint_setup

| 属性 | 值 |
|------|------|
| Agent | Generator |
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
| Writes | `triage_result`, `sanity_retry_count++` |
| Artifacts | 可能 `git revert` |
| Routes | → `sanity_check` (linear, 不重读文件) |

> **注意**：不再重读上下文文件，直接返回 `sanity_check`。

### 19. pick_feature

| 属性 | 值 |
|------|------|
| Agent | Generator |
| Loop | Feature (入口) |
| Reads | `feature_list`, `sprint_contract` |
| Writes | `current_feature_id`, `current_feature_status`, `feature_retry_count=0` |
| Artifacts | (无) |
| Routes | → `implement_feature` (有 feature) / → `generator_review` (无 feature) |

### 20. implement_feature

| 属性 | 值 |
|------|------|
| Agent | Generator |
| Loop | Feature |
| Reads | `current_feature_id`, `feature_list`, `spec` |
| Writes | `implement_result`, `feature_retry_count++`, `session_progress_count++` |
| Artifacts | 实现文件写入 `harness/` |
| Routes | → `test_feature` (linear) |

> **交接点：** 产出的文件是 `test_feature` 的测试对象。

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
| Writes | `feature_list` (更新 passes=true), `current_feature_id=None` |
| Artifacts | `feature_list.json`, `claude-progress.txt`, git commit |
| Routes | → `pick_feature` (有剩余) / → `generator_review` (sprint 完成) |

> **交接点：** 写入 `feature_list.json` 是 `pick_feature` 下轮循环的输入契约。

### 23. generator_review

| 属性 | 值 |
|------|------|
| Agent | Generator |
| Loop | Sprint (review) |
| Reads | `feature_list`, `sprint_contract` |
| Writes | `generator_self_eval` |
| Artifacts | (无) |
| Routes | → `evaluator_qa` (linear) |

### 24. evaluator_qa

| 属性 | 值 |
|------|------|
| Agent | Evaluator |
| Loop | Sprint (review) |
| Reads | `feature_list` |
| Writes | `evaluator_grade` |
| Artifacts | `evaluator_grade.json` (versioned) |
| Routes | → `sprint_complete` (pass) / → `evaluator_bugs` (fail) |

> **交接点：** `evaluator_grade.json` 是 `evaluator_bugs` 和 `generator_fix` 的输入契约。

### 25. evaluator_bugs

| 属性 | 值 |
|------|------|
| Agent | Evaluator |
| Loop | Fix |
| Reads | `evaluator_grade` |
| Writes | `bug_report`, `fix_loop_count++` |
| Artifacts | `bug_report.json` (versioned) |
| Routes | → `generator_fix` (always) |

> **交接点：** `bug_report.json` 是 `generator_fix` 的输入契约。

### 26. generator_fix

| 属性 | 值 |
|------|------|
| Agent | Generator |
| Loop | Fix (≤2 轮) |
| Reads | `bug_report` |
| Writes | `fix_result`, `fix_loop_count++` |
| Artifacts | 修复文件写入 `harness/` |
| Routes | → `evaluator_qa` (自测通过或 fix≥2) / → `generator_fix` (自测失败) |

### 27. sprint_complete

| 属性 | 值 |
|------|------|
| Agent | — (orchestrator, 无 LLM) |
| Loop | Sprint (出口) |
| Reads | `feature_list`, `evaluator_grade` |
| Writes | `sprint_result` |
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
