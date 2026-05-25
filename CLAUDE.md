# 司南 Harness Builder — Contributor Context

> 给所有上手这个 repo 的 AI / 人类协作者的工作守则。**先读这里，再读代码。**

## 一页纸概览

司南是用 LangGraph 编排的三层多智能体系统：

| 层 | 目的 | 入口契约 | 出口契约 |
|---|---|---|---|
| **需求层** | 把模糊需求 → 经过辩论的需求契约 | 用户一句话 | `user_brief_form.json` |
| **架构层** | 把需求契约 → 经过审查的设计稿 | `user_brief_form.json` | `harness_design_draft.json` |
| **研发层** | 把设计稿 → 可运行代码 | `harness_design_draft.json` | `runs/<id>/harness/` 下的代码仓 |

三层都遵守同一套**节点合约协议**：每个 node 只做一件事；路由集中在 `graph.py`；artifact（不是 state）是 agent 之间的真实交接。

## 三层指南索引

接手某一层开发时，**先读对应的层级指南**，再读 NODES.md：

| 层 | 指南（必读，AI 上手） | 合约表（查询） |
|---|---|---|
| 需求层 | [docs/requirement_layer.md](docs/requirement_layer.md) | [src/sinan/nodes/NODES.md](src/sinan/nodes/NODES.md) |
| 架构层 | [docs/architecture_layer.md](docs/architecture_layer.md) | [src/sinan/nodes/NODES.md](src/sinan/nodes/NODES.md) |
| 研发层 | [docs/coding_layer.md](docs/coding_layer.md) | [src/sinan/coding/NODES.md](src/sinan/coding/NODES.md) |

需求层 + 架构层共用同一个 graph (`src/sinan/graph.py`) 和同一份合约表，因为它们共享 `HarnessBuilderState`；研发层独立 (`src/sinan/coding/graph.py`)。

## 改动同步原则（强制）

> **任何改动代码的 PR/commit，必须在同一个 commit 内同步更新对应合约文档。未同步合约的 PR 视为不完整。**

| 你改了什么 | 必须同步改 |
|---|---|
| 新增 / 删除 / 重命名 node | 该层 `NODES.md` 表格 + 该层指南的"节点清单"段 + `graph.py` 注册和路由 |
| 改 node 的 Reads / Writes / Artifacts / Routes | 该层 `NODES.md` 该 node 行 + 该 node 文件头的 docstring |
| 加 / 删 artifact 文件 | 该层 `NODES.md` 的 Artifacts 列 + 该层指南的 "Artifact 清单" 段 |
| 改 graph 路由逻辑 / 条件分支 | 该层 `NODES.md` 的 Routes 列 + 该层指南的 ASCII 流程图 |
| 改 State schema | `state.py` 字段注释 + 该层指南的 "State 字段" 段 |
| 改 `runs/<id>/` 下文件名或格式 | 该层 `NODES.md` 的 Artifacts 列 + README 的 "Run Artifacts" 段 |
| 改 prompt 或 mock 输出 | 改 `prompts.py` 或 `mock_responses.py`，**无需**改合约文档（这些不是契约） |

**为什么这么严**：这个系统的核心承诺是「Agent 通过文件交接」。如果代码里写的契约 ≠ 文档里写的契约，整个交接协议就垮了，新接手的 AI 会按文档去写、按代码去跑，永远对不上。

## 跑代码

```bash
# venv 已存在的话直接跑
PYTHONPATH=src .venv/bin/python -m sinan.cli                  # 跑 CLI
PYTHONPATH=src .venv/bin/python -m pytest -q                  # 跑测试

# 没有 venv 就建一个
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pytest
```

## 关键行为说明

- **用户交互目前是同步 CLI `input()`**，不是 LangGraph 原生 `interrupt() / resume()`。`pending_interrupt`、`resume_payload` 是 state 里的占位字段，未完整接入。
- **架构层有真实的 revision loop**：用户 reject → `arch_revise` → 重入 `framework_design`，最多 2 轮，超出抛 RuntimeError。
- **研发层 sprint 上限 10 轮**，每 sprint 内 negotiation ≤ 3 轮，fix loop ≤ 2 轮。
- **跨 session 不依赖 state**：研发层每个 session 重置上下文，靠磁盘 artifact（`feature_list.json`, `claude-progress.txt`, `sprint_contract.json`, `evaluator_grade.json`, `bug_report.json`）重新 hydrate。

## Run 产出

一次运行产出到 `runs/<run_id>/`，研发层产出到 `runs/<run_id>_coding/harness/`。`runs/` 已被 `.gitignore` 屏蔽，不会进 git。

详细 artifact 清单见各层指南。

## 历史遗留命名（如果在旧代码 / 旧文档里看到）

`wait_brief`, `wait_approval`, `architecture_draft`, `brief_gate` —— 都已被替换。现在叫 `sinan_debrief`, `sinan_approval`, 四步辩论流程。看到这些名字直接当历史档案。

## 仓库环境

- `src/` 布局，运行需要 `PYTHONPATH=src`。
- `.venv/`, `__pycache__/`, `runs/` 都被 `.gitignore` 屏蔽，**不要 `git add` 它们**。
- 老仓库 `claude-code-` 是历史档案，本仓库 `Everything-you-can-harness` 是当前主线。
