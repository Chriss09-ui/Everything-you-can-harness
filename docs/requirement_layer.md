# 需求层 (Requirement Layer) — AI 上手指南

> 给接手"需求层"开发的 AI 的第一份必读。读完这一份，你就能加 node、改路由、改 artifact，而不需要通读全部代码。
>
> 改完代码记得回到 [CLAUDE.md](../CLAUDE.md#改动同步原则强制) 查改动同步清单。

---

## 1. 这一层在干什么

需求层的任务：**把用户的一句话需求，转化为一份经过对抗式辩论、并被用户确认过的"需求契约"**。

它不直接出代码、不出架构稿，只出契约。一份合格的需求契约 = 架构层能不再追问、直接动手设计的输入。

设计动机：避免下游的架构层和研发层基于歧义需求做无效工作。

---

## 2. 流水线

```
spec_expansion → spec_challenge → brief_debate → sinan_debrief → brief_compile
   (拓谱)         (诘问)            (拓谱+诘问辩论)   (用户回答)     (契约定稿)
                                                                         │
                                                                         ▼
                                                              [进入架构层]
```

五个 node，全部 **linear**（无条件分支）。代码定义见 [src/sinan/graph.py](../src/sinan/graph.py)。

---

## 3. 节点清单（与 [NODES.md](../src/sinan/nodes/NODES.md#需求层-nodes-5) 同步）

| # | Node | Agent | 一句话职责 |
|---|---|---|---|
| 1 | `spec_expansion` | 拓谱 (Tuopu) | 把用户输入扩展成多维度需求包，不评判 |
| 2 | `spec_challenge` | 诘问 (Jiewen) | 挑战需求包的漏洞和歧义，不修改原始需求 |
| 3 | `brief_debate` | 拓谱 + 诘问 | 两方对话，沉淀已对齐的点 和 未解决的问题 |
| 4 | `sinan_debrief` | 司南 (用户交互) | 把未解决的问题抛给用户，收集 `user_brief_answers` |
| 5 | `brief_compile` | 契约 (Qiyue) | 综合需求包+辩论+用户答案，定稿契约 |

每个 node 的 Reads / Writes / Artifacts / Routes 全表在 [src/sinan/nodes/NODES.md](../src/sinan/nodes/NODES.md#需求层-nodes-5)。

---

## 4. 输入 / 输出契约

### 入口
- `state["user_raw_input"]` — 一段自然语言（由 `intake_node` 在 graph 启动前注入，见 [cli.py](../src/sinan/cli.py) 的 `intake_node` 调用）

### 出口
- `runs/<run_id>/user_brief_form.json` — 需求契约（**架构层的输入**）。该文件是自包含契约：既包含用户确认/拒绝/优先级等签字信息，也保留 `requirement_pack` 的核心需求字段（目标、范围、成功标准、约束等），下游不需要回读 `requirement_pack.json` 才能理解需求。

> 一旦落盘，架构层可以独立启动：`python -m sinan.cli --from-brief <run_id>` 跳过需求层，从这个文件 hydrate。

### 中间产物（按顺序生成）

| 文件 | 写入者 | 用途 |
|---|---|---|
| `requirement_pack.json` | `spec_expansion` | 结构化需求包 |
| `spec_review.json` | `spec_challenge` | 诘问报告，含未解决风险 |
| `brief_debate.json` | `brief_debate` | 辩论结果，含 agreements / unresolved |
| `user_brief_form.json` | `brief_compile` | **契约文件** — 出口；包含确认信息 + 需求包核心字段 |

所有文件落到 `runs/<run_id>/`。

---

## 5. State 字段（需求层使用部分）

定义见 [src/sinan/state.py](../src/sinan/state.py)。`HarnessBuilderState` 跟架构层共用，下表只列需求层会读写的字段：

| 字段 | 类型 | 谁写 | 谁读 |
|---|---|---|---|
| `user_raw_input` | str | `intake_node` | `spec_expansion` |
| `requirement_pack` | dict | `spec_expansion` | `spec_challenge`, `brief_debate`, `brief_compile` |
| `spec_review` | dict | `spec_challenge` | `brief_debate` |
| `brief_debate` | dict | `brief_debate` | `sinan_debrief`, `brief_compile` |
| `user_brief_answers` | list[dict] | `sinan_debrief` | `brief_compile` |
| `user_brief_form` | dict | `brief_compile` | 架构层 `framework_design`；自包含需求契约 |
| `current_phase` | str | 每个 node | 审计 / 日志 |
| `risk_register` | list[dict] | `spec_challenge` | 跨层风险跟踪 |
| `artifact_versions` | dict | 每个写产物的 node | 版本注册表 |

---

## 6. 关键文件

| 文件 | 用途 |
|---|---|
| [src/sinan/graph.py](../src/sinan/graph.py) | 五个 node 的注册和 linear edge |
| [src/sinan/state.py](../src/sinan/state.py) | `HarnessBuilderState` schema + `make_initial_state()` |
| [src/sinan/nodes/intake.py](../src/sinan/nodes/intake.py) | 不在 graph 中，由 cli.py 调用，把 raw input 塞进 state |
| [src/sinan/nodes/spec_expansion.py](../src/sinan/nodes/spec_expansion.py) | 拓谱 |
| [src/sinan/nodes/spec_challenge.py](../src/sinan/nodes/spec_challenge.py) | 诘问 |
| [src/sinan/nodes/brief_debate.py](../src/sinan/nodes/brief_debate.py) | 辩论 |
| [src/sinan/nodes/sinan_debrief.py](../src/sinan/nodes/sinan_debrief.py) | 用户交互（同步 `input()`） |
| [src/sinan/nodes/brief_compile.py](../src/sinan/nodes/brief_compile.py) | 契约定稿 |
| [src/sinan/prompts.py](../src/sinan/prompts.py) | 角色 prompts（拓谱/诘问/契约的 system prompt） |
| [src/sinan/mock_responses.py](../src/sinan/mock_responses.py) | 测试用确定性 mock 输出 |
| [src/sinan/artifacts.py](../src/sinan/artifacts.py) | `runs/<id>/` 目录、日志、版本化写入 |

---

## 7. 怎么开发

### 加一个新 node

1. 在 `src/sinan/nodes/` 下新建 `xxx.py`，文件头按统一模板写 docstring：

   ```python
   """xxx — <一句话职责>.

   Agent: <角色名>
   Layer: 需求层

   Reads:
       state["field"]  — 说明

   Writes:
       state["field"]  — 说明

   Artifacts:
       <file>.json  — 说明

   Routes:
       → next_node  when <condition>
   """
   ```

2. 实现函数签名：`def xxx_node(state: HarnessBuilderState) -> dict:`，**返回完整 state dict**（LangGraph 会合并）。
3. 在 `src/sinan/nodes/__init__.py` 中 `from . import xxx`。
4. 在 `src/sinan/graph.py` 中：`g.add_node(...)` + `g.add_edge(...)`。
5. 在 [NODES.md](../src/sinan/nodes/NODES.md) 中加一行表格记录。
6. 在本指南的 "节点清单" 段加一行。
7. 在 `mock_responses.py` 中加 mock（如果不加，测试会调真实 LLM）。
8. 跑 `pytest -q` 确认没断。

### 改一个 node 的行为

1. 改 `xxx.py` 实现。
2. 同步改文件头 docstring 的 Reads / Writes / Artifacts。
3. 同步改 [NODES.md](../src/sinan/nodes/NODES.md) 对应行。
4. 如果改了 artifact 文件名或字段，同步改本指南"中间产物"表。

### 改一条路由

1. 改 `graph.py` 里的 router 函数。
2. 同步改 [NODES.md](../src/sinan/nodes/NODES.md) 的 Routes 列。
3. 同步改本指南"流水线" ASCII 图。

### 加一个 artifact

1. 在 node 里 `write_artifact_versioned(...)` 落盘（见 `artifacts.py`）。
2. 在 docstring 的 Artifacts 段加一行。
3. 在 [NODES.md](../src/sinan/nodes/NODES.md) 对应行的 Artifacts 列加。
4. 在本指南"中间产物"表加一行。
5. 如果是层间交接物，更新 README 的 "Run Artifacts" 段。

---

## 8. 容易踩的坑

- **不要在 node 里写 `if/else` 路由**：所有条件分支放 `graph.py` 的 router 函数。
- **不要让一个 node 做两件事**：拆开。比如"扩展+评判"应该是 `spec_expansion` + `spec_challenge` 两个 node。
- **不要修改用户原始输入**：`user_raw_input` 是只读的，要新结构就写新字段。
- **`sinan_debrief` 是同步 `input()`，不是 LangGraph `interrupt()`**：以后要接 web UI 必须重写这个 node。
- **测试用 mock**：`register_mock_responses()` 必须在跑 graph 前调用，否则测试会去打真实 LLM。
- **改完代码记得回 [CLAUDE.md 改动同步原则](../CLAUDE.md#改动同步原则强制) 核对清单。**

---

## 9. 怎么调试

- 看 `runs/<run_id>/decision_log.md` — 每个 node 的决策摘要
- 看 `runs/<run_id>/progress_log.md` — 时序日志
- 看 `runs/<run_id>/run_state.yaml` — 当前 state 快照
- 跑 `pytest tests/test_e2e_mock.py -v` — mock 模式下走完整流水
