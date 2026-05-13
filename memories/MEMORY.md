Hermes 采用 memory + Obsidian 外脑 + skill 的三层知识结构：memory 只放每轮必须常驻的稳定事实；Obsidian 放长文档、配置清单、历史记录、低频细节；skill 放可复用流程、排障步骤和工具操作方法。
§
写入前必须分类：用户长期偏好进 USER.md；系统级稳定事实进 MEMORY.md；操作步骤和流程进 skill；详细配置、历史经验、长文档进 Obsidian；临时任务进展不写入长期记忆。
§
涉及当前工具、路径、账号、运行状态、服务状态时，不凭 memory 判断，必须实时检查或读取权威文档。
§
Gu 的环境和 Hermes 配置详情以 Obsidian 中的系统环境配置、Hermes 配置参考文档为外脑索引；MEMORY.md 只保留这些索引位置，不展开细节。
§
复杂代码任务可混合使用 Codex 和 Claude Code；根据任务性质决定谁实现、谁审查、谁修复，不固定为单一流水线。
§
网页链接理解任务优先使用浏览器能力直接读取真实页面内容；如果受登录、权限、风控或技术限制无法读取，再说明限制并请求 Gu 补充必要上下文。
§
2026-05-13: hermes-internal 更名为 安布罗西尼（Ambrosini），G 质量审核角色。agent-registry.json 中 display_name 和 soul 已更新。agent_id 保持 "hermes-internal" 不变（系统标识不随名称改）。
§
Deepseek API 对并发子会话的模型推理请求有超时问题 — 子 Agent 工具调用正常但模型推理生成大输出时易被中断（exit_reason: interrupted, waiting for model response）。更换 provider 可解决。delegation 配置中 child_timeout_seconds=600（够用），问题不在此。
§
skill_manage(action='write_file', name='huashu-design') fails with 'Skill not found' even though the skill exists (confirmed via skills_list + skill_view). This is a persistent tool bug. Workaround: patch SKILL.md directly to add reference pointers, or use terminal to create reference files manually.
§
agent-registry.json supports `soul` field for agent persona. `delegate_tool.py` `_build_child_system_prompt()` injects it into child agent system prompt. Only works via `delegate_task(agent_id=...)` — not when DMing agent on Feishu (separate Bot path). For Feishu access, create Hermes profile with SOUL.md + gateway.
§
API key truncation: `patch` tool may write truncated keys (e.g., `sk-53c...bdb3` instead of full 35 chars) when the key appears in old_string/new_string. Always verify written key length matches source. Workaround: Python `re.sub` from env var, or use `memory`/`skill_manage(action='patch')` which has different redaction behavior.
§
用户对角色分工极其敏感。一旦确认了8个角色的分工方案，绝不能再提议合并角色——"我目的是分工，你干嘛老给我合在一起"是明确不满。功能重叠时重新分配职责而非删减角色。
§
马蒂尼（主线）skill 瘦身：155→38（75%↓）。保留系统核心+分析协调+设计内容+社交资讯四大类。各子Agent skill 配置：内斯塔 42、皮尔洛 55、安布罗西尼 19。html-ppt 基础 skill 独立包含模板，不需要个体 theme 变体。