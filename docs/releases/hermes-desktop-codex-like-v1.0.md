# Hermes Desktop Codex-like v1.0

日期：2026-06-04
版本：v1.0-consolidation
状态：收口完成

---

## 一、产品主链路

```
Project → Task Thread → Agent Run → Logs/Diff → Review → Done
```

此链路在所有架构文档中保持一致，未被任何模块替换或绕过。

---

## 二、执行器支持矩阵

| Executor | 状态 | CLI 命令 | 说明 |
|---|---|---|---|
| **Codex CLI** | ✅ 可用 | `codex` | 当前主实现工具。支持命令启动、日志收集、退出状态。 |
| **hermes-local** | ✅ 可用 | 内置 | 本地 Hermes agent 会话（同进程）。 |
| **opencode** | ✅ 可用 | `opencode` | 本地开源 coding agent。支持非交互式 run。 |
| **claude-code** | ❌ 未安装 | `claude-code` | 需手动安装 `npm install -g @anthropic-ai/claude-code` |
| **deepseek-tui** | ❌ STUB | `deepseek-tui` | 交互式 TUI 无法程序化驱动。始终显示 UNAVAILABLE。建议使用 `hermes-local` + `deepseek-v4-flash` 替代。 |

---

## 三、Executor 路由规则

| 任务类型 | 推荐 Executor | 置信度 |
|---|---|---|
| 架构设计 / ADR / review | claude-code | 90% |
| 复杂实现 / 大范围重构 | codex-cli | 85% |
| 本地开源 agent 验证 / 实验 | opencode | 80% |
| 快速 bug scan / 小修复 | deepseek-tui | 88% |
| Hermes 内部流程（gateway/adapter/scheduler） | hermes-local | 82% |

Router 只推荐不自动执行。用户必须手动确认后才创建 run。

---

## 四、Worktree 隔离

每个 Task Thread 可绑定独立 git worktree：

- 路径：`.hermes/worktrees/<thread_id_short>/`
- 分支：`hermes/<thread_id_short>/<run_seq>`
- 创建条件：主仓库必须 clean（无未提交变更）
- 操作：merge back、discard（不可逆，需确认）
- 并行安全：允许多个不同 worktree 的 task 并行，禁止同一 worktree 被多个 run 同时写入

---

## 五、Review / QA

| 类型 | 触发 | 推荐 Executor | 规则 |
|---|---|---|---|
| Review | main run complete + worktree dirty + 用户手动 | claude-code | 分析 diff，输出结构化 findings，不修改代码 |
| QA | main run complete + worktree dirty + test_commands 存在 + 用户手动 | opencode | 运行测试，识别风险，不修改代码 |

Review/QA run 不覆盖 main run 状态。用户基于 findings + test results 做最终决策（Accept / Reject / Continue）。

**安全约束**：review/qa run 的 `ExecutorConfig.disabled_tools` 自动填入 `['write_file', 'edit_file', 'create_file']`，Orchestrator 拦截写操作。

---

## 六、External Inbox

外部消息（Feishu / Discord / CLI / Scheduler）只能投递到 Inbox，**不能直接执行代码**：

- 用户审查 InboxItem → Convert to Task → Task Thread (draft) → 用户手动发起 Run
- `raw_payload` 不污染 prompt — 只从 `TaskDraft.suggested_prompt` 提取
- Result 回写：CLI ✅ 可用；Feishu/Discord/Scheduler ❌ stub

---

## 七、v1.0 收口修复（P0/P1）

### P0（已修复）

| ID | 问题 | 修复 |
|---|---|---|
| P0-1 | 状态模型分散在 8 份文档中 | 在 `hermes-desktop-state-model.md` 末尾追加 v1.0 模型补充章节，覆盖 v0.5–v0.8 所有新增模型 |
| P0-2 | `InboxSource.manual` vs `TaskSource.desktop` 不一致 | `InboxSource.MANUAL` → `DESKTOP`；统一 `TaskSource = 'desktop' \| 'cli' \| 'feishu' \| 'discord' \| 'api' \| 'scheduler'` |
| P0-3 | `streamEvents` 终止契约未在接口注释中落实 | 已在 `AgentExecutorAdapter` Protocol 的 `stream_events` 文档字符串中明确「必须以 FAILED event 结束，不得静默结束」 |

### P1（已修复）

| ID | 问题 | 修复 |
|---|---|---|
| P1-1 | Trae 角色未定义 | 标注为 P2（Phase 1 开始前需 ADR 确认）。暂不影响当前代码 |
| P1-2 | `ExecutorConfig` 无 `disabled_tools` 字段 | 添加 `disabled_tools: List[str]` 字段 |
| P1-3 | `AgentRun` 无 `run_seq` 字段 | 添加 `run_seq: int` 字段 + `run_type: str` |
| P1-4 | Router `hermes-local` 关键词含 `scheduler` | 从关键词列表移除 `scheduler` |
| P1-5 | `recent_tasks.summary` 来源不明确 | 明确来源：`AgentRun.error_summary` 或 `ReviewDecision.comment`，两者为空则为 null |

### 代码级修复（本次收口额外发现）

| 项目 | 修复 |
|---|---|
| executor_id 不一致 | registry `"codex"` → `"codex-cli"`，与 router 规则对齐 |
| opencode adapter 未导出 | `__init__.py` 添加 `OpenCodeAdapter` 导出 |
| review/QA 类型未导出 | `__init__.py` 添加所有 v0.7 类型导出 |
| inbox 类型未导出 | `__init__.py` 添加所有 v0.8 类型导出 |
| `RouterRecommendation.source` 枚举 | `"manual"` → `"user_override"` |

---

## 八、P2（未修复，v1.1+）

| ID | 问题 | 说明 |
|---|---|---|
| P2-1 | WorkspaceContext 无版本/变更历史 | AgentRun 可增加 `context_snapshot` 字段存储 context hash |
| P2-2 | InboxItem.expires_at 清理策略 | 过期扫描 + 30 天归档策略 |
| P2-3 | deepseek-tui ui_fidelity:low 的 UI 降级 | ToolCallCard 隐藏、只显示 log stream |
| P2-4 | review/qa run 与 merge 的竞争条件 | Orchestrator 在 merging 时检查活跃 review/qa run |
| P2-5 | Codex.app 降级未在 ADR 中记录 | ADR 末尾追加修订记录 |
| - | Trae 角色未定义 | Phase 1 开始前需 ADR 确认 |

---

## 九、当前代码状态

- 总文件数：20
- 总行数：6,124
- 所有健康检查、路由器测试、worktree 全周期测试通过
- `codex-cli` 在 registry 中注册为 `codex-cli`，与 router 规则一致
- `InboxSource.DESKTOP` 替代 `InboxSource.MANUAL`
- `openCodeAdapter` 通过 `__init__.py` 正确导出
