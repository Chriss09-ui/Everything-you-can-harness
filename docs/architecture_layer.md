# 架构层 (Architecture Layer) — AI 上手指南

> 给接手"架构层"开发的 AI 的第一份必读。读完这一份，你就能加 node、改路由、改 artifact，而不需要通读全部代码。
>
> 改完代码记得回到 [CLAUDE.md](../CLAUDE.md#改动同步原则强制) 查改动同步清单。

---

## 1. 这一层在干什么

架构层的任务：**把需求层定稿的需求契约 → 转化为一份经过多轮辩论、子代理评审、风险审查、（必要时）人工审批的架构设计稿**。

它不直接出代码，只出设计稿。一份合格的设计稿 = 研发层能直接拆 sprint、写代码的输入。

设计动机：模拟"四步辩论 + 红队挑战 + 风险分级 HITL"的真实架构评审过程，避免下游基于未经审视的方案做无效实现。

---

## 2. 流水线

```
[需求层出口]
       │
       ▼
framework_design ─→ subagent_review ─→ framework_adjust ─→ zonggong_integrate
   (总工初稿)        (子代理评审)          (总工调整)            (总工综合)
                                                                    │
                                                                    ▼
                                                          architecture_challenge
                                                              (逆审挑战)
                                                                    │
                                                                    ▼
                                                              approval_gate
                                                              (守门评级)
                                                                    │
                                                                    ▼
                                                                final_spec
                                                          (产出 md + json 待审稿)
                                                                    │
                                                                    ▼
                                                              sinan_approval
                                                       (司南带着用户过一遍 md)
                                                                    │
                                              ┌─────────────────────┴─────────────────────┐
                                              │                                           │
                                           approve                                reject / request_changes
                                              │                                           │
                                              ▼                                           ▼
                                             END                                       arch_revise
                                                                                          │
                                                                                          ▼
                                                                                   framework_design
                                                                                  (重走四步辩论)
```

九个 node + 一个条件路由器。代码定义见 [src/sinan/graph.py](../src/sinan/graph.py)。

> **关键设计**：`final_spec` 在 `sinan_approval` **之前**运行——先把完整设计稿（`harness_design_final.md` 给人看、`harness_design_draft.json` 给研发层 AI 看）落盘，再让司南带着用户过一遍。
> 每次 reject → `arch_revise → framework_design` 重走辩论 → 重新进 `final_spec` 重生成 md，再让用户审。

---

## 3. 节点清单（与 [NODES.md](../src/sinan/nodes/NODES.md#架构层-nodes-9) 同步）

| # | Node | Agent | 一句话职责 |
|---|---|---|---|
| 1 | `framework_design` | 总工框架设计师 | 出架构初稿（四步辩论 Step 1） |
| 2 | `subagent_review` | Memory / Handoff / Eval 子代理 | 三个子代理分别评审初稿（Step 2） |
| 3 | `framework_adjust` | 总工框架设计师 | 综合评审意见，调整设计（Step 3） |
| 4 | `zonggong_integrate` | 总工 (Zonggong) | 综合集成，出 `architecture_pack`（Step 4） |
| 5 | `architecture_challenge` | 逆审 (Nishen) | 红队式挑战，找漏洞，写 `architecture_review` |
| 6 | `approval_gate` | 守门 (Shoumen) | LLM 汇总风险要点 → `gate_flags.risk_level`（展示给用户） |
| 7 | `final_spec` | 司南 (编译者) | 产出 `harness_design_draft.json` + `harness_design_final.md`（待审稿） |
| 8 | `sinan_approval` | 司南 (用户交互) | **带用户过完整 md**，收集 approve / reject / request_changes |
| 9 | `arch_revise` | 司南 (翻译者) | 把用户 reject 翻译成 `arch_revision_brief`，重入 framework_design |

每个 node 的 Reads / Writes / Artifacts / Routes 全表在 [src/sinan/nodes/NODES.md](../src/sinan/nodes/NODES.md#架构层-nodes-9)。

---

## 4. 输入 / 输出契约

### 入口（两种启动方式）
1. **完整流程**：从需求层走过来，`state["user_brief_form"]` 已经在内存
2. **`--from-brief <run_id>`**：从磁盘读 `runs/<run_id>/user_brief_form.json`，直接进 `framework_design`

不管哪种方式，所有架构层 node 都通过 `load_state_or_file(state, key)` 读取——state 没有就从磁盘对应的 `runs/<run_id>/<key>.json` 读。意味着架构层 **任意节点都可以单独重跑**，前提是上游 artifact 存在于磁盘。

- `runs/<run_id>/user_brief_form.json` — 需求层产出的自包含需求契约。它包含用户确认/拒绝/优先级信息，并保留目标、范围、成功标准、约束等需求包核心字段。
- （如果是 revision 轮次）`runs/<run_id>/arch_revision_brief.json` — 上一轮 reject 的修订简报

### 出口
- `runs/<run_id>/harness_design_draft.json` — **研发层的输入**（落盘是契约，state 是热路径）。**versioned 写入**：每次重跑都自动归档为 `harness_design_draft_v1.json` / `_v2.json` ... 可回滚 / 可 diff。

  **关键字段：`test_cases`** — 一组测试用例（id / scenario / input / expected_output_keys / expected_to_pass），由 `final_spec` 从 `success_criteria` 推导出占位骨架。研发层的 `evaluator_qa` 会用 `subprocess + timeout(60s)` 真跑 `harness/main.py` 对照这组用例打分。用户在 `sinan_approval` 阶段能看到、并能编辑 `harness_design_draft.json` 把占位补全。

- `runs/<run_id>/harness_design_final.md` — 给用户/审核者阅读的完整设计稿。**`sinan_approval` 就是带用户过这份 md**；用户决策依据的就是这份文档。

> 两个出口都在 `final_spec` 节点产出——这节点在 `sinan_approval` 之前运行。
> 也就是说：用户审批时手里已经有完整 md 在磁盘上了。
> 研发层入口：`python -m sinan.cli --from-design <run_id>`，从 `harness_design_draft.json` 恢复。

### 中间产物（按顺序生成）

| 文件 | 写入者 | 用途 |
|---|---|---|
| `framework_design.json` | `framework_design` | 总工初稿 |
| `subagent_reviews.json` | `subagent_review` | Memory / Handoff / Eval 三方评审 |
| `subagent_outputs.json` | `subagent_review` | Memory / Handoff / Eval 三方详细模块设计 |
| `framework_adjustment.json` | `framework_adjust` | 总工调整记录 |
| `architecture_pack.json` | `zonggong_integrate` | 综合后的架构包 |
| `architecture_review.json` | `architecture_challenge` | 逆审报告 |
| `arch_revision_brief.json` | `arch_revise` | 仅 reject 轮次产生 |
| `harness_design_draft.json` | `final_spec` | **出口** |
| `harness_design_final.md` | `final_spec` | **出口（人读版）** |

所有文件落到 `runs/<run_id>/`。

---

## 5. 路由规范

路由函数都在 [src/sinan/graph.py](../src/sinan/graph.py)。

### 边（线性）
- `approval_gate → final_spec`：守门讲完风险分级，立刻产出设计稿（md + json）
- `final_spec → sinan_approval`：司南带用户过完整 md，收集决策
- `arch_revise → framework_design`：reject 后回到辩论起点重生成

仅有一个路由器：

### `_approval_outcome_router` (graph.py)

```
approval == "approve"                            → END（final_spec 已运行过）
approval == "reject" / "request_changes"
    AND arch_reject_count < 3                    → arch_revise → framework_design
    AND arch_reject_count >= 3                   → raise RuntimeError("max retry")
```

**`arch_reject_count` 在 `sinan_approval` 检测到 reject/request_changes 后立即递增**（先递增再路由），所以最多允许 3 次用户拒绝，第 3 次时路由器抛 `RuntimeError`。

---

## 6. State 字段（架构层使用部分）

定义见 [src/sinan/state.py](../src/sinan/state.py)。架构层与需求层共用 `HarnessBuilderState`。下表只列架构层会读写的字段：

| 字段 | 类型 | 谁写 | 谁读 |
|---|---|---|---|
| `user_brief_form` | dict | 需求层 `brief_compile` | `framework_design`, `final_spec` |
| `framework_design` | dict | `framework_design` | `subagent_review`, `framework_adjust`, `zonggong_integrate` |
| `subagent_reviews` | dict | `subagent_review` | `framework_adjust`, `zonggong_integrate` |
| `subagent_outputs` | dict | `subagent_review` | `zonggong_integrate`, `final_spec` |
| `framework_adjustments` | dict | `framework_adjust` | `zonggong_integrate` |
| `architecture_pack` | dict | `zonggong_integrate` | `architecture_challenge`, `approval_gate`, `sinan_approval`, `final_spec` |
| `architecture_review` | dict | `architecture_challenge` | `approval_gate`, `sinan_approval`, `arch_revise` |
| `arch_revision_brief` | dict | `arch_revise` | `framework_design`（重入轮次） |
| `gate_flags` | `GateFlags` TypedDict | `approval_gate` | router |
| `resume_payload` | dict | `sinan_approval` | router |
| `arch_reject_count` | int | `sinan_approval` (++) | `_approval_outcome_router` |
| `risk_register` | list[dict] | `architecture_challenge` | 跨层风险跟踪 |
| `harness_design_draft` | dict | `final_spec` | 研发层 |

---

## 7. 关键文件

| 文件 | 用途 |
|---|---|
| [src/sinan/graph.py](../src/sinan/graph.py) | 全部 node 注册 + 两个 router |
| [src/sinan/state.py](../src/sinan/state.py) | `HarnessBuilderState` + `GateFlags` |
| [src/sinan/nodes/framework_design.py](../src/sinan/nodes/framework_design.py) | 四步辩论 Step 1 |
| [src/sinan/nodes/subagent_review.py](../src/sinan/nodes/subagent_review.py) | 四步辩论 Step 2 |
| [src/sinan/nodes/framework_adjust.py](../src/sinan/nodes/framework_adjust.py) | 四步辩论 Step 3 |
| [src/sinan/nodes/zonggong_integrate.py](../src/sinan/nodes/zonggong_integrate.py) | 四步辩论 Step 4 |
| [src/sinan/nodes/architecture_challenge.py](../src/sinan/nodes/architecture_challenge.py) | 逆审挑战 |
| [src/sinan/nodes/approval_gate.py](../src/sinan/nodes/approval_gate.py) | 守门 / 风险评级 |
| [src/sinan/nodes/sinan_approval.py](../src/sinan/nodes/sinan_approval.py) | 用户审批（同步 `input()`） |
| [src/sinan/nodes/arch_revise.py](../src/sinan/nodes/arch_revise.py) | reject → revision brief |
| [src/sinan/nodes/final_spec.py](../src/sinan/nodes/final_spec.py) | 出口编译 |
| [src/sinan/prompts.py](../src/sinan/prompts.py) | 所有角色 prompts |
| [src/sinan/mock_responses.py](../src/sinan/mock_responses.py) | mock 输出 |

---

## 8. 怎么开发

### 加一个新 node

1. 在 `src/sinan/nodes/` 下新建 `xxx.py`，文件头按统一模板写 docstring：

   ```python
   """xxx — <一句话职责>.

   Agent: <角色名>
   Layer: 架构层

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

2. 实现 `def xxx_node(state: HarnessBuilderState) -> dict:`，返回完整 state dict。
3. 在 `src/sinan/nodes/__init__.py` 中 `from . import xxx`。
4. 在 `src/sinan/graph.py` 中：`g.add_node(...)`，并修改 edges（如果不是直插在最后）。
5. 在 [NODES.md](../src/sinan/nodes/NODES.md) 中加表格行。
6. 在本指南"节点清单"和"流水线"ASCII 图中加。
7. 在 `mock_responses.py` 中加 mock。
8. `pytest -q` 确认通过。

### 改路由

1. 改 `graph.py` 里 router 函数（或加新的 `add_conditional_edges`）。
2. 同步改 [NODES.md](../src/sinan/nodes/NODES.md) 的 Routes 列。
3. 同步改本指南"路由规范"段和 ASCII 图。

### 加一个 artifact

1. 在 node 里用 `write_artifact_versioned(...)` 落盘。
2. 在 docstring 的 Artifacts 段加。
3. 在 [NODES.md](../src/sinan/nodes/NODES.md) 对应行加。
4. 在本指南"中间产物"表加。

### 改 risk 等级判定逻辑

`approval_gate` 写 `state["gate_flags"]["risk_level"]`，由 LLM 判定（不是硬编码规则）。
要改：动 `approval_gate.py` 的 prompt。注意：risk_level 这里只作为**展示信息**给用户，
不参与路由决策——架构辩论结束后**必须**进用户审批，与 risk_level 值无关。
**注意**：如果加新的 risk 分支（如 "medium"），同步改：
- `state.py` 的 `GateFlags` 注释
- [NODES.md](../src/sinan/nodes/NODES.md) `approval_gate` 行的 Writes
- `approval_gate.py` 节点 docstring
- 本指南"路由规范"段

---

## 9. 容易踩的坑

- **架构层和需求层共享 `HarnessBuilderState`**：加字段时考虑会不会影响需求层。
- **`framework_design` 可能被多次调用**：因为 reject 会重入它。所以它必须能读 `arch_revision_brief`（如果存在）。同样 `final_spec` 也会被多次调用——每次产出新的 versioned draft + 新的 md。
- **`sinan_approval` 是同步 `input()`**：跟需求层的 `sinan_debrief` 同问题，未来要 web UI 必须重写。
- **`arch_reject_count` 在 sinan_approval 节点里就 +=1**（路由前），超过 3 次抛 RuntimeError——不是 2 次，文档同步过。
- **`final_spec` 不是终结节点**：在 `sinan_approval` 之前运行，产出的 md/json 是**待审稿**。rejected 之后会重生成。approve 才 END。
- **改完代码记得回 [CLAUDE.md 改动同步原则](../CLAUDE.md#改动同步原则强制) 核对清单。**

---

## 10. 怎么调试

- 看 `runs/<run_id>/decision_log.md` — 每个 node 的决策摘要 + 守门评级
- 看 `runs/<run_id>/architecture_pack.json` 和 `architecture_review.json` — 设计 vs 审查
- 看 `runs/<run_id>/run_state.yaml` — 含 `arch_reject_count`、`gate_flags.risk_level` 等
- 跑 `pytest tests/test_e2e_mock.py -v` — mock 模式下走完整流水
- 想测 reject loop：在 `sinan_approval` 的 mock 输入里返回 `"reject"`
