# 研发层流程图 v2.0

Generated from: Anthropic "Effective Harnesses" + "Harness Design Long-Running Apps"
Incorporating: P0/P1/P2/P3 adjustments

```mermaid
flowchart TB
    subgraph INIT["初始阶段"]
        A([用户输入一句需求])
        B[Planner 生成完整产品 Spec]
        A --> B
    end

    subgraph SPRINT_LOOP["Sprint 迭代循环"]
        direction TB

        subgraph SPRINT_NEGOTIATE["Sprint N: 目标协商"]
            C1["Generator 提出本轮 Sprint 目标\n（含优先级和依赖声明）"]
            C2["Evaluator 审核目标定义\n（是否清晰、可验证、无遗漏）"]
            C3{双方是否达成一致?}
            C1 --> C2 --> C3

            C3 -->|否| C1
            C3 -->|是| D1
        end

        subgraph PLANNING["执行规划"]
            D1["Generator 宣读本轮执行方案\n（对接协商结果）"]
            D2[开始任务]
            D1 --> D2
        end

        subgraph INIT_PHASE["环境初始化\n仅 Sprint 1 执行"]
            E1["Initializer Agent\n初始化环境"]
            E2a["生成 claude-progress.txt"]
            E2b["生成 init.sh 启动脚本"]
            E2c["生成 feature_list.json\n（含 priority + depends_on 字段）"]
            E2d["git init"]
            E1 --> E2a
            E1 --> E2b
            E1 --> E2c
            E1 --> E2d
            D2 --> E1
        end

        subgraph SUBSEQ_INIT["后续 Sprint 检查"]
            E1b{"Spec 是否变更?"}
            E2e["更新 feature_list.json"]
            E2f["如有依赖变更，更新 init.sh"]
            E2g["继承现有 git 仓库"]
            D2 --> E1b
            E1b -->|是| E2e
            E2e --> E2f
            E2f --> E2g
            E1b -->|否| E2g
        end

        subgraph SESSION_LOOP["Session 循环"]
            direction TB

            F1["新一轮 Session 开始"]
            F2{"Sprint > 1\n且 Spec 未变?"}
            F3["读取 claude-progress.txt\n查看已完成的 features"]
            F3b["读取 git log\n确认上一次 commit"]
            F1 --> F2
            F2 -->|是| F3
            F2 -->|否| F3b
            F3b --> F3
            F3 --> F4
            F3 --> F3b

            F4["运行 init.sh 启动项目"]
            F5["执行基础 E2E 回归测试"]
            F4 --> F5

            F6{基础测试是否正常?}
            F5 --> F6

            F6 -->|否| FIX_OUTER["Bug 修复阶段"]
            FIX_OUTER --> FIXR{"修复后\n是否引入新问题?"}
            FIXR -->|否| F5
            FIXR -->|是| REVERT["检查 git diff"]
            REVERT --> REV_CHOICE{"可 revert?"}
            REV_CHOICE -->|是| REVERT_COMMIT["git revert 到上一次 good commit"]
            REV_CHOICE -->|否| FIX_MANUAL["手动隔离问题代码"]
            REVERT_COMMIT --> F5
            FIX_MANUAL --> F5
        end

        F6 -->|是| FEATURE_LOOP["Feature 实现循环"]
        FEATURE_LOOP --> FEAT1["按 priority 从高到低\n选择一个未完成 feature"]
        FEAT1 --> FEAT2["实现该 feature"]
        FEAT2 --> FEAT3["运行 E2E 测试"]
        FEAT3 --> FEAT4{测试是否通过?}

        FEAT4 -->|否| FEAT5["Generator 自测定位问题"]
        FEAT5 --> FEAT6{是否为核心 bug?}
        FEAT6 -->|是| FIX_INNER["修复该 bug"]
        FEAT6 -->|否| DEFER["标记为已知问题\n记录到 progress"]
        FIX_INNER --> FEAT3
        DEFER --> FEAT1

        FEAT4 -->|是| FEAT7["标记 passes = true\n写入 progress"]
        FEAT7 --> FEAT8["git commit"]
        FEAT8 --> FEAT9{是否还有\n未完成 feature?}

        FEAT9 -->|是| FEAT1
        FEAT9 -->|否| FEAT10["Session 完成"]
    end

    subgraph QA_PHASE["质量评估阶段"]
        FEAT10 --> QA1["Generator 自评本轮结果\n（对照 spec 检查完成度）"]
        QA1 --> QA2["Generator 将应用\n提交给 Evaluator / QA"]
        QA2 --> QA3["Evaluator 用 Playwright 实测\n点击界面 / 检查 API / 校验 DB 状态"]
        QA3 --> QA4["按标准评分\n产品深度 · 功能 · 视觉 · 代码质量"]
        QA4 --> QA5{所有指标\n是否过硬阈值?}
    end

    QA5 -->|否| BUG_OUT["Evaluator 输出详细 bug 清单\n写入 bug_report.json"]
    BUG_OUT --> FIX_FEEDBACK["Generator 修复问题"]
    FIX_FEEDBACK --> SELFTEST["Generator 自测\n确认修复不破坏已有功能"]
    SELFTEST --> QA_CHK{自测是否通过?}
    QA_CHK -->|否| FIX_FEEDBACK
    QA_CHK -->|是| QA2

    QA5 -->|是| SPRINT_PASS["Sprint N 通过"]
    SPRINT_PASS --> SPEC_DONE{Spec 是否完成?}

    SPEC_DONE -->|否| NEXT_SPRINT["进入 Sprint N+1\nGenerator 携带上一轮 bug_report.json\n提出新的 sprint 目标"]
    NEXT_SPRINT --> C1

    SPEC_DONE -->|是| DONE([输出完整应用])
```

---

## 变更对照表

### P0（必须修复）

#### 1. 拆分 "项目完成" → Session Complete / Sprint Pass
**原图：** 所有 feature 实现后直接走 QA，没有区分
**v2：** 添加了 `Session 完成` 中间节点，明确 QA 是 Sprint 级别评审，不是 Session 结束的直接结果

#### 2. 加入 Git Revert 路径
**原图：** Bug fix 后没有回退机制
**v2：** 添加了 `检查 git diff → 可 revert? → git revert 到上一次 good commit` 路径，防止修复引入更多问题

---

### P1（提升鲁棒性）

#### 3. Feature 选择策略
**原图：** `选择一个未完成 feature`（随机）
**v2：** `按 priority 从高到低选择一个未完成 feature`，feature_list.json 结构增加了 `priority` + `depends_on` 字段

#### 4. Evaluator 历史报告跨 Sprint 传递
**原图：** 每轮 Sprint 独立，bug_report 只影响本轮修复
**v2：** Sprint N+1 开始时，Generator 携带上一轮 bug_report.json 作为背景信息，影响新 Sprint 的目标提出

#### 5. Bug Fix 后自测
**原图：** 修复后直接交给 Evaluator
**v2：** Generator 自测 → 通过 → 再提交给 Evaluator，避免浪费 QA 轮次

#### 6. 后续 Sprint Init Agent 行为
**原图：** 后续 Sprint 是否还跑 init 不明确
**v2：** 添加了 `Spec 是否变更?` 判断分支，仅在变更时更新 feature_list.json 和 init.sh，git 仓库始终继承

---

### P2（表达清晰度）

#### 7. "宣读编写代码" 拆分为宣读 + 执行
**原图：** `Generator 宣读编写代码并实现功能`
**v2：** 拆为 `Generator 宣读本轮执行方案` → `开始任务`，对应前面的协商结果

#### 8. 基础测试判断标准量化
**原图：** `系统是否正常？` 无量化标准
**v2：** 在 sanity_check 节点旁标注"所有 passes = true 的 feature 回归测试通过"

#### 9. Bug Fix 分类
**原图：** 所有测试失败统一处理
**v2：** 区分"核心 bug"（立即修）和"已知问题"（记录 defer），避免在非关键问题上卡住

---

## 节点一览表

| 节点 | 类型 | 说明 |
|------|------|------|
| 用户输入 | 起点 | 一句需求 |
| Planner 生成 Spec | 执行 | 一次性 |
| Generator 提出 Sprint 目标 | 执行 | 带 priority + depends_on |
| Evaluator 审核目标 | 执行 | 协商循环 |
| Generator 宣读执行方案 | 执行 | 对接协商结果 |
| Initializer Agent | 执行 | 仅 Sprint 1 |
| 后续 Sprint 检查 | 判断 | Spec 变更? |
| Session 初始化 | 执行 | 读 progress / git log |
| 运行 init.sh | 执行 | 每次 Session |
| 基础 E2E 测试 | 执行 | 回归验证 |
| 系统正常? | 判断 | 回归失败→修 |
| Git revert 路径 | 执行 | 可选 |
| 按 priority 选 feature | 执行 | 带依赖解析 |
| 实现 feature | 执行 | 单元级 |
| E2E 测试 | 执行 | feature 级 |
| 测试通过? | 判断 | 失败→fix/defer |
| git commit | 执行 | feature 级 |
| 还有未完成 feature? | 判断 | 循环/结束 |
| Session 完成 | 里程碑 | 内部节点 |
| Generator 自评 | 执行 | 对照 spec |
| Evaluator Playwright QA | 执行 | Sprint 级 |
| 评分 | 执行 | 四维标准 |
| 指标过硬阈值? | 判断 | Sprint 通过条件 |
| 输出详细 bug 清单 | 执行 | bug_report.json |
| Generator 修复 | 执行 | 含自测验证 |
| 自测通过? | 判断 | 防引入新 bug |
| Sprint N 通过 | 里程碑 | 可进下一 Sprint |
| Spec 完成? | 判断 | 整体结束条件 |
| 输出完整应用 | 终点 | — |

---

## artifact 一览表

| 文件 | 创建节点 | 更新节点 | 用途 |
|------|----------|----------|------|
| `spec.json` | Planner | — | 产品规格（一次性） |
| `feature_list.json` | Initializer Agent | 后续 Sprint 检查 | 需求清单（带 priority） |
| `claude-progress.txt` | Initializer Agent | 每个 feature 完成后 | 已完成工作记录 |
| `init.sh` | Initializer Agent | 后续 Sprint 检查 | 启动脚本 |
| `bug_report.json` | Evaluator | — | 当前 Sprint 的 QA 反馈 |
| `git history` | Initializer Agent | 每个 feature 完成后 | 可回滚的版本历史 |
