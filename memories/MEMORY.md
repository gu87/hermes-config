Hermes 采用 memory + Obsidian 外脑 + skill 的三层知识结构：memory 只放每轮必须常驻的稳定事实；Obsidian 放长文档、配置清单、历史记录、低频细节；skill 放可复用流程、排障步骤和工具操作方法。
§
写入前必须分类：用户长期偏好进 USER.md；系统级稳定事实进 MEMORY.md；操作步骤和流程进 skill；详细配置、历史经验、长文档进 Obsidian；临时任务进展不写入长期记忆。
§
涉及当前工具、路径、账号、运行状态、服务状态时，不凭 memory 判断，必须实时检查或读取权威文档。
§
Gu 的环境和 Hermes 配置详情以 Obsidian 中的系统环境配置、Hermes 配置参考文档为外脑索引；MEMORY.md 只保留这些索引位置，不展开细节。
§
Hermes 权威信息分层以 `/Users/gu/.hermes/docs/hermes-authority-map.md` 为准；运行状态、端口、重启和回滚命令以 `/Users/gu/.hermes/docs/hermes-runtime-runbook.md` 为准。
§
OpenChronicle 召回结果注入规则：每轮对话开始时，主动调用 `mcp_openchronicle_search` 检索相关记忆，将结果以 `<memory-context>...</memory-context>` 标签引用在回复前，而非写入 system prompt。MEMORY.md + USER.md 的静态内容保持在 system prompt 中不变，保证 cache 命中率。
§
网页链接理解任务优先使用浏览器能力直接读取真实页面内容；如果受登录、权限、风控或技术限制无法读取，再说明限制并请求 Gu 补充必要上下文。
§
电脑配置：MacBook Air M1（8核），8GB 内存，228GB 硬盘（~30GB 可用）。无独立 GPU。这是评估本地模型/工具可行性的硬约束。
§
SOUL.md(~/.hermes/SOUL.md)是权威身份文件。Agent分工:马蒂尼=总控、内斯塔=技术、OpenClaw=调研、皮尔洛=策划、TARS=桌面操作、Codex=代码审查、Claude Code=技术执行。路由:A.改UI写代码→内斯塔预处理→Claude Code执行→内斯塔验收。B.技术诊断→内斯塔。C.方案/内容→皮尔洛。D.调研→OpenClaw。E.代码审查→Codex(不执行)。F.需求模糊→clarify。
§
自检规则：动手前强制三问。任何 write_file/patch/terminal（修改类操作）之前，必须自检：(1)涉及代码或配置修改？(2)超过3步？(3)有副作用？任一答「是」则走内斯塔→CC→内斯塔流程，不得自己直接执行。三个全「否」才能直接做。不确定时默认走流程。这是硬性约束，已经违反过一次，不允许再犯。
§
macOS cc命令冲突：系统 /usr/bin/cc（Clang编译器）与Claude Code别名冲突。修复：alias cc="claude"写入~/.zshrc。
§
用户明确纠正过我的角色行为：说要安装什么东西时，我先自己干而不是按分工流程走，用户质问 "这事儿你又要自己干？别忘了你的角色设定"。凡涉及安装/部署/配置（git clone, brew install, 配环境等），必须按自检规则走 内斯塔→CC→内斯塔 流程，不得自己直接执行。这条已有 SOUL.md 规则但我仍会犯错，需要持续自我约束。
§
terminal tool shell parsing bug with Chinese comments: When writing multiline terminal commands, Chinese characters on lines before bash commands cause the tool repair layer to strip the shell prompt prefix but leave the Chinese line intact, which bash tries to execute as a command and fails with e.g. "/bin/bash: line X: 检查: command not found". Workaround: (1) Put Chinese commentary AFTER the command or in a separate echo statement, (2) Use pure English with `#` comments inside the command string, (3) Or keep each command on its own line without prefixed commentary lines. This is a persistent issue - do NOT write `# 中文注释` lines before bash commands in the terminal tool.
§
visual-novel-studio pipeline test-complete: 2026-05-16 tested with Beckham 1998 article (https://m.dongdianqiu.com/article/5827910.html). Full pipeline ran: Hermes scored article (100/100) → 皮尔洛 wrote script (52KB/980lines/5chapters) → flatten.py converted to 80 flat nodes → gen.py generated 5 backgrounds (GPT Image 2, ~4min each) → compress.py optimized (1.3MB→83KB avg) → assemble.py built dist/index.html (1.1MB/1588lines). Scripts at ~/.hermes/scripts/vns/{config,gen,edit,compress,assemble}.py and ~/.hermes/skills/visual-novel-studio/scripts/flatten.py. Only gaps: UnifiedRewardSDK (ad SDK) and 懂球帝 API cookie.
§
VNS 图片全量审计工作流实践教训：不要一口气做到底再给用户验收。正确的做法是建 Kanban 看板，每个子任务完成后推送摘要给用户审核，用户确认后才进入下一步。早期（1-2次）每步人工审核，熟悉后可逐步放开到半自动/全自动。可调控制度——不是二元的「手动 vs 自动」，而是可调节的审核密度。
§
当用户说「重新生成图片」或涉及图片生成管线调查时，必须派给内斯塔调查管线+出prompts+task package，Hermes不自己读gen.py/workflow/ComfyUI配置。这是硬性分工约束——用户已明确纠正过两次。
