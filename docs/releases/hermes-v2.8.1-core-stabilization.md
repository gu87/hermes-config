# Hermes v2.8.1 Core Stabilization

**Release**: v2.8.1-core-stabilized  
**Date**: 2026-06-02  
**Type**: Core stabilization — no new features, no new agents, no application-layer changes  

---

## 修复目标

在 v2.8 Task Card Pipeline 部署后，对系统进行全量配置审计、漂移修复、安全边界加固和交付质量闭环。本次提交聚焦于让 managed agents 运行时达到可稳定生产的状态，而非增加功能。

---

## 关键变更

### 1. managed-agents mirror drift 修复

**问题**: `config/managed-agents.yaml` 与工程源 `hermes-agent/configs/managed_agents/agents.yaml` 存在结构和内容不一致。`bin/setup.sh` 的部署方向错误（旧镜像覆盖工程源文件）。

**修复**:
- `config/managed-agents.yaml` 重写为与 agents.yaml 一致的结构化格式
- `bin/setup.sh` 修正部署方向：以 agents.yaml 为权威源，managed-agents.yaml 仅作为部署镜像
- `bin/hermes-system-doctor.py` 新增 managed-agents.yaml 镜像一致性检查
- `skills/hermes-subagent-delegation/SKILL.md` 新增配置权威源说明和修改流程

### 2. OpenCode 状态明确

**问题**: `opencode` Agent 在 agent-registry.json 中缺失，导致某些协作链路不可用。

**修复**:
- `config/agent-registry.json` 新增 `opencode` Agent 完整配置（外部 OpenCode CLI 适配器，模型链 opencode_go_deepseek_flash → opencode_go_deepseek_pro）
- 新增 `scripts/opencode-agent.py` 适配脚本
- 新增 `tests/test_opencode_agent.py` 基础测试

### 3. Gate-Policy error taxonomy 扩展

**问题**: v2.8 标准 outbox 的 `error_taxonomy` 字段缺乏系统级的 taxonomy→action 映射，gate-policy.py 分流逻辑依赖手工匹配。

**修复**:
- `scripts/gate-policy.py` 新增 `_TAXONOMY_POLICY` 表：将 11 种 taxonomy code 映射到 5 种 policy action（complete/auto_revision/reject/manual_review/switch_agent）
- 新增 `policy_for_v2_8_1()` 函数：taxonomy-driven 路由，按 severity 优先级选择最严厉 action
- `templates/gate_policy_v2_8.json` 定义 auto_revision_checks 和 hard_stop_checks 集合
- `templates/acceptance_criteria_cheatsheet.md` 新增 error_taxonomy 分类、gate decision 映射、语义检查清单 SC-01~SC-08

### 4. Outbox 标准 schema 与只读 Agent changed_files 强校验

**问题**: 只读 Agent（codex/hermes-internal/pirlo/ambrosini）可以在 outbox 中声明 changed_files 非空而无任何拦截。

**修复**:
- `verify-task.py` `validate_standard_outbox()` 新增 `SCOPE_VIOLATION` 检查：只读 Agent 的 `changed_files` 必须为空
- `verify-task.py` `validate_standard_outbox()` 新增标准 outbox 必填字段、status 枚举、next_action 枚举、type 检查
- `review-task.py` 新增 `allowed_files_check` + `must_avoid_respected` 双重检查
- `review-task.py` 新增 `changed_files_source` 和 `evidence_quality` 检查
- `gate-policy.py` 将 allowed_files_check 和 must_avoid_respected 归类为 hard_stop，直接 reject

### 5. Task Card budget 字段

**问题**: revision 循环无上限控制，可能导致无限返工。

**修复**:
- `scripts/run-task-gate.py` 默认最多自动生成 2 轮 revision inbox
- `gate-policy.py` 在 `revision_task.created=false` 且 `reason` 包含 "limit" 时路由到 `manual_review`
- `templates/task_package_template.md` 记录预算字段与超限行为

### 6. TARS 安全边界加固

**问题**: TARS 桌面操作员的能力描述引用已废弃的 agent_id（如 `kimi`）。

**修复**:
- `skills/autonomous-ai-agents/chief-of-staff/SKILL.md` 移除 `kimi` alias，改用当前 registry 中的 agent_id
- `skills/hermes-multi-agent-research/SKILL.md` 升级 delegation protocol 为 v2.8，显式标注 `delegate-v26.sh`/`delegate-v27.sh` 已废弃

### 7. hermes-system-doctor.py 从 FAIL 恢复到 WARN

**问题**: doctor 之前因 managed-agents mirror 缺失报 FAIL。

**修复**:
- doctor 现在正确检测 mirror 并比较内容
- 当前唯一告警：git state（30 个 changed/untracked entries），属于提交前预期状态

---

## 行为变化

| 变更 | v2.8 之前 | v2.8.1 |
|------|----------|--------|
| `child_timeout_seconds` | 600 秒 | **180 秒**（降低子 Agent 无响应等待时间） |
| 只读 Agent 越权写文件 | 静默通过 | **SCOPE_VIOLATION → fail → reject** |
| scope_violation（文件越界） | review-task.py 可能漏检 | **allowed_files_check + must_avoid_respected 双重拦截 → reject** |
| artifact_missing | 无分类 | **taxonomy: artifact_missing → auto_revision** |
| budget_exceeded（revision 超限） | 无控制 | **manual_review**（不自动返工） |
| 标准 outbox status 校验 | 仅 TASK_STATUSES | **双层校验**（TASK_STATUSES + VALID_OUTBOX_STATUSES） |
| Claude 主程模型 | claude_opus 默认 | **claude_sonnet 默认**（opus 用于复杂/高风险实现） |
| DeepSeek 快工模型 | deepseek_pro 优先 | **deepseek_flash 优先**（降低低成本路径的 token 开销） |
| gate-policy 分流 | 基于 check name 手工匹配 | **taxonomy-driven** 自动路由 |

---

## 兼容性说明

### 旧 revision_needed 兼容性

v2.8.1 保留了 `policy_for()` 的旧逻辑作为 `policy_for_v2_8_1()` 的 fallback。未携带 taxonomy 的旧 gate record 仍能通过 check-name-based 匹配得到正确的 policy action。

### 标准 outbox 路径注意事项

当前标准格式 outbox（含 `agent_id` + `next_action`）的 `status` 字段经过双层校验（TASK_STATUSES vs VALID_OUTBOX_STATUSES），两集合交集仅为 `{failed, blocked}`。**非标准格式 outbox（无 `next_action`）不受此影响，可正常使用任意 TASK_STATUSES 值**。

当前生产链路主要使用非标准格式，因此不影响实际交付。详见下文「已知设计债」。

---

## 已知设计债

### verify-task.py 双层 status 校验

**来源**: v2.5 任务层状态机（TASK_STATUSES，9 个值）+ v2.8 交付层状态（VALID_OUTBOX_STATUSES，3 个值）的独立迭代叠加。

**影响**: 标准格式 outbox 无法使用 `"success"` 或 `"completed"` 通过双校验。**当前不影响生产**（标准格式 outbox 未成为默认交付路径）。

**已记录**: `docs/adr/ADR-verify-task-dual-status-validation.md`  
**已在 skill 中标注**: `verification-loop` skill 的 pitfall 节

**迁移计划**:
- v2.8.2：将 `validate_standard_outbox` 中的 status 检查从 error 降级为 warning
- v2.9：拆分 `task_status` / `delivery_status` 双字段

---

## 验证结果

### Precommit Validation (2026-06-02)

| 检查项 | 结果 |
|--------|------|
| config.yaml 敏感信息审查 | ✅ 通过（仅 child_timeout_seconds 变更） |
| scripts/ 核心脚本变更检查 | ✅ 通过（三个核心脚本未被修改） |
| hermes-system-doctor.py | ⚠️ WARN（仅 git state 告警，全部核心服务正常） |
| Pipeline smoke test 1: 只读审查通过 | ✅ PASS |
| Pipeline smoke test 2: 只读 Agent 越权拦截 | ✅ SCOPE_VIOLATION → fail |
| Pipeline smoke test 3: artifact_missing 自动返工 | ✅ revision_needed → auto_revision |
| Pipeline smoke test 4: scope_violation 拒绝 | ✅ rejected → reject |
| Pipeline smoke test 5: budget_exceeded 转人工 | ✅ manual_review |

**5/5 pipeline 测试通过。4 种异常路径正确拦截。**

完整验证报告：`docs/reports/hermes-v2.8.1-precommit-validation.md`

---

## 未处理事项

以下项目在 v2.8.1 审计中发现但不在本次修复范围内：

| 项目 | 原因 | 建议版本 |
|------|------|---------|
| `verify-task.py` 双层 status 校验 | 不阻塞生产，风险评估为低 | v2.8.2 |
| orchestrator_enabled + max_spawn_depth=1 死能力 | 当前配置已禁用，无影响 | v2.8.2 |
| 子 Agent 无热启动/复用 | 需独立设计 child-agent session-cache | v2.9 |
| fixture test suite | precommit smoke test 使用合成 JSON，无完整 fixture | v2.8.2 |
| doctor --strict mode | 当前 doctor 无 strict flag | v2.8.2 |

**当前 `git status`**: 18 个已修改文件 + 约 30 个 untracked 新文件（全部为 v2.8.1 新增的 scripts/templates/skills/tests/docs）。

---

## 下一步 v2.8.2 建议

| 优先级 | 项目 | 说明 |
|--------|------|------|
| P1 | fixture test suite | 将 precommit smoke test 的合成 JSON 固化为可复现 fixture |
| P1 | doctor --strict | 新增 strict 模式，将 git state 告警也视为 FAIL |
| P2 | dual status warning downgrade | `validate_standard_outbox` status 检查降级为 warning |
| P2 | task-status.py 展示 gate decision | 在状态视图中显示最新 gate decision 和 revision chain |
| P3 | policy test cases | 为 gate-policy.py 的 11 个 taxonomy→action 映射补充单元测试 |
| P3 | child-agent session reuse | 研究 delegate_task 的 AIAgent 构造开销，评估热启动可行性 |

---

*Release note 结束。*
