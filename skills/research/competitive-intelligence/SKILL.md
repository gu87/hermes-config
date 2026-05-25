---
name: competitive-intelligence
description: Gather recent marketing/competitive intelligence (24h-7d window). Monitor brand sponsorships, campaign launches, social media trends. Produce structured briefings with source tables.
agents:
  - intelligence
  - hermes-internal
related_skills:
  - last30days
  - hermes-cron-management
---

# Competitive Intelligence Research

## When to Use This Skill

Use this when the task is:
- Gathering recent marketing/competitive intelligence (past 24h to 7d window)
- Monitoring brand sponsorship moves, campaign launches, social media trends
- Producing a structured briefing with source tables and judgment calls
- Running as a cron-delivered intelligence job
- Chinese-market sports/football marketing intelligence (懂球帝 context)

Do NOT use this for 30-day trend research — that is the `last30days` skill (uses a bundled Python engine with Reddit/X/Twitter sources).

## Source-Gathering Approach

### Primary Tool: Playwright Browser MCP + Google / Google News

**Why:** Google blocks curl/scrapling_fetch. Playwright browser MCP works reliably with JavaScript-rendered pages.

**24-hour filter URL:**

```
https://news.google.com/search?q=<encoded-query>&hl=en-US&gl=US&ceid=US:en&when=1d
```

For shorter windows, use `tbs=qdr:d` (past 24h) or `tbs=qdr:w` (past week) on the standard Google Search URL:

```
https://www.google.com/search?q=<query>&tbm=nws&tbs=qdr:d&hl=en-US
```

### Chinese-Language Research — Google News as Primary Entry Point

For Chinese marketing intelligence (懂球帝 / sports marketing context), bypass standard Google Search and go directly to Google News:

```
https://news.google.com/search?q=<encoded-Chinese-query>&hl=zh-CN&gl=CN&ceid=CN:zh-Hans
```

**Why:** Google News consistently returns Chinese-language results with readable snippet summaries even when the actual article pages are inaccessible (常见 404/付费墙/页面不存在). The snippet text alone often contains enough info for a daily briefing.

**When direct URL navigation fails (common pattern):**
- `sina.com.cn` links return "页面没有找到" (page not found). Google search result URLs are frequently truncated or use redirect wrappers that break.
- `163.com` links redirect to homepage instead of target article.
- `adage.com` articles return 404 — the URL from search results frequently leads to "Page not found".
- `designrush.com` links frequently redirect to 404 as articles get moved or deleted.
- `campaignasia.com`, `yicaiglobal.com` have paywalls.
- **What works**: Navigate to `thepaper.cn` articles directly — they are consistently readable without paywall.

**24-hour filter for Chinese queries:**

```
https://news.google.com/search?q=<query>&hl=zh-CN&gl=CN&ceid=CN:zh-Hans&when=1d
```

**Fallback:** If Google News returns few results for Chinese queries with `when=1d`, use standard Google search with `tbs=qdr:d` and `tbm=nws`:

```
https://www.google.com/search?q=<query>&tbm=nws&tbs=qdr:d&hl=zh-CN&gl=CN
```

### Query Strategy — Run Multiple Angles

Run 3-5 parallel queries covering different angles:

| Angle | Example Query |
|-------|------|
| Broad catch-all | `"World Cup" "2026" sponsor OR marketing OR campaign` |
| Brand/sponsor track | `World Cup 2026 sponsor official brand` |
| Campaign track | `FIFA World Cup 2026 campaign ad creative` |
| Social trend track | `World Cup 2026 social media marketing viral` |
| Chinese market | `世界杯 2026 营销 品牌 赞助` |
| Chinese brand-specific | `海信 世界杯 2026 营销` or `蒙牛 世界杯 2026` |
| Competitor track | `<competitor name> World Cup 2026 marketing` |

The broad `OR`-based catch-all query consistently returns the most results.

### Deep-Dive Workflow

For each promising article found:

1. Check source reliability: if it's a known-fragile source (sina, 163, adage, designrush, campaignasia, yicaiglobal), skip browser_navigate — the snippet is your best data.
2. For reliable sources (thepaper.cn, reuters, bloomberg): `browser_navigate(url)` to the article
3. `browser_snapshot()` to extract content
4. Look for: brand names, campaign names, agency partners, financial terms, key executive quotes, social media strategy components (UGC, influencer, viral mechanics)
5. Note the source's reliability
6. If browser_navigate returns 404 or paywall: return to search results and use snippet data. Do not retry or seek alternative URLs.

### Fallback: When Google Fails

**Google CAPTCHA/block pattern:** `browser_navigate` to Google or Google News may redirect to `google.com/sorry/` (CAPTCHA challenge page). This happens especially from headless browsers without residential proxies. When you see `google.com/sorry/` in the URL, **do not retry** — Google will continue blocking.

**Recommended fallback: Bing via Playwright**

```
https://www.bing.com/search?q=<url-encoded-query>&setlang=zh-cn
```

Bing consistently works with Playwright browser MCP and returns comparable results. For Chinese-language queries, use `setlang=zh-cn` and add `&filters=ex1%3a%22ez1%22` for time-based filtering.

**Bing's Chinese news index** is thinner than Google's but adequate for daily briefings on World Cup/domestic topics. Expect fewer specialist/ad-trade results (ADWEEK, LBBOnline) but sufficient mainstream news coverage.

**Additional fallback notes:**
- **MiniMax web_search API rate limit**: when it returns `usage limit exceeded` (error 2056), switch immediately to Playwright browser MCP. Do not retry MiniMax — it will remain exhausted for the session.
- **Chinese searches from China IP may return zero results** with `tbs=qdr:d` + Chinese keywords. Fall back to English queries or remove the time filter.
- **Google redirects to `google.com.hk`** from China IPs — cached `.hk` results may differ from `.com` results. This is usually fine but note the variance.
- **Rate limiting**: keep to 5-8 page loads per session; no rapid-fire navigation.
- **Sina finance URLs break frequently**: The redirect URL from search results often leads to "页面没有找到". If the first URL fails, move to the next source rather than retrying.

### Reliable Chinese News Sources (Deep-Dive Ready)

These sources consistently return readable article content via `browser_navigate` + `browser_snapshot`:

| Source | URL Pattern | Reliability | Notes |
|--------|-------------|-------------|-------|
| 腾讯新闻 (QQ.com) | `news.qq.com/rain/a/...` | High | Full article text readable; heavy page elements (sidebars, ad slots) but main article content is accessible |
| 澎湃新闻 (thepaper.cn) | `thepaper.cn/newsDetail_*` | High | Already documented in skill — consistently readable |
| 北京日报 (BJD.com.cn) | `news.bjd.com.cn/...` | High | Reliable access |
| 直播吧 (zhibo8.com) | `news.zhibo8.com/...` | Medium | Sports news aggregator; readable |
| CCTV | `tv.cctv.com/...` | High | Official broadcaster — reliable |
| 央视广告频道 | `1118.cctv.com/...` | High | CCTV advertising/marketing channel; publishes World Cup media plans, sponsor event coverage (总台总经理室). Critical source for sponsor intelligence: content matrix, program sponsorship inventory, 300+ attendee lists |

**Sources that remain snippet-only** (as already documented): sina.com.cn, 163.com, campaignasia.com, adage.com, yicaiglobal.com, designrush.com — do not attempt deep-dive.

### Reliable English Sources (Deep-Dive Ready)

These English-language sources consistently return readable article content. Add to this list as new sources are verified:

| Source | URL Pattern | Reliability | Notes |
|--------|-------------|-------------|-------|
| ESPN | `espn.com/soccer/story/_/id/...` | High | Full article text readable; paywall on some features but news stories are accessible |
| SB Nation | `*.sbnation.com/...` | Medium-High | Sports blog network (Vox Media). Article text fully readable; heavy page elements (sidebars, widgets) but main content accessible |
| Branding in Asia | `brandinginasia.com/...` | Medium | Marketing trade publication; readable |
| Reuters | `reuters.com/...` | High | Full article; may have paywall after N articles |
| Bloomberg | `bloomberg.com/...` | High | Paywall on most articles; use snippet for deep content |

**SB Nation verification note (2026-05-25):** Article loaded fully via Google News redirect without paywall, CAPTCHA, or 404. Navigation path: Google News search → `browser_navigate(google_news_read_url)` → auto-redirect to `cominghomenewcastle.sbnation.com` → full article readable.

## Source Reliability Scale

| Level | Description | Examples |
|-------|-------------|---------|
| High | Breaking news, exclusive access, primary source interviews | WWD, ADWEEK, Bloomberg, Reuters, thepaper.cn (澎湃新闻) |
| Medium | Official announcements, press release republication, industry trade | FOX Sports, LBBOnline, SportsPro, Forbes, jiemian.com (界面新闻), dongqiudi.com (懂球帝), finance.sina.com.cn (新浪财经), tmtpost.com (钛媒体) |
| Low | Opinion/analysis pieces, aggregators, republished press releases | Drug Store News, RetailWire, Brand Innovators, eastmoney.com (东方财富) |
| Unlabeled | Source not checked in this run — label explicitly | — |

Label unavailable sources in the source table (e.g., "X/Twitter: unavailable without credentials").

## Report Format

### Format A: Three-Tier Daily Briefing (推荐用于定时早/晚报)

适用于 cron 自动推送的每日简报。设计原则：三种读法（30秒→2分钟→5分钟），每条信号带行动建议。

```markdown
# 🏆 懂球帝世界杯营销日报 | {日期} {早报/晚报}

## 📌 今日三信号
> ① {最重要的一条}
> ② {第二条}
> ③ {第三条}

---

## 📰 品牌动态

### 1. {品牌名} {动作}
**时间**：{时间}
**动作**：{2-3句描述}
**为什么重要**：{1句}
**对我们意味着**：{1句可执行的行动建议}
**来源**：{来源}

（2-5条，按P0→P1→P2优先级排列）

---

## 🧠 启示与行动
- {具体可执行的建议}
- {每条能直接拿去用，不做「值得关注」「建议跟踪」这类空话}
```

**Format A 规则：**
- 「三信号」固定3条，是全文核心。读者只看这3条就能掌握大局
- 「品牌动态」每条必须包含「为什么重要」和「对我们意味着」
- 「启示与行动」每条必须可操作。❌ 「值得关注」「建议跟踪」 ✅ 「百威双星模式可推给蒙牛，周二前出一版概念」
- 无新信息时输出 `[SILENT]`

### Format B: One-Shot Research Briefing (用于按需深度调研)

```markdown
# 【标题】<Topic> - YYYY.MM.DD

## 【摘要】
- 动态1: ...
- 动态2: ...
- 动态3: ...
(3-5 key findings)

## 【关键变化】
- **变化1**：<What changed + implication for strategy>
- **变化2**：<What changed + implication>

## 【来源】
| 来源 | 时间 | 链接 | 备注 |

## 【判断】
- **是否需要关注**：是 / 否
- **建议后续动作**：
  1. ...
  2. ...
  3. ...
```

## Steps

1. **Understand scope** — time window (24h/7d/30d), topic (World Cup / industry / competitor), delivery method (cron vs on-demand)
2. **Define P0/P1/P2 brand priority** (for cron briefings):
   - **P0** — 合作客户 + 世界杯官方赞助商 + 足球品牌。这些是重点监控对象，品牌动态中优先报道
   - **P1** — 竞品媒体/平台。其他体育媒体的世界杯营销动作
   - **P2** — 行业趋势。营销创新案例、品牌合作新模式
3. **Run 3-5 parallel queries** covering different angles using browser_navigate. P0 brands get dedicated queries. P1/P2 are caught by broader sweeps.
4. **Snapshot each result page** and extract headlines
5. **Deep-dive into 3-5 most relevant articles** using browser_navigate. Prefer P0 brand articles.
6. **Compile findings** organized by theme/change, not by source. P0 findings go first.
7. **Assess source reliability** — distinguish sourced findings from interpretation
8. **Format output** as structured briefing (Format A for daily cron, Format B for one-shot research)
9. **If cron-delivered**: output the briefing directly (no file save needed — the cron system delivers the response text)

### 早/晚报拆分模式

对于每日定时的竞品情报，推荐早晚两次抓取以覆盖全球时区：

| 报次 | 时间 | 覆盖范围 |
|------|------|---------|
| 早报 | 08:30 | 欧美夜盘（美股收盘到亚洲开盘）+ 前一天亚洲未覆盖信息 |
| 晚报 | 18:00 | 中国日盘 + 欧洲上午动态 |

两个 cron job 使用相同的 prompt 模板（仅 `{早报/晚报}` 标记不同），时间窗口均为过去12小时。

## Common Pitfalls

- scrapling_fetch does NOT work for news gathering — consistently times out on Google (curl error 28), then marks the MCP server as "unreachable" after 3 consecutive failures, blocking further use for the entire session. Always use Playwright browser MCP from the start. After the first timeout, switch immediately — do not retry.
- Google News snapshots are text-only — images and video embeds cannot be extracted from snapshots
- Timestamps are relative — "3 days ago" means relative to crawl time, not absolute. Multiple relative timestamps in one report may confuse if cross-referenced later
- Chinese language searches from China IP may have lower recall — Google News' Chinese index is thinner; supplement with English queries
- Don't over-query — 5-8 page loads max per session to avoid rate limiting
- Don't re-ask the user — cron jobs have no user present; make reasonable decisions on scope and depth
- **"Stay on search results" technique**: After browser_navigate to Google search results, read article summaries from the browser_snapshot directly. Individual article links (sina.com.cn, 163.com, adage.com, campaignasia.com, designrush.com) frequently return 404, redirect to homepage, or hit paywalls. The search result snippets alone contain 70-80% of actionable intelligence for a daily briefing. Only deep-dive articles from reliably accessible sources (thepaper.cn, reuters.com, bloomberg.com).
- When a browser_navigate to an external article returns 404 or paywall, do NOT waste turns trying alternative routes. Return to the search results page and use snippet data.
- Chinese news site URL fragility: sina.com.cn, 163.com URLs from Google search results frequently return "页面没有找到" or redirect to homepage. Prefer thepaper.cn articles which are reliably readable. For paywalled sources (campaignasia.com, yicaiglobal.com, adage.com), the Google News snippet may be your best data source.
- Google News "展开" button is fragile: Clicking the expand button on a Google News article card may fail with Playwright (both ref= and text= selectors). Do not fight it — instead, use browser_navigate with the full Google News read URL (https://news.google.com/read/... from the link's href). This auto-redirects to the actual article page for many sources. If the redirect works, you get full article text. If it fails (404/paywall), fall back to snippet data.
- Google News when=1d filter is directional, not strict: Google News' time filter is approximate — especially for Chinese-language queries, it frequently returns results from 4 to 21+ days ago. Do not dismiss older articles that appear within this filter; they are often the best available intelligence for a narrow window. Supplement Chinese queries with English searches (which have stricter time filtering) to find truly recent items.
- same_tool_failure_warning (3+ consecutive failures of the same tool) is a signal to change approach immediately, not retry.

## Related Skills

- `last30days` — 30-day community/social trend research (uses bundled Python engine, different source coverage)
- `hermes-cron-management` — cron job lifecycle and troubleshooting

## Reference Files

- `references/world-cup-daily-briefing-cron-template.md` — 懂球帝世界杯营销日报 cron prompt 模板（三层结构 + P0/P1/P2 + 早/晚报拆分）
- `references/world-cup-2026-05-25-session.md` — 2026-05-25早报session记录：搜索查询、关键发现、FIFA赞助商层级体系知识库、工具使用经验
- `references/world-cup-2026-05-23-session.md` — 2026-05-23 session记录
- `references/world-cup-2026-05-16-session.md` — 2026-05-16 session记录
- `references/world-cup-2026-05-14-session.md` — 2026-05-14 session记录
