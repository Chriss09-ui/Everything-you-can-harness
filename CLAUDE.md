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

每一层有自己的"指南 + 合约表"两个文件，**碰哪个层的代码就必须改哪层的两个文件**：

| 层 | 指南（必须同步） | 合约表（必须同步） |
|---|---|---|
| 需求层 | `docs/requirement_layer.md` | `src/sinan/nodes/NODES.md` |
| 架构层 | `docs/architecture_layer.md` | `src/sinan/nodes/NODES.md` |
| 研发层 | `docs/coding_layer.md` | `src/sinan/coding/NODES.md` |

下表是 "改了什么 → 必须同步改哪些文件" 的速查：

| 你改了什么 | 必须同步改 |
|---|---|
| 新增 / 删除 / 重命名 node | 当前层合约表（"节点清单"段）+ 当前层指南（"节点清单"段）+ `graph.py` 注册和路由 |
| 改 node 的 Reads / Writes / Artifacts / Routes | 当前层合约表该 node 行 + 该 node 文件头的 docstring + 当前层指南对应段落（State/Artifact/Routes） |
| 加 / 删 artifact 文件 | 当前层合约表 Artifacts 列 + 当前层指南 "Artifact 清单" 段 |
| 改 graph 路由逻辑 / 条件分支 | 当前层合约表 Routes 列 + 当前层指南的 ASCII 流程图 + router 计数 |
| 改 State schema | `state.py` 字段注释 + 当前层指南的 "State 字段" 段（含写入者列） |
| 改 `runs/<id>/` 下文件名或格式 | 当前层合约表 Artifacts 列 + README 的 "Run Artifacts" 段 |
| 改 prompt 或 mock 输出 | 改 `prompts.py` 或 `mock_responses.py`，**无需**改合约文档（这些不是契约） |
| 新增 artifact 字段 / 改 artifact 形状 | `src/sinan/validation.py` 的 `_REQUIRED_FIELDS` 对应条目 + 测试（`tests/test_validation.py`） |

> **硬上限 / 计数常量**（如 `sprint_number ≥ 10`、router 数量）任何一处变化必须同步：代码、当前层指南、`docs/sinan_流程图_v2.md` 三处。文档之间自相矛盾是最常见的漂移源。
>
> 注：架构层 `arch_reject_count` 不再是硬上限——拒绝循环没有数量限制，由用户在 `sinan_approval` 中选 `approve` 或 `abort` 显式终止。`arch_reject_count` 仍保留作展示/审计用途。

**为什么这么严**：这个系统的核心承诺是「Agent 通过文件交接」。如果代码里写的契约 ≠ 文档里写的契约，整个交接协议就垮了，新接手的 AI 会按文档去写、按代码去跑，永远对不上。

## 跑代码

```bash
# venv 已存在的话直接跑
PYTHONPATH=src .venv/bin/python -m sinan.cli                       # 完整流程
PYTHONPATH=src .venv/bin/python -m sinan.cli --from-brief <id>     # 跳过需求层
PYTHONPATH=src .venv/bin/python -m sinan.cli --from-design <id>    # 跳过整个设计层
PYTHONPATH=src .venv/bin/python -m pytest -q                       # 跑测试

# 没有 venv 就建一个
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/pip install pytest
```

> `--from-brief` 和 `--from-design` 都依赖磁盘 artifact，无需保留内存 state。
> 任何 node 都通过 `load_state_or_file()` 实现「state 优先 + 磁盘 fallback」。

> **Schema 校验**：所有 LLM 产物在 `parse_and_validate_artifact()` 解析时校验；所有 Python 组装的产物（`harness_design_draft`、`bug_report`、`sprint_result`）在写盘前用 `validate_artifact()` 校验；跨层边界（planner 读 draft、framework_design 读 brief）做读后校验。Schema 定义在 [src/sinan/validation.py](src/sinan/validation.py)。

## 关键行为说明

- **用户交互目前是同步 CLI `input()`**，不是 LangGraph 原生 `interrupt() / resume()`。`pending_interrupt`、`resume_payload` 是 state 里的占位字段，未完整接入。
- **架构层有真实的 revision loop**：用户 reject → `arch_revise` → 重入 `framework_design`，最多 3 轮，超出抛 RuntimeError。
- **研发层 sprint 上限 10 轮**，每 sprint 内 negotiation ≤ 3 轮，fix loop ≤ 2 轮。
- **跨 session 不依赖 state**：研发层每个 session 重置上下文，靠磁盘 artifact（`feature_list.json`, `claude-progress.txt`, `sprint_contract.json`, `evaluator_grade.json`, `bug_report.json`）重新 hydrate。

## Run 产出

一次运行产出到 `runs/<run_id>/`，设计层 artifact 在根目录、研发层代码仓在 `runs/<run_id>/harness/`。`runs/` 已被 `.gitignore` 屏蔽，不会进 git。

详细 artifact 清单见各层指南。

## 历史遗留命名（如果在旧代码 / 旧文档里看到）

`wait_brief`, `wait_approval`, `architecture_draft`, `brief_gate` —— 都已被替换。现在叫 `sinan_debrief`, `sinan_approval`, 四步辩论流程。看到这些名字直接当历史档案。

## 仓库环境

- `src/` 布局，运行需要 `PYTHONPATH=src`。
- `.venv/`, `__pycache__/`, `runs/` 都被 `.gitignore` 屏蔽，**不要 `git add` 它们**。
- 老仓库 `claude-code-` 是历史档案，本仓库 `Everything-you-can-harness` 是当前主线。
