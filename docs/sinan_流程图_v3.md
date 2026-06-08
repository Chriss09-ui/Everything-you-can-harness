```
═══════════════════════════════════════════════════════════════════════════════
                  司南 Harness Builder — V3 完整流程图（中文详注版）
═══════════════════════════════════════════════════════════════════════════════

  ┌────── CLI (cli.py main) ──────┐
  │  用户输入一段自然语言需求       │   ★ 用户交互 0
  │  生成 run_id = run_xxxxxxxx   │
  │  创建 runs 目录 + 注册 mock    │
  └──────────────┬─────────────────┘
                 ▼
  ┌─ intake_node (司南 Sinan) ─────┐   ◄ 不在 graph 中，cli 手动调用
  │  把用户原始输入存进 state      │
  │  写一条进度日志               │
  └──────────────┬─────────────────┘
                 │
                 │  graph.invoke(state)  ─── LangGraph 状态机入口
                 ▼
╔═══════════════════════════════════════════════════════════════════════════╗
║                  【需求层 Brief Layer】（线性，无分支）                      ║
╚═══════════════════════════════════════════════════════════════════════════╝

  ┌────────────────────────────────────────────────────────────────────────┐
  │ ① spec_expansion         Agent: 拓谱 Tuopu                              │
  │   作用：把一句话需求扩成结构化的需求包                                    │
  │                                                                        │
  │   输入：用户的原始自然语言（state.user_raw_input）                        │
  │                                                                        │
  │   输出：requirement_pack.json（需求包），含——                            │
  │     · 一句话用例摘要         · 核心目标                                  │
  │     · 受益方/相关方          · 范围（包含/排除）                          │
  │     · 至少 3 条可验证的成功标准                                          │
  │     · 系统替用户做的隐含假设  · 已知约束（预算/延迟/合规）                 │
  │     · 代理性格（谨慎/大胆…） · 风险承受度（保守/中等/激进）                │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ② spec_challenge         Agent: 诘问 Jiewen                             │
  │   作用：扮演"杠精"，逐条审查需求包，挑出薄弱点                             │
  │                                                                        │
  │   输入：上一步的需求包                                                  │
  │                                                                        │
  │   输出：spec_review.json（需求审查），含——                               │
  │     · 模糊点 + 若不解决会出什么风险                                      │
  │     · 内部冲突的需求对                                                  │
  │     · 用户没说但显然在假设的事                                           │
  │     · 无法客观衡量的目标                                                │
  │     · 没覆盖到的边界场景                                                │
  │     · 挑战分 0–10（越高问题越多）                                        │
  │     · 建议：通过 / 澄清后通过 / 驳回                                     │
  │                                                                        │
  │   副作用：把模糊点登记到 risk_register                                  │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ③ brief_debate           Agent: 辩论协调者 Debate Moderator              │
  │   作用：让拓谱和诘问当面辩一场，对齐分歧、提炼必须问用户的问题             │
  │                                                                        │
  │   输入：需求包 + 需求审查（一起喂给同一个 LLM 演双簧）                    │
  │                                                                        │
  │   输出：brief_debate.json（辩论纪要），含——                              │
  │     · 拓谱的核心立场                                                    │
  │     · 诘问提出的关键质疑                                                │
  │     · 拓谱对每条质疑的回应                                              │
  │     · 双方达成的共识点                                                  │
  │     · 仍未解决的分歧                                                    │
  │     · ★ 必须由用户回答的问题清单（下一步要逐条问）                        │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ④ sinan_debrief          Agent: 司南 Sinan（调用 sinan_interact prompt） │
  │   ★ 用户交互 1                                                  │
  │   作用：司南把辩论结论格式化后展示给用户，逐题收集回答                     │
  │                                                                        │
  │   输入：辩论纪要里的 user_questions（问题清单）                          │
  │                                                                        │
  │   交互流程：                                                            │
  │     · 调用 LLM（sinan_interact prompt）格式化辩论结果                   │
  │     · 司南打印：已对齐点 / 仍存分歧点 / 待回答问题                       │
  │     · 用户每题回答一行，可输入：                                         │
  │         - 直接回答                                                      │
  │         - "skip"  跳过此题（记为 None）                                │
  │         - "done"  提前结束（剩余题全部记为 None）                      │
  │     · 若存在未解决问题或跳过：询问 proceed/abort                         │
  │                                                                        │
  │   输出：                                                               │
  │     · state.user_brief_answers（含每题答案 + 回答状态 + 时间戳）          │
  │                                                                        │
  │   关键变化：不再直接硬编码问题展示，改由 LLM 格式化，                     │
  │             支持多轮追问、优先级排序等智能行为                            │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ⑤ brief_compile          Agent: 契约 Qiyue                              │
  │   作用：把"机器扩展"和"用户回答"合并成一份正式签收的需求表                 │
  │                                                                        │
  │   输入：需求包 + 辩论纪要 + 用户的回答                                   │
  │                                                                        │
  │   输出：user_brief_form.json（最终需求表），含——                         │
  │     · 用户已确认的需求列表                                              │
  │     · 用户明确拒绝的建议                                                │
  │     · 用户额外补的上下文                                                │
  │     · 优先级排序（must / should / nice to have）                        │
  │     · 最终一致同意的约束                                                │
  │     · 签收时间戳 + brief_version=1.0                                    │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       │
╔═══════════════════════════════════════════════════════════════════════════╗
║                【架构层 Architecture Layer — 四步辩论流程】                  ║
╚═══════════════════════════════════════════════════════════════════════════╝
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ⑥ framework_design      Agent: 总工框架师 Zonggong Framework             │
  │   作用：根据需求表，画出 harness 的整体框架结构（初始方案）                │
  │                                                                        │
  │   输入：用户需求表（user_brief_form）                                    │
  │                                                                        │
  │   ┌─ 若是重试轮次（arch_revise 触发），还会收到：───────────────┐       │
  │   │  arch_revision_brief（修复指令），含具体问题 + 修复要求     │       │
  │   └────────────────────────────────────────────────────────────┘       │
  │                                                                        │
  │   输出：framework_design.json（含 version=1.0 或 version=2.0+）         │
  │     · nodes 节点列表         · edges 普通边                             │
  │     · conditional_edges 条件边 · phase_sequence 阶段顺序               │
  │     · entry_point 入口节点     · end_state 终止状态                    │
  │     · design_rationale 设计理念                                         │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ⑦ subagent_review       Agent: 3 名子专家（并行串行调用）                │
  │   作用：3 个子专家各自出本模块详细设计，并对框架进行评审                    │
  │                                                                        │
  │   输入：用户需求表 + 框架设计方案                                        │
  │                                                                        │
  │   ┌─ 每个子专家分两步执行：────────────────────────────────────────┐    │
  │   │  Step 1: 生成自己模块的详细设计                                │    │
  │   │  Step 2: 以专家视角评审整体 framework                          │    │
  │   └────────────────────────────────────────────────────────────────┘    │
  │                                                                        │
  │   子专家配置：                                                          │
  │                                                                        │
  │   记忆师 zonggong_memory                                               │
  │     输出：memory module 详细设计 + framework 评审意见                   │
  │                                                                        │
  │   交接师 zonggong_handoff                                              │
  │     输出：handoff protocol 详细设计 + framework 评审意见                 │
  │                                                                        │
  │   评估师 zonggong_eval                                                 │
  │     输出：eval placements 详细设计 + framework 评审意见                   │
  │                                                                        │
  │   输出（两份）：                                                        │
  │     · subagent_reviews.json  — 3 份评审报告（用于反馈给 framework）      │
  │     · subagent_outputs.json — 3 份模块详细设计（用于总工整合）           │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ⑧ framework_adjust      Agent: 总工框架师 Zonggong Framework             │
  │   作用：框架师根据子专家评审报告，吸收合理意见、拒绝不合理反馈             │
  │                                                                        │
  │   输入：framework 初始方案 + 3 份子代理评审报告                         │
  │                                                                        │
  │   输出：framework_adjustment.json，含——                                 │
  │     · feedback_responses（每条 feedback 的接受/拒绝 + 理由）           │
  │     · adjusted_framework（调整后的完整 framework）                      │
  │     · preserved_elements（决定保留的设计元素）                           │
  │                                                                        │
  │   副作用：state.framework_design 更新为 adjusted_framework（v2）         │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ⑨ zonggong_integrate   Agent: 总工 Zonggong（整合所有子模块输出）         │
  │   作用：总工把 4 份子产出（framework + memory + handoff + eval）         │
  │         合并为一份完整的 Harness 架构包                                 │
  │                                                                        │
  │   输入：                                                                │
  │     · 调整后的 framework                                                │
  │     · 3 份子模块详细设计（memory / handoff / eval）                     │
  │     · 用户需求契约                                                      │
  │     · arch_revision_brief（若是重试轮次）                               │
  │                                                                        │
  │   输出：architecture_pack.json，含——                                    │
  │     · phase_sequence 阶段序列    · approval_gates 审批闸门               │
  │     · failure_recovery 失败恢复   · state_schema 状态摘要                │
  │     · 内存/交接/评估模块设计      · 风险识别                             │
  │     · 考虑过但被拒绝的备选方案及其原因                                    │
  │     · subagent_outputs（保留 3 份原始产出）                            │
  │     · design_trace（设计演进快照：初始 framework / 子代理评审 /          │
  │       framework 调整结果，由系统拼接）                                  │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ⑩ architecture_challenge Agent: 逆审 Nishen                             │
  │   作用：在用户签字前，把架构包按 5 个维度刨一遍，找出毛病                  │
  │                                                                        │
  │   输入：架构包 + 用户需求表                                             │
  │                                                                        │
  │   输出：architecture_review.json（架构审查），含——                       │
  │     · 过度设计警告（比需求复杂的组件）                                   │
  │     · 交接缺口（agent 之间会丢信息的地方）                                │
  │     · 评估缺口（缺哪些质检钩子）                                         │
  │     · 未覆盖的失败模式                                                  │
  │     · 成本/复杂度不匹配的领域                                            │
  │     · 挑战分 0–10                                                      │
  │     · 建议：通过 / 修改后通过 / 驳回                                     │
  │                                                                        │
  │   副作用：把过度设计 + 失败遗漏登记到 risk_register                       │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ⑪ approval_gate          Agent: 守门 Shoumen（★ LLM 判断，非硬编码）     │
  │   作用：汇总架构风险要点，产出风险摘要展示给用户                           │
  │                                                                        │
  │   关键变化：V1 用硬编码规则（挑战分≥4 且 过度设计+失败遗漏非空），         │
  │             V2 改为调用 LLM（shoumen prompt）做综合判断，且不再决策路由   │
  │             ——架构辩论结束后必须进用户审批                                │
  │                                                                        │
  │   输入：逆审结果 + 架构包摘要 + 用户需求                                 │
  │                                                                        │
  │   输出（写入 gate_flags，展示给用户）：                                  │
  │     · risk_level（low / medium / high / critical）— ★ LLM 判断结果     │
  │     · reasoning（判断理由）                                             │
  │     · key_concerns（重点关注项）                                        │
  │     · checklist（逐项检查结果）                                        │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       │ (线性边，必走)
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ⑫ final_spec             Agent: 司南 Sinan（纯整合，不调 LLM）           │
  │   作用：把全程产物压成两份待审稿（先准备好，再交给用户审）                 │
  │                                                                        │
  │   关键变化：V1 / V2 早期把 final_spec 放在 sinan_approval 之后；           │
  │             现在改为之前——让用户在审批时手里已经有完整 md 可看              │
  │                                                                        │
  │   输入：架构包 + 架构审查 + 用户需求表 + framework 演进记录              │
  │                                                                        │
  │   输出（两份，都是待审稿）：                                            │
  │     · harness_design_draft.json — 研发层 AI 消费的结构化契约            │
  │     · harness_design_final.md   ★ 给用户看的完整设计稿，含——            │
  │         一、需求确认（目标 / 范围 / 成功标准）                            │
  │         二、架构设计（图描述 / 状态 schema / 阶段顺序 /                   │
  │                       交接协议 / 审批闸门 / 失败恢复）                    │
  │         三、核心模块设计（记忆模块 / 交接协议 / 评估机制）                 │
  │         四、治理与安全（审批闸门 / 失败恢复策略）                          │
  │         五、设计理念                                                     │
  │         六、审查摘要（子代理评审 + 架构挑战）                              │
  │         七、风险摘要表                                                  │
  │         八、Artifact 版本历史                                           │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       │ (线性边，必走)
                                       ▼
  ┌────────────────────────────────────────────────────────────────────────┐
  │ ⑬ sinan_approval  ★ 用户交互 2                                          │
  │ 司南带着用户分章节过完整 md：需求确认 → 架构设计 → 核心模块 → 治理 →     │
  │ 设计理念 → 审查摘要 → 风险摘要（每节都可暂停），最后收集用户决策。        │
  │                                                                        │
  │ 输入：harness_design_draft（含完整设计）+ gate_flags（守门风险摘要）     │
  │ 输出：state.resume_payload.approval                                     │
  │       = approve / reject / request_changes / abort                     │
  │                                                                        │
  │ 若 reject 或 request_changes：                                          │
  │   arch_reject_count += 1（仅用于展示/审计，不再用作循环上限）           │
  └────────────────────────────────────┬───────────────────────────────────┘
                                       │
                          ┌────────────┼────────────────┐
                          │            │                │
                      approve        abort       reject / request_changes
                          │            │                │
                          │            │                │
                   ┌──────▼─────┐ ┌────▼─────────┐ ┌────▼────────────┐
                   │ END         │ │ END           │ │ arch_revise     │
                   │ (final_spec│ │ (用户中止；   │ │ （生成修复指令） │
                   │ 已运行过)   │ │ 设计稿留盘）  │ │                  │
                   └─────────────┘ └───────────────┘ └────┬────────────┘
                                                          │
                                                  回到 ⑥ framework_design
                                                  （重走辩论 → 重生 final_spec
                                                  → 重审；用户可一直 reject
                                                  直到显式 approve 或 abort）
                                       │
                                       ▼
                                  [ 设计层结束 ]
                                       │
                                       ▼
╔═══════════════════════════════════════════════════════════════════════════╗
║                       【研发层 Coding Layer — GAN 式迭代】                  ║
╚═══════════════════════════════════════════════════════════════════════════╝
  输入：harness_design_draft.json（设计层产出）
  注：下图 planner / sprint_plan / sprint_negotiate / sprint_setup / implement_feature /
      evaluator_qa / generator_fix 这 7 个节点是 tool-use agent（执行模型见本层末尾）；
      其余 init_* / read_* / sanity_check / test_feature / commit_feature / bug_triage /
      sprint_complete 是确定性逻辑或真 runner，不调 LLM、不经 agent seam。

  ┌────────────────────────────────────────────────────────────────────────┐
  │  ┌─────────────────────────────────────────────────────────────────┐  │
  │  │                    外层：Sprint Loop（≤10 轮）                  │  │
  │  │                                                                 │  │
  │  │  planner ──► sprint_plan ──► sprint_negotiate ──► sprint_setup │  │
  │  │              （最多 3 轮谈判）                                   │  │
  │  └──────────────────────────┬──────────────────────────────────────┘  │
  │                             ▼                                         │
  │  ┌─────────────────────────────────────────────────────────────────┐  │
  │  │                  中层：Session Loop（每次重置上下文）              │  │
  │  │                                                                 │  │
  │  │  session_init ──► session_setup ──► sanity_check               │  │
  │  │                                       │                           │  │
  │  │                   ┌───────────────────┴────────┐                 │  │
  │  │                   ▼                            ▼                 │  │
  │  │             [pass]                      [fail]                   │  │
  │  │               │                            │                     │  │
  │  │               ▼                            ▼                     │  │
  │  │  ┌───────────────────────────────────────────────────────┐     │  │
  │  │  │              内层：Feature Loop（按优先级）              │     │  │
  │  │  │                                                       │     │  │
  │  │  │  pick_feature ──► implement_feature                   │     │  │
  │  │  │                      │                                 │     │  │
  │  │  │                      ▼                                 │     │  │
  │  │  │               test_feature                            │     │  │
  │  │  │               │       │                              │     │  │
  │  │  │          [pass]│      [fail]                          │     │  │
  │  │  │               │       │                               │     │  │
  │  │  │               ▼       └──────────────────┐            │     │  │
  │  │  │         commit_feature ──► [更多?◄──────┘            │     │  │
  │  │  │               │                                   │     │  │
  │  │  │          [完成全部 feature?]                         │     │  │
  │  │  │               │                                    │     │  │
  │  │  │               ▼                                    │     │  │
  │  │  │        evaluator_qa                            │     │  │
  │  │  │               │                                    │     │  │
  │  │  └───────────────┼────────────────────────────────────┘     │  │
  │  │                  ▼                                              │  │
  │  │  ┌─────────────────────────────────────────────────────────┐  │  │
  │  │  │              QA Loop（Fix Loop，≤2 轮自修复）            │  │  │
  │  │  │                                                         │  │  │
  │  │  │  evaluator_qa ──► [pass] ──► sprint_complete           │  │  │
  │  │  │          │                                              │  │  │
  │  │  │          ▼ [fail]                                      │  │  │
  │  │  │  evaluator_bugs ──► generator_fix ──► [自测?] ──┘     │  │  │
  │  │  │                                 │                       │  │  │
  │  │  │                            [修复成功?]                  │  │  │
  │  │  │                                 │                       │  │  │
  │  │  │                              [继续/强退]                 │  │  │
  │  │  └─────────────────────────────────────────────────────────┘  │  │
  │  │                  │                                              │  │
  │  │                  ▼                                              │  │
  │  │           sprint_complete ──► [spec 完成?]                    │  │
  │  │                               │  是 → END                      │  │
  │  │                               │  否 → 新一轮 sprint            │  │
  │  └───────────────────────────────────────────────────────────────────┘  │
  └────────────────────────────────────────────────────────────────────────┘
                                       ▼
  ───────────────────────────────────────────────────────────────────────────
   〔研发层 续〕节点执行模型 —— 上面这 7 个 LLM 节点不是普通函数，是 tool-use agent
  ───────────────────────────────────────────────────────────────────────────

调用一个 LLM 节点 = 拉起一个真 agent，让它在 harness/ 里自己用工具干活，干完只交回一份 JSON
（不再"单轮补全 + 手工 write_text"；seam = src/sinan/agent.py）

   node ─► get_agent_runner()
              ├─[有 ANTHROPIC_API_KEY 或 BACKEND=real]─► RealAgentRunner
              │       └─► claude_agent_sdk.query() ─► 子进程拉起 claude CLI（真工具调用）
              └─[否则 / BACKEND=mock]──────────────────► MockAgentRunner（离线·pytest 全程走这条）
                     │
                     ▼
   ┌── agent 自主循环（≤ max_turns=40 轮）： 思考 ─► 调工具 ─► 读结果 ─► 再思考 …
   │      工具 = Read / Write / Edit / Bash / Glob / Grep （按节点收敛，见下表）
   │      每次工具调用先过 PreToolUse hook（沙箱闸门）：
   │         ├─ Write/Edit 越出 harness/ 或写 init.sh     ─► deny
   │         ├─ Bash 命中 denylist (rm -rf / sudo / dd …)  ─► deny
   │         └─ 其余                                       ─► allow
   └── 迭代到产出最终 JSON
                     │
                     ▼
   ResultMessage.structured_output ─► node ─► validate_artifact ─► 写盘

  〔配置〕options = ClaudeAgentOptions(system_prompt=<角色>, cwd=harness/,
        allowed_tools=<按节点收敛>, permission_mode="dontAsk", setting_sources=[],
        max_turns=40, hooks={PreToolUse:[safe_hook]}, output_format=<该 artifact 的 schema>)

  〔工具集〕allowed_tools 按节点收敛（dontAsk 强制：清单外的工具直接被 deny）
        implement_feature / generator_fix          ─► Read Write Edit Bash Glob Grep   写码+跑测试
        evaluator_qa                               ─► Read Glob Grep（只读）           judge 独立
        planner / sprint_plan / negotiate / setup  ─► （空·零工具）                    纯结构化输出

  〔安全边界〕3 层防护 + 1 个已知缺口
        ① cwd=harness/        agent 的根目录
        ② dontAsk 白名单      清单外工具 → deny（∴ 只读/零工具节点真起不了 Bash）
        ③ PreToolUse hook     Write/Edit 越界或写 init.sh → deny ； Bash 命中 denylist → deny
        ⚠ 缺口  开 Bash 的 2 节点，shell 重定向 echo>/abs 仍能逃逸（命令字符串过滤不完备）
                ─► 硬隔离不在代码层，靠部署期「每任务一个容器」；本地可信运行接受残余风险

  〔后端选择〕RealAgentRunner（需 claude CLI 已装并认证）/ MockAgentRunner（离线·复刻文件副作用）
  〔确定性上限〕sprint≤10 / negotiate≤3 / fix≤2 / feature_retry≤2 / sanity_retry≤2 焊死在 graph.py
        router；max_turns=40 只是单次 agent 的防失控天花板，不表达循环轮次

                                       ▼
                                    [ 研发层结束 ]


╔═══════════════════════════════════════════════════════════════════════════╗
║                       【横切关注点 Cross-cutting】                          ║
╚═══════════════════════════════════════════════════════════════════════════╝

每个节点都会做的"通用动作"（artifacts.py 提供）：
  ① 更新 run_state.yaml  —— 记录进入了哪个阶段
  ② 写 progress_log.md   —— 一行一条的人类可读时间线
  ③ 写 decision_log.md   —— 关键决策的来龙去脉
  ④ 写当步产物 json/yaml/md
  ⑤ 把当前阶段标 completed

LLM 后端怎么选：
  · 设计层（单轮补全，llm.py get_llm_client）：
      有 ANTHROPIC_API_KEY → Anthropic；有 OPENAI_API_KEY → OpenAI；都没有 → MockLLMClient
  · 研发层 7 个 LLM 节点（真 agent，agent.py get_agent_runner）：
      SINAN_AGENT_BACKEND=real 或有 ANTHROPIC_API_KEY → RealAgentRunner（需 claude CLI）；
      否则 → MockAgentRunner（离线）。详见上面研发层〔节点执行模型〕。

JSON 解析与校验（parse_and_validate_artifact，全流程共用）：
  先剥掉 ```fence```，再 json.loads，然后按 _REQUIRED_FIELDS 做字段校验；
  解析失败或字段缺失时**显式抛 ValueError**——由调用方 try/except 或让
  上层感知，不做静默兜底。

★ 用户交互一共 3 处：
  ⓿ 提交原始需求（cli 启动时）
  ❶ 回答辩论问题（sinan_debrief，多轮 input）
     注：agent 工作方式（每节点工具集、max_turns=40 上限）不是用户配置项，
        而是按节点固定在代码里（见研发层〔节点执行模型〕），需求层不收集这些偏好。
  ❷ 审批架构（sinan_approval，四选一：approve / reject / request_changes / abort）

★ 死循环保险丝：
  架构层：拒绝循环没有数量上限，由用户在 sinan_approval 选 approve 或 abort
          显式终止。abort 不进研发层，设计稿留盘；可后续 --from-design 接力。
  研发层：sprint_number > 10（即第 10 个 sprint 完成后）→ 强制抛错停止。

★ 设计层 Agent 角色一览：
  ┌─────────────┬──────────────────┬──────────────────────────────────┐
  │  Agent 名称 │  角色定位          │  prompt key                      │
  ├─────────────┼──────────────────┼──────────────────────────────────┤
  │  拓谱 Tuopu │  需求扩展          │  tuopu                           │
  │  诘问 Jiewen│  需求审查          │  jiewen                          │
  │  辩论 Moderator│ 辩论协调        │  brief_debate                   │
  │  司南 Sinan │  用户交互整合      │  sinan_interact                  │
  │  契约 Qiyue │  需求编译          │  qiyue                           │
  │  框架师     │  总工框架设计      │  zonggong_framework             │
  │  记忆师     │  记忆模块设计      │  zonggong_memory                 │
  │  交接师     │  交接协议设计      │  zonggong_handoff                │
  │  评估师     │  评估机制设计      │  zonggong_eval                   │
  │  逆审 Nishen│  架构审查          │  nishen                          │
  │  守门 Shoumen│  风险守门（LLM）  │  shoumen                         │
  └─────────────┴──────────────────┴──────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════════
                       【V1 → V2 核心变化总结】
═══════════════════════════════════════════════════════════════════════════════

1. 用户交互层重构
   V1: wait_brief（硬编码展示） / wait_approval（硬编码展示）
   V2: sinan_debrief（LLM 格式化）/ sinan_approval（LLM 格式化）
   - wait_brief.py、wait_approval.py、sinan_interact.py 均已删除
   - sinan_debrief.py 和 sinan_approval.py 替代

2. 架构辩论流程（最重要变化）
   V1: architecture_draft（总工含 4 子专家，一次性出完整架构）
   V2: 四步辩论流程
     ⑥ framework_design → ⑦ subagent_review → ⑧ framework_adjust → ⑨ zonggong_integrate
   - 框架、子专家、调整、总工整合四步分离
   - 子专家不再只做评审，同时输出自己模块的详细设计
   - framework 经评审和调整后才进入整合

3. 守门判断 LLM 化
   V1: approval_gate（硬编码规则：挑战分≥4 且 过度设计+失败遗漏非空）
   V2: approval_gate（LLM + shoumen prompt 做综合风险判断）

4. 拒绝回环增加 arch_revise 中间步骤
   V1: wait_approval 拒绝 → 回到 architecture_draft（直接重试）
   V2: sinan_approval 拒绝 → arch_revise（生成修复指令）→ framework_design
   - arch_revise_node 生成 arch_revision_brief，包含具体问题 + 修复指令
   - framework_design 收到修复指令，针对性修改
   - 总工整合时可看到完整的 design_trace（旧名 design_evolution，已重命名）

5. 产物增强
   - final_spec 生成 harness_design_final.md 时附带「Artifact 版本历史」段（write_json 之后再读取，包含本次写入版本）
   - framework_design 带版本号（v1 / v2+）
   - architecture_pack 保留完整 design_trace（初始方案→评审→调整→整合）
   - user_brief_answers 增加回答状态（answered/skipped）和时间戳

6. 代码清理
   - 删除：wait_brief.py、wait_approval.py、sinan_interact.py、architecture_draft.py
   - 合并到：sinan_debrief.py、sinan_approval.py、framework_design.py、arch_revise.py
```
