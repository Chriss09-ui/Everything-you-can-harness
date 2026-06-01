"""Mock LLM response registration — loaded at startup for V1 testing."""
from __future__ import annotations
import json
from .llm import MockLLMClient


def register_mock_responses() -> None:
    """Register all mock responses for the V1 pipeline."""

    # 拓谱 (Spec Expander) — triggered by "Requirement Pack"
    MockLLMClient.register("Requirement Pack", json.dumps({
        "use_case_summary": "一个帮助用户从自然语言需求构建 agentic harness 设计的系统",
        "primary_goal": "将模糊的用户意图转化为结构化、可执行的 harness 架构设计",
        "stakeholders": ["开发者", "技术负责人", "产品经理"],
        "scope_inclusions": [
            "需求分析与扩展",
            "需求审查与质疑",
            "架构设计",
            "架构反审",
            "用户审批",
            "最终设计稿输出"
        ],
        "scope_exclusions": [
            "自动代码生成",
            "自动部署",
            "长期记忆存储",
            "真实沙箱执行"
        ],
        "success_criteria": [
            "用户输入一段自然语言后，系统能产出完整的 Requirement Pack",
            "系统能自动识别需求中的模糊点和冲突",
            "最终输出包含完整的架构设计和风险评估"
        ],
        "assumptions": [
            "用户具备基本的 agentic 系统概念",
            "用户愿意在关键节点参与审批",
            "LLM 的推理能力足以支撑需求分析和架构设计"
        ],
        "known_constraints": [
            "V1 仅支持设计阶段，不含构建",
            "需要 API key 才能使用真实 LLM",
            "所有数据存储在本地文件系统"
        ],
        "persona_qualities": ["谨慎", "结构化", "工程导向"],
        "risk_tolerance": "conservative"
    }, ensure_ascii=False))

    # 诘问 (Spec Challenger) — triggered by "批判性审查"
    MockLLMClient.register("批判性审查", json.dumps({
        "ambiguities": [
            {
                "item": "用户'基本的 agentic 系统概念'的定义不明确",
                "risk_if_unaddressed": "可能导致系统对初级用户不友好"
            },
            {
                "item": "'完整的架构设计'的完整性标准未定义",
                "risk_if_unaddressed": "无法客观验收产出物质量"
            }
        ],
        "conflicts": [],
        "hidden_assumptions": [
            "假设用户有耐心完成多轮审批",
            "假设 LLM 输出的 JSON 总是可解析的"
        ],
        "unverifiable_goals": [
            "'足以支撑需求分析'缺少量化标准"
        ],
        "edge_cases": [
            "用户输入极短（如一个词）",
            "用户输入包含相互矛盾的需求",
            "LLM 返回非 JSON 格式响应"
        ],
        "challenge_score": 4,
        "recommendation": "clarify_then_pass"
    }, ensure_ascii=False))

    # 契约 (Brief Compiler)
    MockLLMClient.register("生成最终 User Brief Form", json.dumps({
        "confirmed_requirements": [
            "需求分析与扩展功能",
            "需求审查与质疑功能",
            "架构设计功能",
            "用户审批闸门"
        ],
        "rejected_suggestions": [],
        "supplementary_notes": "用户确认接受 V1 仅做设计不做构建的限制",
        "priority_order": [
            {"requirement": "需求扩展", "priority": "must_have"},
            {"requirement": "架构设计", "priority": "must_have"},
            {"requirement": "需求审查", "priority": "should_have"},
            {"requirement": "架构反审", "priority": "should_have"}
        ],
        "constraints_final": [
            "V1 仅设计阶段",
            "本地文件存储",
            "CLI 交互"
        ],
        "sign_off_timestamp": "2026-04-24T00:00:00Z",
        "brief_version": "1.0"
    }, ensure_ascii=False))

    # 总工整合 (Architect)
    MockLLMClient.register("请整合以上所有输出，生成完整的 Harness 架构包", json.dumps({
        "graph_description": "线性状态机: INTAKE → SPEC_EXPANSION → SPEC_CHALLENGE → BRIEF_DEBATE → SINAN_DEBRIEF → BRIEF_COMPILE → FRAMEWORK_DESIGN → ARCHITECTURE_CHALLENGE → APPROVAL_GATE → FINAL_SPEC。需求层固定串行，架构层含条件分支。",
        "state_schema_summary": {
            "run_id": "str",
            "current_phase": "str",
            "requirement_pack": "dict",
            "spec_review": "dict",
            "brief_debate": "dict",
            "user_brief_form": "dict",
            "architecture_pack": "dict",
            "architecture_review": "dict",
            "harness_design_draft": "dict",
            "gate_flags": "dict",
            "arch_reject_count": "int",
            "risk_register": "list",
            "messages": "list"
        },
        "phase_sequence": [
            "INTAKE",
            "SPEC_EXPANSION",
            "SPEC_CHALLENGE",
            "BRIEF_DEBATE",
            "SINAN_DEBRIEF",
            "BRIEF_COMPILE",
            "FRAMEWORK_DESIGN",
            "ARCHITECTURE_CHALLENGE",
            "APPROVAL_GATE",
            "SINAN_APPROVAL",
            "FINAL_SPEC"
        ],
        "memory_module": {
            "working_memory": "当前任务上下文存储在 state 中，每个节点通过 state dict 传递",
            "project_memory": "所有 artifact 写入 runs/{run_id}/ 目录，作为项目级持久化",
            "long_term_memory": "V1 暂不实现，通过用户审批时的上下文继承实现信息复用",
            "memory_handoffs": "每个节点退出时，书记写入磁盘；下一节点读取磁盘+state",
            "storage_backends": "文件系统（JSON/YAML/MD），无数据库依赖",
            "retention_policy": "runs/ 目录保留最近 10 次运行，旧运行可手动清理"
        },
        "handoff_protocol": {
            "handoff_points": ["spec_expansion→spec_challenge", "spec_challenge→brief_debate", "brief_debate→sinan_debrief", "brief_compile→framework_design", "final_spec→planner"],
            "context_included": ["requirement_pack", "spec_review", "brief_debate", "user_brief_form", "architecture_pack", "architecture_review", "harness_design_draft"],
            "state_transfer": "热路径通过 LangGraph state，持久边界通过 runs/{run_id}/ 下的 JSON artifact",
            "error_recovery": "节点失败时保留已写 artifact，允许从设计稿恢复研发层",
            "versioning": "可迭代 artifact 使用 versioned JSON 写入"
        },
        "eval_placements": {
            "eval_triggers": ["spec_challenge 完成时", "architecture_challenge 完成时", "用户审批前", "研发层 QA 时"],
            "eval_criteria": ["需求完整性", "架构合理性", "风险可接受性", "实现可运行性"],
            "eval_frequency": "每个 Gate 点各评估一次",
            "eval_outputs": "challenge_score / risk_level / evaluator_grade",
            "quality_gates": "低风险自动通过，高风险进入用户审批",
            "user_notification": "当 risk_level != low 时通知用户"
        },
        "approval_gates": ["SINAN_DEBRIEF", "APPROVAL_GATE"],
        "failure_recovery": "架构拒绝最多 3 次，超过后强制停止并输出已有产物。LLM 调用有超时保护和重试机制。",
        "risks_identified": [
            "LLM 输出不稳定可能导致 JSON 解析失败",
            "用户可能在审批环节放弃，导致流程挂起",
            "多子 agent 并行调用增加 Token 消耗"
        ],
        "alternative_options": [
            {
                "option": "子 agent 串行执行",
                "rejected_reason": "串行执行增加延迟，且后执行的子 agent 无法利用前面 agent 的洞察"
            }
        ],
        "subagent_outputs": {
            "framework": {
                "nodes": ["intake", "spec_expansion", "spec_challenge", "brief_debate", "sinan_debrief", "brief_compile", "framework_design", "architecture_challenge", "approval_gate", "sinan_approval", "final_spec"],
                "edges": [["spec_expansion", "spec_challenge"], ["spec_challenge", "brief_debate"], ["brief_debate", "sinan_debrief"], ["sinan_debrief", "brief_compile"], ["brief_compile", "framework_design"], ["framework_design", "architecture_challenge"], ["architecture_challenge", "approval_gate"]],
                "conditional_edges": [["approval_gate", "sinan_approval"], ["approval_gate", "final_spec"], ["sinan_approval", "framework_design"], ["sinan_approval", "final_spec"]],
                "entry_point": "spec_expansion",
                "end_state": "FINAL_SPEC"
            },
            "memory_module": {
                "working_memory": "当前任务上下文存储在 state 中，每个节点通过 state dict 传递",
                "project_memory": "所有 artifact 写入 runs/{run_id}/ 目录，作为项目级持久化",
                "long_term_memory": "V1 暂不实现，通过用户审批时的上下文继承实现信息复用",
                "memory_handoffs": "每个节点退出时，书记写入磁盘；下一节点读取磁盘+state",
                "storage_backends": "文件系统（JSON/YAML/MD），无数据库依赖",
                "retention_policy": "runs/ 目录保留最近 10 次运行，旧运行可手动清理"
            },
            "handoff_protocol": {
                "handoff_points": ["spec_expansion→spec_challenge", "spec_challenge→brief_debate", "brief_debate→sinan_debrief", "brief_compile→framework_design", "framework_design→architecture_challenge", "architecture_challenge→approval_gate"],
                "context_included": ["requirement_pack", "spec_review", "brief_debate", "user_brief_form", "architecture_pack", "architecture_review"],
                "state_transfer": "通过 LangGraph state dict 传递，节点返回更新后的 state dict",
                "error_recovery": "节点失败时重试一次，仍失败则记录错误并输出已有产物",
                "versioning": "每个 artifact 有版本号，写入 artifact_versions"
            },
            "eval_placements": {
                "eval_triggers": ["spec_challenge 完成时", "architecture_challenge 完成时", "用户审批前"],
                "eval_criteria": ["需求完整性", "架构合理性", "风险可接受性"],
                "eval_frequency": "每个 Gate 点各评估一次",
                "eval_outputs": "challenge_score (0-10) + recommendation",
                "quality_gates": "challenge_score <= 3 为通过，否则需要人工介入",
                "user_notification": "当 challenge_score > 3 时通知用户"
            }
        }
    }, ensure_ascii=False))

    # 框架设计师子 agent — Round 1 (initial framework generation)
    MockLLMClient.register("【第一轮】请设计 harness 的整体框架结构", json.dumps({
        "nodes": [
            {"name": "spec_expansion", "role": "扩展需求"},
            {"name": "spec_challenge", "role": "质疑需求"},
            {"name": "brief_compile", "role": "定稿需求契约"},
            {"name": "framework_design", "role": "设计 harness 框架"},
            {"name": "architecture_challenge", "role": "逆审架构"},
            {"name": "approval_gate", "role": "风险分级"},
            {"name": "final_spec", "role": "编译研发层设计稿"}
        ],
        "edges": [
            {"from": "spec_expansion", "to": "spec_challenge"},
            {"from": "spec_challenge", "to": "brief_debate"},
            {"from": "brief_compile", "to": "framework_design"},
            {"from": "framework_design", "to": "architecture_challenge"},
            {"from": "architecture_challenge", "to": "approval_gate"}
        ],
        "conditional_edges": [
            {"condition": "risk_level == low", "routes": "approval_gate -> final_spec"},
            {"condition": "risk_level != low", "routes": "approval_gate -> sinan_approval"}
        ],
        "phase_sequence": ["需求契约", "架构设计", "架构逆审", "风险审批", "最终设计稿"],
        "entry_point": "spec_expansion",
        "end_state": "FINAL_SPEC",
        "design_rationale": "先把需求固化为文件契约，再让架构层和研发层只消费明确 artifact。"
    }, ensure_ascii=False))

    # 框架设计师子 agent — Revision round. Triggered when ``framework_design``
    # was re-entered from ``arch_revise → framework_design`` (rather than the
    # linear first-run path). The user-prompt suffix in that case is
    # ``"请按上述修复指令调整 framework..."`` — distinct from the Round-1
    # ``"【第一轮】请设计..."`` suffix. The shape is the same as Round 1 but
    # the content reflects an edited framework (a couple of role strings are
    # adjusted so a test can tell by inspection which path produced it).
    MockLLMClient.register("请按上述修复指令调整 framework", json.dumps({
        "nodes": [
            {"name": "spec_expansion", "role": "扩展需求"},
            {"name": "spec_challenge", "role": "质疑需求"},
            {"name": "brief_compile", "role": "定稿需求契约"},
            {"name": "framework_design", "role": "设计 harness 框架（已修订）"},
            {"name": "architecture_challenge", "role": "逆审架构"},
            {"name": "approval_gate", "role": "风险分级"},
            {"name": "final_spec", "role": "编译研发层设计稿"}
        ],
        "edges": [
            {"from": "spec_expansion", "to": "spec_challenge"},
            {"from": "spec_challenge", "to": "brief_debate"},
            {"from": "brief_compile", "to": "framework_design"},
            {"from": "framework_design", "to": "architecture_challenge"},
            {"from": "architecture_challenge", "to": "approval_gate"}
        ],
        "conditional_edges": [
            {"condition": "risk_level == low", "routes": "approval_gate -> final_spec"},
            {"condition": "risk_level != low", "routes": "approval_gate -> sinan_approval"}
        ],
        "phase_sequence": ["需求契约", "架构设计", "架构逆审", "风险审批", "最终设计稿"],
        "entry_point": "spec_expansion",
        "end_state": "FINAL_SPEC",
        "design_rationale": "按 arch_revision_brief 调整后保留契约化交接主结构。"
    }, ensure_ascii=False))

    # 记忆模块设计师子 agent
    MockLLMClient.register("你是记忆模块设计师", json.dumps({
        "working_memory": "当前任务上下文存储在 state 中，每个节点通过 state dict 传递",
        "project_memory": "所有 artifact 写入 runs/{run_id}/ 目录，作为项目级持久化",
        "long_term_memory": "V1 暂不实现，通过用户审批时的上下文继承实现信息复用",
        "memory_handoffs": "每个节点退出时，书记写入磁盘；下一节点读取磁盘+state",
        "storage_backends": "文件系统（JSON/YAML/MD），无数据库依赖",
        "retention_policy": "runs/ 目录保留最近 10 次运行，旧运行可手动清理"
    }, ensure_ascii=False))

    # 交接协议设计师子 agent
    MockLLMClient.register("你是交接协议设计师", json.dumps({
        "handoff_points": ["spec_expansion→spec_challenge", "spec_challenge→brief_debate", "brief_debate→sinan_debrief", "brief_compile→framework_design", "framework_design→architecture_challenge", "architecture_challenge→approval_gate"],
        "context_included": ["requirement_pack", "spec_review", "brief_debate", "user_brief_form", "architecture_pack", "architecture_review"],
        "state_transfer": "通过 LangGraph state dict 传递，节点返回更新后的 state dict",
        "error_recovery": "节点失败时重试一次，仍失败则记录错误并输出已有产物",
        "versioning": "每个 artifact 有版本号，写入 artifact_versions"
    }, ensure_ascii=False))

    # 评估专家子 agent
    MockLLMClient.register("你是评估专家", json.dumps({
        "eval_triggers": ["spec_challenge 完成时", "architecture_challenge 完成时", "用户审批前"],
        "eval_criteria": ["需求完整性", "架构合理性", "风险可接受性"],
        "eval_frequency": "每个 Gate 点各评估一次",
        "eval_outputs": "challenge_score (0-10) + recommendation",
        "quality_gates": "challenge_score <= 3 为通过，否则需要人工介入",
        "user_notification": "当 challenge_score > 3 时通知用户"
    }, ensure_ascii=False))

    # 框架调整 (Framework Adjuster) — triggered by "逐条回应并调整 framework"
    MockLLMClient.register("逐条回应并调整 framework", json.dumps({
        "adjusted_framework": {
            "nodes": [
                {"name": "spec_expansion", "role": "扩展需求"},
                {"name": "spec_challenge", "role": "质疑需求"},
                {"name": "brief_compile", "role": "定稿需求契约"},
                {"name": "framework_design", "role": "设计 harness 框架"},
                {"name": "architecture_challenge", "role": "逆审架构"},
                {"name": "approval_gate", "role": "风险分级"},
                {"name": "final_spec", "role": "编译研发层设计稿"},
            ],
            "edges": [
                {"from": "spec_expansion", "to": "spec_challenge"},
                {"from": "framework_design", "to": "architecture_challenge"},
                {"from": "architecture_challenge", "to": "approval_gate"},
            ],
            "conditional_edges": [
                {"condition": "risk_level == low", "routes": "approval_gate -> final_spec"},
            ],
            "phase_sequence": ["需求契约", "架构设计", "架构逆审", "风险审批", "最终设计稿"],
            "entry_point": "spec_expansion",
            "end_state": "FINAL_SPEC",
            "design_rationale": "保留契约化交接，按子代理评审意见微调。",
        },
        "feedback_responses": [
            {"feedback": "需要更明确的 fallback 协议", "response": "accepted",
             "rationale": "已在 design_rationale 中强调"}
        ],
        "preserved_elements": ["契约化交接", "四步辩论结构"],
    }, ensure_ascii=False))

    # 逆审修订简报 (Arch Reviser) — triggered by the actual user-prompt suffix
    # ``arch_revise_node`` sends to the LLM (matches the prompt regardless of
    # which ``arch_revise`` prompt template is in use, so long as the suffix
    # matches the code path).
    MockLLMClient.register("翻译为具体的修复指令", json.dumps({
        "revision_summary": "缩小过度设计、补全 handoff 缺口",
        "specific_issues": [
            {
                "issue": "sinan_debrief 缺少用户输入格式校验",
                "in_previous_design": "无校验逻辑",
                "fix_instruction": "为 sinan_debrief 增加用户输入格式校验"
            },
            {
                "issue": "LLM 调用无超时保护",
                "in_previous_design": "所有 LLM 调用直接 await",
                "fix_instruction": "为 LLM 调用增加超时保护"
            },
        ],
        "preserve_points": ["契约化交接", "四步辩论结构"],
    }, ensure_ascii=False))

    # 子代理评审报告 — all three review calls can share this shape in mock mode.
    MockLLMClient.register("评审当前 framework 设计", json.dumps({
        "agent_name": "mock_reviewer",
        "agent_role": "子代理评审者",
        "incompatibilities": [],
        "missing_elements": [],
        "endorsed_elements": [
            {
                "element": "artifact-based handoff",
                "reason": "跨节点交接有可审计的文件边界"
            }
        ],
        "summary": "当前 framework 与模块设计兼容"
    }, ensure_ascii=False))

    # 逆审 (Architecture Challenger) — triggered by "批判性审查以上架构"
    MockLLMClient.register("批判性审查以上架构", json.dumps({
        "over_engineering_flags": [
            "risk_register 在 V1 中可能过早引入，V1 流程较简单"
        ],
        "handoff_gaps": [
            "sinan_debrief 节点的用户输入未做格式验证"
        ],
        "eval_gaps": [
            "缺少对 LLM 输出质量的自动评估机制"
        ],
        "failure_mode_omissions": [
            "未处理 LLM 调用超时的场景",
            "未处理用户在审批环节长时间无响应的情况"
        ],
        "cost_complexity_concerns": [
            "每个阶段都调用 LLM 的成本在高频使用时可能较高"
        ],
        "challenge_score": 3,
        "recommendation": "pass"
    }, ensure_ascii=False))

    # 辩论协调者 (Brief Debate) — triggered by "请主持辩论"
    MockLLMClient.register("请主持辩论", json.dumps({
        "tuopu_position": "司南系统需要覆盖需求层（扩展+审查）和架构层（设计+反审），以多阶段确保需求质量",
        "jiewen_challenges": [
            "V1 阶段过多可能导致用户疲劳，影响参与意愿",
            "辩论阶段是否有必要存在，还是直接问用户更高效？",
            "LLM 每次输出的 JSON 格式不稳定，可能导致解析失败"
        ],
        "tuopu_responses": [
            "多阶段是必要的，每个阶段都有明确的价值交付",
            "辩论是拓谱和诘问对齐的核心机制，不可跳过",
            "JSON 解析有容错机制，解析失败会记录 raw 内容"
        ],
        "aligned_points": [
            "司南系统采用线性多阶段工作流",
            "每个阶段必须有明确的输入、输出和验收标准",
            "重大决策必须经过人工审批",
            "所有 artifact 必须写入磁盘"
        ],
        "remaining_disagreements": [
            "辩论阶段是否需要第二轮对抗",
            "LLM 调用是否需要添加超时保护"
        ],
        "user_questions": [
            "你的系统预期每日处理多少个需求任务？",
            "用户审批时，你希望看到多详细的架构描述？",
            "系统失败时，你希望收到什么样的告警通知？",
            "你对 V1 的交付周期有明确的时间要求吗？"
        ]
    }, ensure_ascii=False))

    # 司南 (交互) — sinan_debrief_node 用，按 sinan_interact prompt 输出 display 包装。
    # 保持 4 个 user_questions + 0 个 remaining_disagreements：这样 unresolved_risks=False，
    # 走 "全部回答、直接进 brief_compile" 的 happy path，避免触发 proceed/abort 二次确认。
    MockLLMClient.register("你是司南（Sinan），司南系统的首席交互官", json.dumps({
        "display": {
            "header": "辩论已完成，请您填写以下信息",
            "question_instruction": "请逐条回答（输入 'skip' 跳过，'done' 结束）：",
            "aligned_points": [
                "系统采用多阶段协作工作流",
                "所有 artifact 写入磁盘作为交接契约",
            ],
            "remaining_disagreements": [],
            "user_questions": [
                "你的系统每日预期处理多少任务？",
                "用户审批时希望看到多详细的架构描述？",
                "系统失败时希望收到什么告警通知？",
                "对 V1 的交付周期有明确的时间要求吗？",
            ],
        }
    }, ensure_ascii=False))
