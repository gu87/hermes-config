---
name: sports-marketing-intel
description: 体育赛事营销情报日报生成——搜索、抓取、结构化输出三信号日报。覆盖世界杯、奥运会、欧洲杯等大型赛事期间品牌营销动态监测。
---

# 体育营销情报日报

为懂球帝营销中心生成每日品牌营销情报，用于大型赛事（世界杯/奥运会/欧洲杯等）期间品牌动态监测和商业机会识别。

## 触发条件
- 定时任务执行体育营销情报搜集
- 用户要求查看赛事品牌营销动态
- 用户说"世界杯情报"、"营销日报"、"品牌动态报告"

**世界杯专用参考**：加载 `references/world-cup-2026-sources.md` 获取2026世界杯的品牌清单、信息源可用性矩阵和赛事关键日期。加载 `references/case-library-2026.md` 获取已抓取的品牌案例库，写日报时可快速引用避免重复抓取。

## 输出格式（严格三层结构）

```markdown
# 🏆 {赛事名}营销日报 | {YYYY.MM.DD} 早报/晚报

## 📌 今日三信号
> ① {最重要的一条——品牌动作有竞争威胁或商业机会}
> ② {第二条}
> ③ {第三条}

---

## 📰 品牌动态

### 1. {品牌名} {动作}
**时间**：{时间}
**动作**：{2-3句描述}
**为什么重要**：{1句}
**对我们意味着**：{1句可执行的行动建议——必须具体到"联系谁、卖什么、怎么做"，禁止写"值得关注""建议跟踪""持续观察"}
**来源**：{来源}

（2-5条，优先级品牌在前）

---

## 🧠 启示与行动
- {每条必须可操作——禁止空泛的方向性建议}
- {每条要能直接拿去执行}
```

## 关键规则
- **三信号**：固定3条，是全文最核心的信息浓缩
- **品牌动态**：每条必须有"对我们意味着"的行动建议——不能是"值得关注"，必须是"联系XX部门做XX"或"准备XX材料发给XX客户"
- **启示**：禁止写"值得关注""建议跟踪""持续观察"——每条必须是可执行的动作指令
- **SILENT规则**：如果经过充分搜索确认完全没有任何可用的品牌信息，输出 `[SILENT]`
- **Cron job 配置**：此 skill 必须在 cron job 创建时通过 `skills=["sports-marketing-intel"]` 声明，确保每次定时执行自动加载。否则 Agent 会丢失信息源矩阵和输出格式规范。

## 搜索方案：AnySearch MCP

> ⚠️ 2026.06.08 更新：mcp_minimax_web_search 已关闭，Playwright 已禁用。2026.06.09 更新：scrapling_fetch 和 Obscura 已废弃。搜索方案仅有 AnySearch MCP（Hermes config 中注册，通过 `mcp-remote` 代理）。

**AnySearch MCP** 暴露的 4 个工具：
- `mcp_anysearch_search` — 通用搜索（query 必填；可选 domain/sub_domain 做垂直领域搜索）
- `mcp_anysearch_batch_search` — 并行搜索 2-5 个 query，替代多次串行调用
- `mcp_anysearch_extract` — 抓取已知 URL 全文并转 Markdown
- `mcp_anysearch_get_sub_domains` — 获取垂直领域子分类

**⚠️ mcp_anysearch_extract 可靠性（2026.06.09 实测）**：
- 对国内新闻站点（sina.com.cn、163.com、36kr.com、21jingji.com、stcn.com）抓取成功率约 **50%**
- 失败返回 `extract_fetch_failed: all extract proxies exhausted`
- 不可完全依赖 extract 获取全文。搜索结果的 snippet 已包含足够信息和引文，可以直接使用
- PR-Newswire/美通社等 PR 发稿源抓取成功率高，优先 extract
- extract 连续 3 次失败时切换 URL 或直接依赖 snippet

**一日搜索工作流（推荐）**：
1. 第一波（搜索）：`mcp_anysearch_batch_search` 并行搜索 3-5 组关键词（按 P0 品牌或 `{赛事名} 品牌 营销 今日` 分组），每组返回前 10 条
2. 第一波（抓取）：对 PR-Newswire/美通社等高价值结果尝试 extract 获取全文
3. 第二波（补查）：针对搜索结果中发现的热点新品牌/突发话题（如 Nike 广告发布）再搜一组
4. 第三波（竞品/行业）：补查竞品平台动态和行业趋势文章
5. 汇总输出：按三层结构编写日报

**不使用的工具**：
- `browser_navigate` / `browser_click` / `browser_snapshot` — 会拉起 Chrome
- `delegate_task` — 已验证在 cron job 下 180s 超时，不可靠
- `mcp_scrapling_fetch` / Obscura — 已废弃
- Playwright MCP — 已禁用

**推荐搜索关键词模板**：
- 中文：`{品牌名} 世界杯 营销 {当前月份}`、`世界杯 营销 今日`
- 英文：`{Brand} World Cup 2026 campaign {Month}`
- 热点：`世界杯 品牌 营销 最新`, `World Cup sponsorship 2026 latest`

## 信息不足时的处理策略

当 AnySearch 大面积失败时：
- **不要输出 [SILENT]**，除非经过充分搜索确认完全没有任何可用的品牌信息
- **允许「趋势版」日报**：如果只有 1-2 条有价值信息，可以只输出 1-2 条品牌动态，不需要塞满 5 条
- **标注数据缺口**：明确告知用户哪些中文品牌/竞品动态未能覆盖

## 常见陷阱

### extract 失败时的降级
当 extract 工具大面积不可用时，不要反复重试同一 URL。直接从搜索 snippet 提取关键信息撰写日报——snippet 通常包含足够信息量。连续 3 次 extract 失败后应该切换 URL 而不是重试同一个。

### 与案例库的关系
有价值的品牌案例（含描述、关键数据、战略意义、对我们意味着）应在写日报的同时写入 `references/case-library-2026.md`。案例库是长期资产，日报是单次输出。两次日报覆盖了同一个品牌的不同阶段，需要去重或合并。
