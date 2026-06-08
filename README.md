# 司南 Harness Builder

把一段自然语言需求，端到端转化为可运行的代码 harness。

## What It Does

司南是一个用 LangGraph 编排的三层多智能体流水线：

1. **需求层** — 把用户的一句话需求，经过扩展、质疑、辩论，再与用户对齐，形成一份**需求契约**。
2. **架构层** — 把需求契约经过四步辩论、子代理评审、风险审查、（必要时的）人工审批，转化为一份**架构设计稿**。
3. **研发层** — 把设计稿在四重嵌套循环（Sprint / Session / Feature / Fix）中实现成可运行的代码。

Agent 之间通过**磁盘文件契约**交接，所有路由决策集中在 graph 层，所有产出可审计、可回放、可复现。

## Quick Start

```bash
# 1. Create and activate a virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 2. Install dependencies (plus pytest for running tests)
pip install -r requirements.txt
pip install pytest

# 2b. (Only for a REAL coding-layer run) install + authenticate the Claude Code
# CLI. The coding layer's LLM nodes run as Claude Agent SDK agents, and the SDK
# drives the `claude` CLI as a subprocess. Tests don't need this (they run on
# MockAgentRunner, fully offline).
#   npm install -g @anthropic-ai/claude-code   # or: brew install claude
#   claude   # then complete login once

# 3. Run the CLI from the repo root
PYTHONPATH=src python -m sinan.cli

# 3b. Or skip the requirement layer (uses an existing user_brief_form.json)
PYTHONPATH=src python -m sinan.cli --from-brief <run_id>

# 3c. Or skip the entire design layer (uses an existing harness_design_draft.json)
PYTHONPATH=src python -m sinan.cli --from-design <run_id>

# 4. Run tests
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Resume flags read from disk and jump into the corresponding layer:

- `--from-brief <run_id>` — reads `runs/<run_id>/user_brief_form.json`, skips the
  requirement layer, re-runs architecture + coding. Use to retry an
  architecture / design iteration without re-prompting the user.
- `--from-design <run_id>` — reads `runs/<run_id>/harness_design_draft.json`,
  skips both design layers, re-runs coding only. Use to retry the slow coding
  layer without re-running the (interactive) design layers.

Repo 用 `src/` 布局，没有 `pyproject.toml`，所以运行模块前需要 `PYTHONPATH=src`。

## LLM Mode

研发层和设计层用不同的执行机制：

**设计层**（单轮补全，`src/sinan/llm.py` `get_llm_client`）：
- 未设置 API key → 内置 `MockLLMClient`（确定性输出，测试可重复）
- 设置 `OPENAI_API_KEY` 或 `ANTHROPIC_API_KEY` → 调用真实 provider
- SDK 未安装 → 自动 fallback 到 mock

**研发层**（7 个 LLM 节点跑成真 agent，`src/sinan/agent.py` `get_agent_runner`）：
- `SINAN_AGENT_BACKEND=real` 或设置了 `ANTHROPIC_API_KEY` → `RealAgentRunner`
  （经 Claude Agent SDK 拉起 `claude` CLI，agent 用 Read/Write/Edit/Bash 等工具
  在 `harness/` 内自主读写跑测试）。**需先装好并认证 `claude` CLI**（见 Quick Start 2b）。
- 否则，或 `SINAN_AGENT_BACKEND=mock` → `MockAgentRunner`（离线，不起 CLI）。

> **测试始终离线**：`tests/conftest.py` 强制清空凭证并钉 `SINAN_AGENT_BACKEND=mock`，
> 所以 `pytest -q` 不依赖网络或真实 `claude` CLI，与本地 `.env` 无关。

本地实验时复制 `.env.example` 到 `.env` 并填入 key。

## Project Structure

```
src/sinan/
├── cli.py                   # 终端入口（顺序跑设计层 → 研发层）
├── graph.py                 # 需求层 + 架构层 LangGraph 装配
├── state.py                 # HarnessBuilderState schema
├── artifacts.py             # run 目录、日志、版本化 artifact 写入
├── llm.py                   # 设计层单轮补全：Mock / OpenAI / Anthropic 适配器
├── agent.py                 # 研发层 agent 执行 seam：Claude Agent SDK / MockAgentRunner
├── mock_responses.py        # 设计层确定性 mock 输出
├── prompts.py               # 设计层角色 prompt
├── nodes/                   # 需求层 + 架构层 node 实现
│   └── NODES.md             # ⭐ Node 合约表（source of truth）
└── coding/                  # 研发层包
    ├── graph.py             # 研发层 LangGraph（26 nodes）
    ├── state.py             # CodingState schema
    ├── prompts.py           # Planner / Generator / Evaluator prompts
    ├── git.py / testing.py  # git 与测试封装
    ├── mock_responses.py    # 研发层 mock 输出
    ├── nodes/               # 26 个 node 模块
    └── NODES.md             # ⭐ 研发层 Node 合约表

tests/                       # smoke + e2e mock tests
docs/
├── requirement_layer.md     # ⭐ 需求层 AI 上手指南
├── architecture_layer.md    # ⭐ 架构层 AI 上手指南
├── coding_layer.md          # ⭐ 研发层 AI 上手指南
└── *_流程图_v2.md            # 流程图
```

## Three Layers — Where To Read

| 想做什么 | 看哪份文档 |
|---|---|
| AI 接手开发**需求层** | [docs/requirement_layer.md](docs/requirement_layer.md) |
| AI 接手开发**架构层** | [docs/architecture_layer.md](docs/architecture_layer.md) |
| AI 接手开发**研发层** | [docs/coding_layer.md](docs/coding_layer.md) |
| 查需求/架构层每个 node 的契约 | [src/sinan/nodes/NODES.md](src/sinan/nodes/NODES.md) |
| 查研发层每个 node 的契约 | [src/sinan/coding/NODES.md](src/sinan/coding/NODES.md) |
| 全局工作守则 + 改动同步规范 | [CLAUDE.md](CLAUDE.md) |

## Run Artifacts

每次运行产出到 `runs/<run_id>/`，包含需求包、架构稿、决策日志、版本注册表等。`runs/` 被 `.gitignore` 屏蔽。详见各层指南。

## Scope

**当前实现**：需求扩展 / 需求挑战 / 用户对齐 / 架构辩论 / 风险审批 / 设计稿生成 / 研发层 sprint 编排 / 自修复循环。

**不在当前 scope**：LangGraph `interrupt() / resume()` 完整接入（目前用同步 CLI `input()`）、生产级持久化、长期记忆基础设施。
