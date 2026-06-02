# 研发层 (Coding Layer) — AI 上手指南

> 给接手"研发层"开发的 AI 的第一份必读。研发层是三层里**最复杂**的一层（26 个 node、11 个路由函数、4 重嵌套循环、并行 fan-out/fan-in），读完这一份再去查代码就不会迷路。
>
> 改完代码记得回到 [CLAUDE.md](../CLAUDE.md#改动同步原则强制) 查改动同步清单。

---

## 1. 这一层在干什么

研发层的任务：**把架构层定稿的设计稿 → 在嵌套循环中转化为可运行的代码仓**。

它直接出代码、出 git history、出可执行的 harness。一份合格的产出 = 一个能跑、能测试通过、按 sprint 完成度评分的代码仓库。

设计动机：模拟真实工程师团队的研发节奏——分 sprint、有协商、每轮 session 重置上下文（avoiding context drift）、按 feature 拆分、自动评审 + 自修复。

---

## 2. 四重嵌套循环

```
┌──────────────────────────────────────────────────────────────────┐
│ Sprint Loop (≤10 轮)                                              │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Sprint Negotiate (≤3 轮)                                    │ │
│  │  Generator 与 Evaluator 就 sprint 范围讨价还价               │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Session Loop                                                │ │
│  │ 每个 session 重置上下文，从磁盘 artifact 重新 hydrate         │ │
│  │                                                            │ │
│  │  ┌──────────────────────────────────────────────────────┐ │ │
│  │  │ Feature Loop                                          │ │ │
│  │  │ 按优先级 pick → implement → test → commit             │ │ │
│  │  │                                                       │ │ │
│  │  │  ┌────────────────────────────────────────────────┐  │ │ │
│  │  │  │ Fix Loop (≤2 轮)                               │  │ │ │
│  │  │  │ QA 不过 → 生成 bug report → 自修复 + 自测       │  │ │ │
│  │  │  └────────────────────────────────────────────────┘  │ │ │
│  │  └──────────────────────────────────────────────────────┘ │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

---

## 3. 流水线（高层视图）

```
[架构层出口: harness_design_draft.json]
        │
        ▼
   planner ──→ sprint_plan ──→ sprint_negotiate
                                       │
                              (agreed/round>3) ↓ ↑ (disagreed)
                                       │ └─────┘
                                       ▼
                              sprint_setup ──→ session_init
                                                    │
                            ┌──── (Sprint 1) ───────┴───────── (后续 Sprint) ────┐
                            ▼                                                    │
                  [5 并行: init_progress / init_script /                          │
                   init_feature_list / init_git / init_loop_entry]               │
                            │                                                    │
                            └────────────────►session_setup_entry◄───────────────┘
                                                    │
                                       [4 并行: read_pwd / read_progress /
                                                read_feature_list / read_git_log]
                                                    │
                                                    ▼
                                          session_setup_exit ──→ sanity_check
                                                                      │
                                                  (pass) ↓     ↑ (fail, ≤2 次)
                                                          │     └──── bug_triage ───┘
                                                          ▼
                                                    pick_feature
                                          ┌──────────────┴──────────────┐
                              (有 feature) │                             │ (无 feature)
                                          ▼                             ▼
                                  implement_feature             evaluator_qa
                                          │                             │
                                          ▼                             ▼
                                    test_feature                  evaluator_qa
                                  ┌──────┴───────┐              ┌───────┴────────┐
                          (pass /  ↓             ↑ (fail, retry<2)        ↓        ↓
                           retry≥2)│             └──implement_feature   (pass)   (fail)
                                  ▼                                       ↓        ↓
                            commit_feature                          sprint_complete  evaluator_bugs
                          ┌──────┴───────┐                                ↓             │
                  (剩余)  ↓               ↓ (sprint 完成)        ┌────────┴────────┐    ▼
                   pick_feature      evaluator_qa         (END)              ↑  generator_fix
                                                              (spec_complete)    │     │
                                                                          (sprint≤10) │  ┌────┴────┐
                                                                       sprint_plan ←──┘  ↓         ↓
                                                                                  (verified) (fail, retry<2)
                                                                                  evaluator_qa  generator_fix
```

代码定义见 [src/sinan/coding/graph.py](../src/sinan/coding/graph.py)（26 nodes + 11 个路由函数，其中 2 个 fan-out 通过 `Send` API）。

---

## 4. 节点清单（与 [NODES.md](../src/sinan/coding/NODES.md) 同步）

完整 26 个 node 的 Reads / Writes / Artifacts / Routes 在 [src/sinan/coding/NODES.md](../src/sinan/coding/NODES.md)。下表只列**角色 + 一句话职责**，便于速查：

| # | Node | Agent | Loop | 一句话 |
|---|---|---|---|---|
| 1 | `planner` | Planner | Sprint (入口) | 把 harness_design 拆成 `spec` + `feature_list` |
| 2 | `sprint_plan` | Generator | Sprint | 出 sprint 目标提案 |
| 3 | `sprint_negotiate` | Evaluator | Sprint | 协商 sprint 范围（≤3 轮） |
| 4 | `sprint_setup` | Generator | Sprint | 加 execution_plan + 重置 fix_loop_count |
| 5 | `session_init` | Initializer | Session (入口) | 协调器：扇出到 init 或直进 setup |
| 6 | `init_progress` | Initializer | Session (并行) | 写 `claude-progress.txt` |
| 7 | `init_script` | Initializer | Session (并行) | 写 `init.sh` |
| 8 | `init_feature_list` | Initializer | Session (并行) | 写 `feature_list.json` |
| 9 | `init_git` | Initializer | Session (并行) | `git init` + `src/` |
| 10 | `init_loop_entry` | Initializer | Session (并行) | 写决策日志 |
| 11 | `session_setup_entry` | Initializer | Session | 协调器：扇出到 4 并行读 |
| 12 | `read_pwd` | Initializer | Session (并行) | 读 cwd → `session_context["pwd"]` |
| 13 | `read_progress` | Initializer | Session (并行) | 读 progress 文件 |
| 14 | `read_feature_list` | Initializer | Session (并行) | 读 feature 列表 |
| 15 | `read_git_log` | Initializer | Session (并行) | 读 git 历史 |
| 16 | `session_setup_exit` | Initializer | Session | 扇入合并 context，跑 init.sh |
| 17 | `sanity_check` | Evaluator | Session | 跑健康检查 |
| 18 | `bug_triage` | Evaluator | Session | sanity fail 时分诊 / 可能 `git revert` |
| 19 | `pick_feature` | Generator | Feature (入口) | 按优先级选 feature |
| 20 | `implement_feature` | Generator | Feature | 写实现文件 |
| 21 | `test_feature` | Evaluator | Feature | 跑 feature 级测试 |
| 22 | `commit_feature` | Generator | Feature | 更新 feature_list + git commit |
| 23 | `evaluator_qa` | Evaluator | Sprint review | Runner (`main.py` 真跑)+ LLM 综合评分 → `evaluator_grade.json` |
| 24 | `evaluator_bugs` | Evaluator | Fix | 出 `bug_report.json` |
| 25 | `generator_fix` | Generator | Fix (≤2 轮) | 修代码 + 自测 |
| 26 | `sprint_complete` | — (orchestrator) | Sprint (出口) | 出 `sprint_result.json`，判断 END 或下一轮 |

---

## 5. 输入 / 输出契约

### 入口（两种来源，按优先级）
1. `state["harness_design_draft"]` — 架构层产出的设计稿，由 cli.py 在完整流程中直接传入
2. `runs/<run_id>/harness_design_draft.json` — 当 state 为空时 `planner_node` 自动从磁盘读取

第 2 种来源支持 `python -m sinan.cli --from-design <run_id>` 跳过设计层直接进研发层（详见 README）。
研发层因此可以**独立从文件启动**，不依赖前置内存 state。

### 出口
- `runs/<run_id>/harness/` 下的**完整代码仓**（含 git history、src/、测试）
- `runs/<run_id>/sprint_result.json` — 最终 sprint 评分摘要

> **统一 run_id**：设计层和研发层共享同一个 `run_id`。设计层产物落在 `runs/<run_id>/`，
> 研发层代码仓落在 `runs/<run_id>/harness/`。所有跨层文件物理上同目录可达。

### Artifact 全清单（按 sprint 生命周期）

研发层最关键的设计：**Agent 之间不通过 state 传递信息，只通过下表里的磁盘文件**。

| 文件 | 路径 | 写入者 | 消费者 |
|---|---|---|---|
| `claude-progress.txt` | `harness/` | `init_progress`, `commit_feature` | `read_progress`（每个 session 开头读） |
| `init.sh` | `harness/` | `init_script` | `session_setup_exit`（运行它） |
| `feature_list.json` | `harness/` | `init_feature_list`, `commit_feature` | `read_feature_list`, `pick_feature`, `evaluator_qa`, `evaluator_qa`, `_commit_feature_router` |
| `harness/.git/` | `harness/` | `init_git`, `commit_feature`, `bug_triage` | `read_git_log`, `_sprint_complete_router` |
| `sprint_contract.json` | `runs/<id>/` (versioned) | `sprint_plan`, `sprint_negotiate`, `sprint_setup` | 下一轮 sprint 协商 |
| `evaluator_grade.json` | `runs/<id>/` (versioned) | `evaluator_qa` | `evaluator_bugs`, `generator_fix` |
| `bug_report.json` | `runs/<id>/` (versioned) | `evaluator_bugs` | `generator_fix` |
| `sprint_result.json` | `runs/<id>/` (versioned) | `sprint_complete` | 出口 |
| `spec.json` | `runs/<id>/` | `planner` | sprint 协商时参考 |

**"versioned"** 指 artifact 每次写入都生成新版本号（`sprint_contract_v1.json`, `_v2.json`, ...），可回溯历史。

> **为什么不用 state 传？** LangGraph 的 state 在节点内合并，但**两个 session 之间 state 不持久**。文件是跨 session 重新 hydrate 的唯一手段。这是研发层的核心设计原则。

---

## 6. 路由规范

11 个路由函数（9 个 routing decision + 2 个 fan-out，后者通过 `Send` API），全部在 [src/sinan/coding/graph.py](../src/sinan/coding/graph.py) 底部：

| Router | 入口 node | 决策依据 | 出口 |
|---|---|---|---|
| `_session_init_fanout` | `session_init` | `_is_first_init` | 5 并行 init / 跳到 setup |
| `_session_setup_fanout` | `session_setup_entry` | 无条件 | 4 并行 read |
| `_sprint_negotiate_router` | `sprint_negotiate` | `sprint_contract.agreed` / `negotiate_round > 3` | `sprint_setup` / `sprint_plan` |
| `_sanity_check_router` | `sanity_check` | `sanity_pass` / `sanity_retry_count ≥ 2` | `pick_feature` / `bug_triage` |
| `_pick_feature_router` | `pick_feature` | 有无 `current_feature_id` | `implement_feature` / `evaluator_qa` |
| `_test_feature_router` | `test_feature` | `test_result.passed` / `feature_retry_count ≥ 2` | `commit_feature` / `implement_feature` |
| `_commit_feature_router` | `commit_feature` | sprint 内还有未完成 feature? | `pick_feature` / `evaluator_qa` |
| `_evaluator_qa_router` | `evaluator_qa` | `evaluator_grade.overall_pass` | `sprint_complete` / `evaluator_bugs` |
| `_evaluator_bugs_router` | `evaluator_bugs` | 总是 | `generator_fix` |
| `_generator_fix_router` | `generator_fix` | `fix_result.verified` / `fix_loop_count ≥ 2` | `evaluator_qa` / `generator_fix` |
| `_sprint_complete_router` | `sprint_complete` | `spec_complete` / `sprint_number > 10` | `END` / `sprint_plan` / `RuntimeError` |

### 上限值（动这些会改变循环语义，谨慎）

| 上限 | 值 | 在哪 |
|---|---|---|
| Sprint 最大轮数 | **10** | `_sprint_complete_router` |
| Negotiate 最大轮数 | **3** | `_sprint_negotiate_router` |
| Sanity retry 上限 | **2** | `_sanity_check_router` |
| Feature retry 上限 | **2** | `_test_feature_router` |
| Fix loop 上限 | **2** | `_generator_fix_router` |

---

## 7. State 字段

定义见 [src/sinan/coding/state.py](../src/sinan/coding/state.py)。研发层不用 `HarnessBuilderState`，而是用独立的 `CodingState`。下面列关键字段：

| 字段 | 类型 | 谁写 | 谁读 |
|---|---|---|---|
| `harness_design_draft` | dict | cli.py（从设计层传入） | `planner` |
| `spec` | dict | `planner` | sprint planning |
| `feature_list` | dict | `init_feature_list`, `commit_feature` (内存视图) | `pick_feature`, `read_feature_list` |
| `sprint_contract` | dict | `sprint_plan`, `sprint_negotiate`, `sprint_setup` | sprint loop |
| `sprint_number` | int | `_sprint_complete_router` (++) | 各 router |
| `session_number` | int | `_sprint_complete_router` (reset) | 协调器 |
| `negotiate_round` | int | `sprint_negotiate` (++) | `_sprint_negotiate_router` |
| `current_feature_id` | str/None | `pick_feature`, `commit_feature` | feature loop |
| `test_result` | dict | `test_feature` | `_test_feature_router` |
| `evaluator_grade` | dict | `evaluator_qa` | `_evaluator_qa_router`, `evaluator_bugs` |
| `bug_report` | dict | `evaluator_bugs` | `generator_fix` |
| `fix_result` | dict | `generator_fix` | `_generator_fix_router` |
| `fix_loop_count` | int | `evaluator_bugs`, `generator_fix` | `_generator_fix_router` |
| `feature_retry_count` | int | `implement_feature` | `_test_feature_router` |
| `sanity_retry_count` | int | `bug_triage` | `_sanity_check_router` |
| `session_context` | `Annotated[dict, _merge_dicts]` | 4 个并行 read 节点 | `session_setup_exit` |
| `_is_first_init` | bool | cli.py / session_init | `_session_init_fanout` |

`session_context` 是**关键**：它的 `Annotated[..., _merge_dicts]` reducer 让 4 个并行 read 节点的写入自动合并，是 LangGraph 处理并行节点状态合并的标准模式。

---

## 8. 关键文件

| 文件 | 用途 |
|---|---|
| [src/sinan/coding/graph.py](../src/sinan/coding/graph.py) | 26 个 node 注册 + 11 路由函数（9 router + 2 fan-out） |
| [src/sinan/coding/state.py](../src/sinan/coding/state.py) | `CodingState` + `make_coding_state()` |
| [src/sinan/coding/nodes/](../src/sinan/coding/nodes/) | 26 个 node 模块 |
| [src/sinan/coding/prompts.py](../src/sinan/coding/prompts.py) | Planner / Generator / Evaluator / Initializer / Negotiator prompts |
| [src/sinan/coding/git.py](../src/sinan/coding/git.py) | `git init / add / commit / log / revert` 封装 |
| [src/sinan/coding/testing.py](../src/sinan/coding/testing.py) | **Runner**：subprocess + 60s timeout 跑 `harness/main.py`，对照 design_draft.test_cases 评分 |
| [src/sinan/coding/mock_responses.py](../src/sinan/coding/mock_responses.py) | mock 输出 |
| [src/sinan/coding/parse_json.py](../src/sinan/coding/parse_json.py) | 容错 JSON 解析 |

---

## 9. 怎么开发

### 加一个新 node

1. 在 `src/sinan/coding/nodes/` 下新建 `xxx.py`，文件头按统一模板写 docstring：

   ```python
   """xxx — <一句话职责>.

   Agent: <Planner | Generator | Evaluator | Initializer | Negotiator>
   Loop:  <Sprint | Session | Feature | Fix>

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

2. 实现 `def xxx_node(state: CodingState) -> dict:`，返回完整 state dict。
3. 在 `src/sinan/coding/nodes/__init__.py` 中 `from . import xxx`。
4. 在 `src/sinan/coding/graph.py` 中：`g.add_node(...)` + edges / conditional edges。
5. 在 [NODES.md](../src/sinan/coding/NODES.md) 中加表格行（注意编号）。
6. 在本指南"节点清单"和"流水线"ASCII 图中加。
7. 在 `mock_responses.py` 中加 mock。
8. `pytest tests/test_coding_e2e_mock.py -v` 确认通过。

### 加一条路由

1. 在 `graph.py` 底部加新的 `_xxx_router(state) -> str` 函数。
2. 用 `g.add_conditional_edges(...)` 接上。
3. 同步改 [NODES.md](../src/sinan/coding/NODES.md) 对应 node 的 Routes 列。
4. 同步改本指南"路由规范"段和 ASCII 图。

### 加并行节点（fan-out）

研发层有两组并行节点（init 5 个 + read 4 个）。模式：

1. 在协调器里用 `Send("target_node", state)` 列表扇出。
2. 所有 target node 用 `g.add_edge(target, "fan_in_node")` 扇入到下一个聚合点。
3. 如果并行节点写同一个 state 字段，**必须**用 `Annotated[..., reducer]`（见 `session_context`），否则会报 InvalidUpdateError。
4. 同步改 [NODES.md](../src/sinan/coding/NODES.md)、本指南、ASCII 图。

### 加一个 artifact

1. 决定路径：跨 session 共享的放 `harness/`；按 sprint 版本化的放 `runs/<id>/`（用 `write_artifact_versioned`）。
2. 在 node docstring 的 Writes 段加。
3. 在 [NODES.md](../src/sinan/coding/NODES.md) 对应行加。
4. 在本指南"Artifact 全清单"表加（写入者、消费者都填）。
5. 如果是层间交接物，更新 README 和 CLAUDE.md。

### 改一个循环的上限

1. 改 `graph.py` 对应 router 的常量（如 `>= 2` 改成 `>= 3`）。
2. 同步改本指南"上限值"表。
3. 跑 e2e mock 测试看会不会卡死。

---

## 10. 容易踩的坑

- **`harness/` 是 agent 真正的工作目录**，跟 `runs/<id>/` 下其他 artifact 平级，但语义不同。`harness/` 是产物代码；`runs/<id>/` 下其他文件是过程档案。
- **并行节点必须用 reducer 合并 state**：见 `session_context: Annotated[dict, _merge_dicts]`。如果新加并行节点写同一字段没加 reducer，LangGraph 会抛 `InvalidUpdateError`。
- **Session 重置上下文 = 不要从 state 里读跨 session 的数据**。每个 session 开头通过 `read_*` 节点从磁盘 hydrate。state 字段只在单次 graph 调用内可靠。
- **Sprint 上限是 RuntimeError，不是优雅退出**：第 10 个 sprint 完成后会直接抛错。要改用 graceful exit 必须改 router + cli.py 的 try/except。
  （注：架构层的 `arch_reject_count` 早期也是同款 RuntimeError 上限，现已改为无上限 + `abort` 显式中止——见 [architecture_layer.md](architecture_layer.md#-_approval_outcome_router-graphpy)。）
- **`bug_triage` 不重读上下文文件**，直接回 `sanity_check`。原因是 sanity fail 通常是代码问题，不是上下文问题。
- **mock 模式必须 `register_coding_mock_responses()` 在调 graph 前**。`cli.py` 已经调了，但你写新测试时容易忘。
- **测试用产物会污染 `runs/`**。`runs/` 已被 `.gitignore` 屏蔽，但本地磁盘会堆积，自己定期 `rm -rf runs/test_*`。
- **改完代码记得回 [CLAUDE.md 改动同步原则](../CLAUDE.md#改动同步原则强制) 核对清单。**

---

## 11. 怎么调试

- 看 `runs/<run_id>/decision_log.md` — sprint 协商、QA 评分、reject 原因
- 看 `runs/<run_id>/harness/claude-progress.txt` — 当前进度
- 看 `runs/<run_id>/harness/feature_list.json` — 哪些 feature 已完成 / 失败
- `cd runs/<run_id>/harness && git log --oneline` — feature commit 序列
- 看 versioned 文件如 `sprint_contract_v1.json`, `_v2.json` — 协商演进
- 跑 `pytest tests/test_coding_e2e_mock.py -v` — mock 模式下走完整研发流水
- 跑 `pytest tests/test_coding_graph_smoke.py -v` — 仅验证 graph 结构
