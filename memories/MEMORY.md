Hermes memory policy: MEMORY.md 只放每轮必须常驻的稳定事实和权威索引；用户长期偏好进 USER.md；长文档、历史记录、配置清单、排障细节进 Obsidian/OpenChronicle；可复用流程进 skill/runbook；临时进展不写入长期记忆。
§
权威索引：身份和角色边界看 `/Users/gu/.hermes/SOUL.md`；知识分层看 `/Users/gu/.hermes/docs/hermes-authority-map.md`；运行态和自检看 `/Users/gu/.hermes/bin/hermes-system-doctor.py` 与 `/Users/gu/.hermes/docs/hermes-runtime-runbook.md`；Agent 编制/能力/路由看 `config/agent-registry.json` 和 `hermes-agent/configs/managed_agents/agents.yaml`；模型看 `config/models.yaml`；ADR 看 `docs/adr/INDEX.md`（当前 4 个：Closeout Memory Check v1 / Codex-like Workbench / Control-Plane-First / verify-task Dual Status）。
§
OpenChronicle 召回规则：需要历史细节时调用 `mcp_openchronicle_search`，用 `<memory-context>...</memory-context>` 引用；不要把低频细节塞回 system prompt。
§
电脑硬约束：MacBook Air M1，8GB 内存，约 228GB SSD，无独立 GPU。评估本地模型、桌面自动化和常驻服务时必须考虑内存压力。
§
当前 Hermes 运行模型：单飞书入口，默认/马蒂尼 `ai.hermes.gateway` 常驻；旧 profile gateway 默认禁用。Agent 编制通过主入口内部路由/managed agents 调度。
§
Closeout Memory Check v1 dogfood 观察项：验证中——真实任务中观察是否该提醒时提醒、不该提醒时静默、不产生噪音、不重复提案。发现问题只记录，不立即改。
§
记忆系统 dogfood 观察期（2026-06-08 起） — 三条观察项：
1. 开工前是否正确加载 PROJECT.md
2. 收工前是否正确触发 Closeout Memory Check（4-state output）
3. MEMORY / SOUL / PROJECT.md 是否出现重复或漂移
规则：不新增记忆层，不引入新依赖，不做自动学习。发现偏离时报告用户，不自作主张修复。
§
行为规则：当对话线程被其他任务打断后，当前子任务结束时必须主动捞回未完成的线程——"baoyu-design 还要继续吗？"之类。用户明确反感「给了建议动作但被打断后不回捞」的遗漏。这不是建议，是需要执行的闭环检查。
§
Gu 期望 Hermes 在话题被中断后主动捞回未完成的任务，而不是静默丢弃。"怎么又没有反馈了"是重复出现的纠正模式——中断不等于取消，闭环责任在 Hermes。
§
lark-cli 升级：1.0.39 → 1.0.49。npm postinstall 脚本 `node scripts/install.js` 会超时，workaround：`npm i -g @larksuite/cli@latest --ignore-scripts` 后手动跑 `node /path/to/scripts/install.js`。feishu-operations skill 已由 postinstall 自动更新为动态查版。
§
baoyu-design 已安装到 ~/.agents/skills/baoyu-design，symlink 到 ~/.hermes/skills/baoyu-design。设计对比测试输出目录：~/.hermes/output/design-compare/。delegate_task 不支持 per-task model 选择，跨模型测试需用 cronjob 的 model 参数。
§
SOUL 待更新项（本次会话发现，跨会话持久化到此 memory）：

1. **"怎么又没有反馈了"** — 任务被用户新消息打断后，收尾时没有主动把未完成事项捞回来。规则：每次完成任务或话题切换前，扫描是否有之前提出但未闭合的 action item，有则主动带到用户面前。

2. **"你让我看看，你别自己判断"** — 做对比/评估类任务时（设计对比、模型对比），先发原始输出给用户看，再做分析。不要只说结论不让看。数据展示类同理：先给表，再给判断。

3. **"这是有问题还是没有问题？"** — 用户问的是结论，不需要展开排障全流程。非阻塞性小问题直接说"没问题"，阻塞性问题说"有问题 + 一句话根因 + 修复方案"，不要给完整诊断日志。