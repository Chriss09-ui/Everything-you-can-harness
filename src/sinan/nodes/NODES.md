# 需求层 + 架构层 — Node Contract Reference

> 本文档是需求层 + 架构层的开发规范。每个 node 模块遵循统一的 **Agent Handoff Contract**，
> 明确"谁写什么、谁读什么"，让模型能快速理解而无需细读实现代码。

---

## 交接协议核心原则

### 原则 1：Artifact 是交接契约

| 产出节点 | Artifact 文件 | 消费节点 |
|----------|--------------|----------|
| spec_expansion | `requirement_pack.json` | spec_challenge, brief_debate, brief_compile |
| spec_challenge | `spec_review.json` | brief_debate |
| brief_debate | `brief_debate.json` | sinan_debrief, brief_compile |
| sinan_debrief | — (state only: user_brief_answers) | brief_compile |
| brief_compile | `user_brief_form.json` | framework_design |
| framework_design | `framework_design.json` | subagent_review, framework_adjust |
| subagent_review | `subagent_reviews.json`, `subagent_outputs.json` | framework_adjust, zonggong_integrate, final_spec |
| framework_adjust | `framework_adjustment.json` | zonggong_integrate |
| zonggong_integrate | `architecture_pack.json` | architecture_challenge, approval_gate, final_spec |
| architecture_challenge | `architecture_review.json` | approval_gate |
| approval_gate | gate_flags (state) | sinan_approval, final_spec |
| arch_revise | `arch_revision_brief.json` | framework_design |
| final_spec | `harness_design_draft.json`, `harness_design_final.md` | 研发层 (coding layer) |

### 原则 2：每个 Node 只有一个职责

- `spec_expansion`：只扩展需求，不评判
- `spec_challenge`：只挑战，不修改需求
- `approval_gate`：只评估风险等级，不做审批决策

### 原则 3：路由决策集中在 graph.py

条件路由（approval_gate → sinan_approval/final_spec, sinan_approval → arch_revise/final_spec）全部由 graph.py 的 router 函数决定。

### 原则 4：Node 返回完整 state dict

---

## Node 合约模板

```python
"""<node_name> — <一句话描述>.

Agent: <角色名>（<中文名>）
Layer: <需求层|架构层>

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

---

## 需求层 Nodes (5)

### 1. spec_expansion

| 属性 | 值 |
|------|------|
| Agent | 拓谱 (Tuopu) |
| Layer | 需求层 |
| Reads | `user_raw_input` |
| Writes | `requirement_pack`, `current_phase`, `artifact_versions` |
| Artifacts | `requirement_pack.json` |
| Routes | → `spec_challenge` (linear) |

### 2. spec_challenge

| 属性 | 值 |
|------|------|
| Agent | 诘问 (Jiewen) |
| Layer | 需求层 |
| Reads | `requirement_pack` |
| Writes | `spec_review`, `current_phase`, `artifact_versions`, `risk_register` |
| Artifacts | `spec_review.json` |
| Routes | → `brief_debate` (linear) |

### 3. brief_debate

| 属性 | 值 |
|------|------|
| Agent | 拓谱 + 诘问 (辩论) |
| Layer | 需求层 |
| Reads | `requirement_pack`, `spec_review` |
| Writes | `brief_debate`, `current_phase`, `artifact_versions` |
| Artifacts | `brief_debate.json` |
| Routes | → `sinan_debrief` (linear) |

### 4. sinan_debrief

| 属性 | 值 |
|------|------|
| Agent | 司南 (用户交互) |
| Layer | 需求层 |
| Reads | `brief_debate` |
| Writes | `user_brief_answers`, `current_phase` |
| Artifacts | (无 — 通过 input() 收集用户答案) |
| Routes | → `brief_compile` (linear) |

### 5. brief_compile

| 属性 | 值 |
|------|------|
| Agent | 契约 (Qiyue) |
| Layer | 需求层 (出口) |
| Reads | `requirement_pack`, `brief_debate`, `user_brief_answers` |
| Writes | `user_brief_form`, `current_phase`, `artifact_versions` |
| Artifacts | `user_brief_form.json` — 自包含需求契约，包含确认信息 + 需求包核心字段，架构层入口 |
| Routes | → `framework_design` (linear, 进入架构层) |

> **层间交接点：** `user_brief_form.json` 是需求层→架构层的唯一交接物。

---

## 架构层 Nodes (9)

### 6. framework_design

| 属性 | 值 |
|------|------|
| Agent | 总工框架设计师 |
| Layer | 架构层 (四步辩论 Step 1) |
| Reads | `user_brief_form`, `arch_revision_brief` (如有) |
| Writes | `framework_design`, `current_phase`, `artifact_versions` |
| Artifacts | `framework_design.json` |
| Routes | → `subagent_review` (linear) |

### 7. subagent_review

| 属性 | 值 |
|------|------|
| Agent | 子代理 (Memory / Handoff / Eval) |
| Layer | 架构层 (四步辩论 Step 2) |
| Reads | `framework_design` |
| Writes | `subagent_reviews`, `subagent_outputs`, `current_phase`, `artifact_versions` |
| Artifacts | `subagent_reviews.json`, `subagent_outputs.json` |
| Routes | → `framework_adjust` (linear) |

### 8. framework_adjust

| 属性 | 值 |
|------|------|
| Agent | 总工框架设计师 |
| Layer | 架构层 (四步辩论 Step 3) |
| Reads | `framework_design`, `subagent_reviews` |
| Writes | `framework_design` (overwrites Round-1 with the adjusted version; Round-1 is auto-archived as `framework_design_v1.json`), `framework_adjustments`, `current_phase`, `artifact_versions` |
| Artifacts | `framework_adjustment.json`, `framework_design.json` (versioned — see Artifacts table below) |
| Routes | → `zonggong_integrate` (linear) |

### 9. zonggong_integrate

| 属性 | 值 |
|------|------|
| Agent | 总工 (Zonggong) |
| Layer | 架构层 (四步辩论 Step 4) |
| Reads | `framework_design`, `subagent_outputs`, `subagent_reviews`, `framework_adjustments`, `arch_revision_brief`, `user_brief_form` (or `requirement_pack` fallback) |
| Writes | `architecture_pack`, `current_phase`, `artifact_versions` |
| Artifacts | `architecture_pack.json` |
| Routes | → `architecture_challenge` (linear) |

> Reads 全部经 `load_state_or_file`（state 优先 + 磁盘 fallback），让 `--from-brief` /
> `--from-design` 重入路径不依赖 state 仍能正常工作。

### 10. architecture_challenge

| 属性 | 值 |
|------|------|
| Agent | 逆审 (Nishen) |
| Layer | 架构层 |
| Reads | `architecture_pack` |
| Writes | `architecture_review`, `current_phase`, `artifact_versions`, `risk_register` |
| Artifacts | `architecture_review.json` |
| Routes | → `approval_gate` (linear) |

### 11. approval_gate

| 属性 | 值 |
|------|------|
| Agent | 守门 (Shoumen) |
| Layer | 架构层 |
| Reads | `architecture_pack`, `architecture_review` |
| Writes | `gate_flags` (设置 risk_level / shoumen_reasoning / key_concerns / checklist / flagged_risks), `pending_interrupt`, `current_phase` |
| Artifacts | (无) |
| Routes | → `sinan_approval` (用户审批是**强制**环节，守门只汇总风险要点展示给用户) |

### 12. sinan_approval

| 属性 | 值 |
|------|------|
| Agent | 司南 (用户交互) |
| Layer | 架构层 |
| Reads | `harness_design_draft`（含完整设计稿，分章节展示）, `gate_flags`（守门风险摘要） |
| Writes | `resume_payload`, `arch_reject_count++` on reject, `pending_interrupt=Null`, `current_phase` |
| Artifacts | (无 — interactive console node) |
| Routes | → END (approve, router 决定) / → arch_revise (reject/request_changes, ≤3 轮，超出 RuntimeError) |

> **设计意图**：本节点前置的 `final_spec` 已经把完整的 `harness_design_draft.json` +
> `harness_design_final.md` 落盘。司南在这节点里**分章节把完整设计讲给用户听**
> （需求 / 架构 / 模块 / 治理 / 理念 / 审查 / 风险），让用户在掌握全貌后决策。
>
> 单次 run 内可能调用多次（reject 后 framework_design 重走辩论 → 重新进 final_spec → 重新进 sinan_approval）。

### 13. arch_revise

| 属性 | 值 |
|------|------|
| Agent | 司南 (翻译者) |
| Layer | 架构层 |
| Reads | `architecture_review`, `resume_payload` |
| Writes | `arch_revision_brief`, `current_phase` |
| Artifacts | `arch_revision_brief.json` |
| Routes | → `framework_design` (linear, 重入四步辩论) |

> 注：`arch_reject_count` 不在这里递增——在 `sinan_approval` 节点里就 +=1 了（reject 之前就计数）。

### 14. final_spec

| 属性 | 值 |
|------|------|
| Agent | 司南 (编译者) |
| Layer | 架构层（sinan_approval 前一站） |
| Reads | `architecture_pack`, `user_brief_form`, `framework_design`, `subagent_reviews`, `subagent_outputs`（均经 `load_state_or_file()`） |
| Writes | `harness_design_draft`, `current_phase` |
| Artifacts | `harness_design_draft.json` (**versioned**) — 研发层 AI 消费；`harness_design_final.md` — **给用户阅读的完整设计稿**，sinan_approval 就基于这份 md 讲 |
| Routes | → `sinan_approval` (linear, 强制用户审批) |

> **设计意图**：本节点的位置在 `sinan_approval` **之前**——先把两版交接物准备好，
> 再让司南带着用户过一遍。approve 时直接结束（router → END），reject 时回去
> `framework_design` 重走辩论 → 重新进 final_spec 重新生成 md + json。
>
> **层间交接点**：`harness_design_draft.json` 是架构层→研发层的唯一交接物。

---

## 路由函数规范

```python
def _approval_outcome_router(state: HarnessBuilderState) -> str:
    """Route: sinan_approval → END | arch_revise.

    Condition:
        → END          when approval == "approve"
        → arch_revise  when rejection (≤3 rounds, else RuntimeError)
    """
```

> 注：从 `approval_gate` 开始的边都是这种顺序：`approval_gate → final_spec → sinan_approval`。
> 用户审批是**强制**环节，守门只产出一目了然的风险摘要展示给用户。

---

## 入口节点（不在 graph 中注册，由 CLI 直接调用）

- `intake.py` — 接收用户原始输入，初始化 state。由 `cli.py` 在 `graph.invoke()` 之前调用，因此不在 `graph.py` 里注册。

## 已删除的遗留节点

- `wait_brief.py` — 已删除，由 `sinan_debrief` 替代。`mock_responses.py` 中的 phantom 名称也已清理。

---

## 新增 Node 时的检查清单

- [ ] 按上方模板写 docstring（Agent / Layer / Reads / Writes / Artifacts / Routes）
- [ ] 只做一件事，不混入其他职责
- [ ] 在本文件 (`NODES.md`) 中注册
- [ ] 在 `graph.py` 中添加 node 和 edge
- [ ] 添加 mock response（测试用）
- [ ] 跑 `pytest` 确认不破坏现有流
