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
| Writes | `framework_adjustments`, `current_phase`, `artifact_versions` |
| Artifacts | `framework_adjustment.json` |
| Routes | → `zonggong_integrate` (linear) |

### 9. zonggong_integrate

| 属性 | 值 |
|------|------|
| Agent | 总工 (Zonggong) |
| Layer | 架构层 (四步辩论 Step 4) |
| Reads | `framework_design`, `subagent_reviews`, `framework_adjustments` |
| Writes | `architecture_pack`, `current_phase`, `artifact_versions` |
| Artifacts | `architecture_pack.json` |
| Routes | → `architecture_challenge` (linear) |

### 10. architecture_challenge

| 属性 | 值 |
|------|------|
| Agent | 逆审 (Nishen) |
| Layer | 架构层 |
| Reads | `architecture_pack` |
| Writes | `architecture_review`, `current_phase`, `artifact_versions`, `risk_register`, `gate_flags` |
| Artifacts | `architecture_review.json` |
| Routes | → `approval_gate` (linear) |

### 11. approval_gate

| 属性 | 值 |
|------|------|
| Agent | 守门 (Shoumen) |
| Layer | 架构层 |
| Reads | `architecture_pack`, `architecture_review`, `gate_flags` |
| Writes | `gate_flags` (设置 risk_level), `current_phase` |
| Artifacts | (无) |
| Routes | → `final_spec` (risk=low) / → `sinan_approval` (risk=high) |

### 12. sinan_approval

| 属性 | 值 |
|------|------|
| Agent | 司南 (用户交互) |
| Layer | 架构层 |
| Reads | `architecture_pack`, `architecture_review` |
| Writes | `resume_payload`, `current_phase` |
| Artifacts | (无 — 通过 input() 收集用户审批) |
| Routes | → `final_spec` (approve) / → `arch_revise` (reject/request_changes, ≤2 轮) |

### 13. arch_revise

| 属性 | 值 |
|------|------|
| Agent | 司南 (翻译者) |
| Layer | 架构层 |
| Reads | `architecture_review`, `resume_payload` |
| Writes | `arch_revision_brief`, `arch_reject_count++`, `current_phase` |
| Artifacts | `arch_revision_brief.json` |
| Routes | → `framework_design` (linear, 重入四步辩论) |

### 14. final_spec

| 属性 | 值 |
|------|------|
| Agent | 司南 (编译者) |
| Layer | 架构层 (出口) |
| Reads | `architecture_pack`, `user_brief_form`（均经 `load_state_or_file()`，state 空时回退到磁盘） |
| Writes | `harness_design_draft`, `current_phase` |
| Artifacts | `harness_design_draft.json` (**versioned**), `harness_design_final.md` |
| Routes | → END |

> **层间交接点：** `harness_design_draft.json` 是架构层→研发层的唯一交接物。

---

## 路由函数规范

```python
def _approval_gate_router(state: HarnessBuilderState) -> str:
    """Route: approval_gate → final_spec | sinan_approval.

    Condition:
        → final_spec      when risk_level == "low"
        → sinan_approval  when risk_level != "low"
    """

def _approval_outcome_router(state: HarnessBuilderState) -> str:
    """Route: sinan_approval → final_spec | arch_revise.

    Condition:
        → final_spec   when approval == "approve"
        → arch_revise  when rejection (≤2 rounds, else RuntimeError)
    """
```

---

## 遗留节点 (不在当前 graph 中)

- `intake.py` — 早期入口节点，已由 `spec_expansion` 替代
- `wait_brief.py` — 早期用户交互节点，已由 `sinan_debrief` 替代

---

## 新增 Node 时的检查清单

- [ ] 按上方模板写 docstring（Agent / Layer / Reads / Writes / Artifacts / Routes）
- [ ] 只做一件事，不混入其他职责
- [ ] 在本文件 (`NODES.md`) 中注册
- [ ] 在 `graph.py` 中添加 node 和 edge
- [ ] 添加 mock response（测试用）
- [ ] 跑 `pytest` 确认不破坏现有流
