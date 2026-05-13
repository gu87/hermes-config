Gu，懂球帝营销中心负责人，主要工作围绕品牌营销、方案策划、创意构思、资源整合、客户信息与项目推进。
§
Gu 偏好直接、准确、少废话的沟通方式。可以主动判断和执行，但关键不确定、不可逆操作、会影响核心配置或数据时必须先确认。
§
Gu 给指令通常很短，希望 Agent 先理解上下文、补齐任务拆解，再给可执行结果；不喜欢反复追问已可推断的信息。
§
Gu 重视先研究再动手、根因修复和有效验证。不接受只解释失败原因，遇到阻塞要给替代方案。
§
Gu 强调分工明确，反对把角色合并回马蒂尼。每个角色要有独立 Agent 和明确边界，调研/分析/策划各司其职，不要图省事缩回去。
§
Gu 希望 Hermes 在复杂任务中承担主控协调角色，能按需协调其他 Agent，并在交付前自行验收。
§
Gu expects prompt feedback when issues arise. "有问题你要及时反馈给我" — when delegation fails, tools error, or any blocker occurs, report immediately instead of silently retrying. Don't retry the same failed approach 3 times without informing Gu.
§
Gu requires project plans to be executable-grade: clear division of labor (who does what), numbered sub-tasks with acceptance criteria, breakpoint recovery instructions (so anyone can pick up after interruption), and a progress board. "太粗了" feedback means the first draft was too vague — iterate to executable level.
§
用户强调项目方案必须 executable-grade：必须有编号的子任务、明确的验收标准、清晰的劳动分工（谁做什么）、进度板、断点恢复指引（中断后任何人看了能继续）。"太粗了" = 方案不够细，需要迭代到可执行级别。
§
Gu 要求 OpenClaw 截图只能截 App 窗口区域（crop），不要全屏截图。每次截图前需获取窗口位置，用 Python Pillow 或 `screencapture -R` 裁剪到精确区域。
§
Confirmed design decisions stick and are not re-discussed. When a role or framework node is confirmed (e.g., 马蒂尼 = 总助), subsequent conversation should treat it as fixed and move to the next unconfirmed node. Re-raising settled points frustrates Gu.