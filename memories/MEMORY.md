Hermes memory policy: MEMORY.md 只放每轮必须常驻的稳定事实和权威索引；用户长期偏好进 USER.md；长文档、历史记录、配置清单、排障细节进 Obsidian/OpenChronicle；可复用流程进 skill/runbook；临时进展不写入长期记忆。
§
涉及路径、账号、端口、运行状态、服务状态、当前模型或权限时，不凭 memory 判断，必须实时读取权威文件或运行健康检查。
§
权威索引：身份和角色边界看 `/Users/gu/.hermes/SOUL.md`；知识分层看 `/Users/gu/.hermes/docs/hermes-authority-map.md`；运行态和自检看 `/Users/gu/.hermes/bin/hermes-system-doctor.py` 与 `/Users/gu/.hermes/docs/hermes-runtime-runbook.md`；Agent 编制/能力/路由看 `config/agent-registry.json` 和 `hermes-agent/configs/managed_agents/agents.yaml`；模型看 `config/models.yaml`。
§
OpenChronicle 召回规则：需要历史细节时调用 `mcp_openchronicle_search`，用 `<memory-context>...</memory-context>` 引用；不要把低频细节塞回 system prompt。
§
电脑硬约束：MacBook Air M1，8GB 内存，约 228GB SSD，无独立 GPU。评估本地模型、桌面自动化和常驻服务时必须考虑内存压力。
§
当前 Hermes 运行模型：单飞书入口，默认/马蒂尼 `ai.hermes.gateway` 常驻；旧 profile gateway 默认禁用。Agent 编制通过主入口内部路由/managed agents 调度。
§
核心 Agent 编制：Hermes 技术翻译官、Claude 主程执行官、Codex 代码审查官、DeepSeek 低成本快工、Intelligence 情报研究员、Pirlo 商业策划师、Designer 视觉设计师、TARS 桌面操作员、Ambrosini 质量门卫。
§
自检防漂移规则：系统快照必须先跑 `python3 /Users/gu/.hermes/bin/hermes-system-doctor.py`；报告容量、模型、Agent、skill、toolsets 时必须给源文件/实时检查证据；旧日志只能标 STALE，不能单独定性当前故障。
§
副作用操作规则：涉及安装、部署、配置、写代码、改核心文件、删除/覆盖等操作时先判断风险并走合适分工；不可逆或核心配置操作需用户确认。
§
代理环境：Clash Verge 常用本地代理 `127.0.0.1:7890`；非 login shell 可能不读取 `~/.zshrc` 代理变量，必要时显式传 `--proxy` 或 env。npm registry 国内可能超时，优先考虑 npmmirror。
§
GitHub MCP 认证优先走 `gh auth status` + `gh auth token` 写 `.env` GITHUB_TOKEN；gh 用 keychain/OAuth，比手动 PAT 更不易过期。
§
Claude agent 委托路径与本地 Claude Code Pro 独立：Hermes 委托通过外部 Claude Code CLI，需避免继承错误 `ANTHROPIC_API_KEY`；agent 401 不等于 Claude Code 坏。
§
任务-工具匹配规则：收到内容转换/生成类任务时，先检查可用 skill 或专用服务；Markdown/内容转样式化 HTML 优先用 html-anything API（14732），不手写 HTML。
§
LibreOffice CLI automation 已部署，归 TARS 桌面自动化域；用 `python3.11 -m cli_anything.libreoffice`，详情看 skill `libreoffice-cli`。
§
verify-task.py 对 outbox.status 有双层校验（TASK_STATUSES vs VALID_OUTBOX_STATUSES），交集仅 {failed, blocked}。标准格式 outbox（含 agent_id+next_action）无法用 success/completed 通过。非标准格式（无 next_action）可绕过。详细设计分析见 docs/adr/ADR-verify-task-dual-status-validation.md，已在 verification-loop skill 的 pitfall 节引用。当前判定为设计特性非 bug，不在 v2.8.1 修改，v2.8.2 计划降级为 warning。