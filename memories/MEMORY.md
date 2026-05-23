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
SOUL.md(~/.hermes/SOUL.md)是权威身份文件。Agent分工:马蒂尼=总控、内斯塔=技术、Intelligence=调研/情报、皮尔洛=策划、TARS=桌面操作、Codex=代码审查、Claude Code=技术执行。路由:A.改UI写代码→内斯塔预处理→Claude Code执行→内斯塔验收。B.技术诊断→内斯塔。C.方案/内容→皮尔洛。D.调研/情报→Intelligence。E.桌面/App/GUI操作→TARS。F.代码审查→Codex(不执行)。G.需求模糊→clarify。
§
自检规则：动手前强制三问。任何 write_file/patch/terminal（修改类操作）之前，必须自检：(1)涉及代码或配置修改？(2)超过3步？(3)有副作用？任一答「是」则走内斯塔→CC→内斯塔流程，不得自己直接执行。三个全「否」才能直接做。不确定时默认走流程。这是硬性约束，已经违反过一次，不允许再犯。
§
macOS cc命令冲突：系统 /usr/bin/cc（Clang编译器）与Claude Code别名冲突。修复：alias cc="claude"写入~/.zshrc。
§
用户明确纠正过我的角色行为：说要安装什么东西时，我先自己干而不是按分工流程走，用户质问 "这事儿你又要自己干？别忘了你的角色设定"。凡涉及安装/部署/配置（git clone, brew install, 配环境等），必须按自检规则走 内斯塔→CC→内斯塔 流程，不得自己直接执行。这条已有 SOUL.md 规则但我仍会犯错，需要持续自我约束。
§
系统快照流程：用户说「看看Agent状态/系统快照」时按 (1) ps aux 查进程 (2) agent-registry.json 读注册表 (3) gateway_state.json 查连接（可能过时，需日志验证）(4) errors.log 尾N行 (5) lsof 查端口 (6) vm_stat+df 查资源。输出：网关进程表 + Agent注册表 + 端口映射 + 问题列表 + 定时任务表。
§
skill_manage 对部分已注册 skill（如 lark-shared）报 "not found"，但 skill_view/skills_list 能找到。这是 skill 注册表索引 bug，非名称错误。遇到时走降级：要么创建新 skill，要么存 memory。需 curator 修复 skill_manage 的 name 解析逻辑。
§
当用户说「重新生成图片」或涉及图片生成管线调查时，必须派给内斯塔调查管线+出prompts+task package，Hermes不自己读gen.py/workflow/ComfyUI配置。这是硬性分工约束——用户已明确纠正过两次。
§
2026-05-21: Managed Agents(编制制)架构确认为 Hermes 操作模式，写入 SOUL.md 核心哲学 + Obsidian wiki。SOUL 备份: ~/.hermes/docs/soul-backups/SOUL.md.2026-05-21。本体升级(475 commits落后)建议等 tagged release 再升。
§
lark-cli update 失败模式排查：超时/exit 4 表示 npm registry 不可达。Gu 机器有 Clash Verge 代理 127.0.0.1:7890 但无 HTTP_PROXY env vars。排查: networksetup→lsof -i :7890→env|grep -i proxy。Go 二进制内建 HTTP 客户端可能不读 HTTP_PROXY。替代方案: 从 cdn.npmmirror.com/binaries/lark-cli/ 手动下载 tar.gz 解压替换 ~/.npm-global/lib/node_modules/@hermes-os/lark-cli/bin/lark-cli。
§
代理环境：Clash Verge (verge-mih) 运行在 127.0.0.1:7890，系统网络设置已启用 Web Proxy，~/.zshrc 已配 HTTP_PROXY 等环境变量。但 Hermes terminal 工具不自动 source ~/.zshrc（非 login shell），terminal 命令看不到代理 env vars，需显式传 --proxy 或设 env。Hermes 网关和 Feishu 通过系统代理正常通信。lark-cli update 的 Go 二进制内置 HTTP 客户端不走环境变量代理，需手动从 npmmirror CDN 下载二进制替换。npm registry（registry.npmjs.org）Cloudflare CDN 在国内连接超时，npmmirror.com 可用。
§
2026-05-23: 飞书运行模型收敛为单入口：只保留 default/马蒂尼 `ai.hermes.gateway` 常驻连接飞书；`nesta`、`piero`、`maldini`、`ambrosini` profile gateway 均 disabled。Agent 编制保留，通过主入口内部路由/managed agents 调度。
