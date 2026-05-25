Hermes memory policy: MEMORY.md 只放每轮必须常驻的稳定事实；用户长期偏好进 user-profile.md；长文档、历史记录、配置清单、排障细节进 Obsidian/OpenChronicle；可复用流程进 skill/runbook；临时任务进展不写入长期记忆。
§
涉及路径、账号、端口、运行状态、服务状态、当前模型或权限时，不凭 memory 判断，必须实时读取权威文件或运行健康检查。
§
权威索引：身份和角色边界看 `/Users/gu/.hermes/SOUL.md`；知识分层看 `/Users/gu/.hermes/docs/hermes-authority-map.md`；运行态、端口、重启和自检顺序看 `/Users/gu/.hermes/docs/hermes-runtime-runbook.md`；Agent 编制/能力/路由看 `/Users/gu/.hermes/config/agent-registry.json` 和 `/Users/gu/.hermes/hermes-agent/configs/managed_agents/agents.yaml`。
§
OpenChronicle 召回规则：需要历史细节时调用 `mcp_openchronicle_search`，用 `<memory-context>...</memory-context>` 引用；不要把低频细节塞回 system prompt。
§
电脑硬约束：MacBook Air M1，8GB 内存，约 228GB SSD，无独立 GPU。评估本地模型、桌面自动化和常驻服务时必须考虑内存压力。
§
当前 Hermes 运行模型：单飞书入口，默认/马蒂尼 `ai.hermes.gateway` 常驻；旧 profile gateway（nesta/piero/maldini/ambrosini）默认禁用。Agent 编制保留，通过主入口内部路由/managed agents 调度。
§
当前核心 Agent 编制：Hermes 技术翻译官（原 nesta 技术中间层）、Claude 主程执行官（外部 Claude Code CLI，后端由 CC Switch 控制）、Codex 代码审查官（外部 Codex CLI，只读审查）、DeepSeek 低成本快工、Intelligence 情报研究员、Pirlo 商业策划师、TARS 桌面操作员、Ambrosini 质量门卫。
§
系统快照/自检必须读取机器可读配置，不能只读 prompt：1) launchctl 查 gateway；2) agents.yaml + agent-registry.json 查 Agent；3) models.yaml 查 model_ref；4) config.yaml 查 delegation；5) MEMORY/user-profile 查字符上限；6) 最近 gateway 日志查错误。注意 `browser.camofox.managed_persistence` 不是 Agent 持久化开关。
§
自检规则：涉及安装、部署、配置、写代码、改核心文件、删除/覆盖等有副作用操作时，先判断风险并走合适分工；不可逆或核心配置操作需用户确认。已经确认过的设计不重复争辩。
§
代理环境：Clash Verge 常用本地代理 `127.0.0.1:7890`；非 login shell 可能不读取 `~/.zshrc` 代理变量，必要时显式传 `--proxy` 或 env。npm registry 国内可能超时，优先考虑 npmmirror 替代下载。
