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
- **Technical / product competitive intelligence**: GitHub repo comparisons, feature matrices, open-source project landscapes, Desktop App enhancer ecosystems, AI coding tool competitive research

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

### Best Discovery Method for Last-24h English News: Bing News + Scrapling Stealth

**Verified 2026-06-01:** Bing News via `mcp_scrapling_fetch` stealth mode is currently the most reliable method for finding fresh (sub-24h) English-language World Cup marketing news. It found Forbes (5h old) and Communicate Online (21h old) when Google News RSS had only stale results.

**Bing News search URL pattern:**

```
https://www.bing.com/news/search?q=<url-encoded-query>&qft=interval%3d%227%22&form=YFNR
```

**Key parameters:**
- `qft=interval%3d%227%22` = past 24 hours (use `%228%22` for 7 days)
- `qft=sortbydate%3d%221%22` = sort by most recent instead of best match
- Append `&form=YFNR` to avoid the base-URL redirect to Bing homepage

**Query strategy that works:** Use P0 brand names directly in the query string rather than generic keywords. Example query that found 5h-old Forbes article: `World+Cup+2026+sponsor+adidas+nike+budweiser+campaign`. The broad OR-like matching catches articles mentioning any of those brands, surfacing content even when the target article doesn't mention all query terms.

**Why Bing over Google News RSS:** Google News RSS (`news.google.com/rss/search`) consistently returns articles from 3+ days ago — it is useful for archival research but NOT for real-time discovery. Google News RSS should be treated as a secondary/archival source.

**Why scrapling over Playwright browser for Bing:** `mcp_scrapling_fetch` with stealth mode returns readable search result text with article headlines, timestamps, and snippet summaries — no JavaScript execution overhead. Playwright browser `browser_navigate` to Bing works but requires additional `browser_snapshot` calls and returns noisy YAML with site chrome.

### Chinese-Language Research — Baidu News as Primary Entry Point (Recommended)

**Preferred first stop for Chinese marketing intelligence.** Baidu News via Playwright browser is faster and more reliable than Google News for Chinese-language queries. It consistently returns recent content (within 24-48h) with readable summaries in the snapshot YAML — no CAPTCHA, no redirect failures, no `google.com/sorry/`.

**24-hour filtered Baidu News URL pattern:**

```
https://www.baidu.com/s?wd=<url-encoded-query>&tn=news&rtt=4
```

Where `rtt=4` is the 24-hour time filter. Without `rtt`, results span weeks/months.

**Snapshot format:** Baidu News returns a YAML snapshot with each article as a `generic` block containing:
- `heading` with title text + link URL
- `generic` block with relative timestamp (e.g. "昨天17:41", "5天前") + summary snippet
- Source link (e.g. "同花顺财经", "新浪财经", "钛媒体APP")

**Extraction strategy:**
1. Navigate to Baidu News with `rtt=4`
2. `browser_snapshot()` — headlines and summaries are fully extractable from the YAML
3. For deep dives: use Scrapling `s_fetch_page` basic mode on article URLs from known-reliable sources (thepaper.cn, huxiu.com, baijiahao.baidu.com with正规媒体 publisher). For untrusted自媒体 on baijiahao or fragile sources (新浪财经/163), use snippet data — don't navigate.
4. Run multiple angle queries (see Query Strategy table below)
5. **Baidu News snapshot is self-sufficient for ~80% of briefing content** — only deep-read the 2-3 most critical articles (verified 2026-05-27 evening session)

**Why Baidu over Google for Chinese:** Google News' Chinese index (`hl=zh-CN&gl=CN`) is thin and inconsistent — especially for niche topics like sports sponsorship. Baidu News has deeper Chinese coverage and no CAPTCHA risk.

### Google News — Secondary for Cross-Validation

For English-language queries or cross-validating Chinese findings against an international source:

```
https://news.google.com/search?q=<encoded-Chinese-query>&hl=zh-CN&gl=CN&ceid=CN:zh-Hans
```

**Why:** Google News returns Chinese-language results with readable snippet summaries even when the actual article pages are inaccessible (常见 404/付费墙/页面不存在).

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
| Competitor track | `<competitor name> World Cup 2026 marketing` or `<competitor name> 世界杯 2026 营销` | 竞品沉默本身就是信号——0结果=竞品在世界杯营销层面静默，懂球帝占据先发优势，应写入日报「竞品动态」板块 |

The broad `OR`-based catch-all query consistently returns the most results.

### Deep-Dive Workflow

For each promising article found:

1. Check source reliability: if it's a known-fragile source (sina, 163, adage, designrush, campaignasia, yicaiglobal), skip browser_navigate — the snippet is your best data.
2. For reliable sources (thepaper.cn, reuters, bloomberg): `browser_navigate(url)` to the article
3. `browser_snapshot()` to extract content
4. Look for: brand names, campaign names, agency partners, financial terms, key executive quotes, social media strategy components (UGC, influencer, viral mechanics)
5. Note the source's reliability
6. If browser_navigate returns 404 or paywall: return to search results and use snippet data. Do not retry or seek alternative URLs.

### Fallback: When Google Fails — Toolset-Unavailable (Offline) Mode

**Scenario:** The 晚报 cron job (18:00) may run in a subagent session with only file/skill-management tools — no `web_search`, `browser_navigate`, `mcp_playwright`, or `mcp_scrapling_fetch`. This happens when the subagent's toolset is restricted (e.g., `enabled_toolsets: [\"file\"]`), or when the primary agent has already exhausted web-search resources earlier in the day.

**Offline fallback workflow — use `references/` session records as primary data source:**

1. **Load the most recent session record(s)** from the skill's `references/` directory using `skill_view(name='competitive-intelligence', file_path='references/world-cup-YYYY-MM-DD-session.md')`
2. **Check what the most recent session already found** — the morning session records contain search logs, key findings, and tool usage notes. These are usually sufficient for a 晚报 update because:
   - The 晚报 window (6h from morning run) rarely produces major breaking news
   - Cross-verification and deeper analysis add more value than fresh search
3. **Harvest OpenChronicle event logs for real-time internal intelligence** — When OpenChronicle is running (screen-capture plugin), the daily event log (`event-YYYY-MM-DD.md`) under `~/Library/Mobile Documents/iCloud~md~obsidian/Documents/个人知识库/3-知识/wiki/OpenChronicle记忆/` contains raw Feishu chat captures, MCN platform activity, and internal brand discussions. This is a **primary offline intelligence source** that web search cannot match:

   a. **Read today's event log first** — use `read_file` to scan for brand keywords in recorded Feishu messages (耐克、蒙牛、伊利、安慕希、百威、小米、比亚迪、剑南春、世界杯、赞助). The event log captures visible_text from Feishu group chats even when you lack web/browser tools.

   b. **Search across event logs using OpenChronicle MCP tools** (when available via `mcp_openchronicle_search_captures`) — query past 24h for brand keywords to find execution-level intel that web search can't reach.

   c. **Extract execution-level intel from Feishu captures** — typically contains:
      - Brand partnership group chats (e.g. 耐克合作, 营销中心沟通群) — real-time discussions on resource placement, image specs, launch timelines
      - MCN platform captures (e.g. mcn.mgcc.com.cn orders) — KOL campaign orders with brand names, budgets, delivery dates
      - Note source reliability: internal captures are HIGH for execution intel but may not be public yet — tag as "飞书内部群聊捕获" in the source table

   d. **飞书审批中心 (Feishu Approval Center) — HIGH-value intelligence source** (verified 2026-05-27): The Approval Center (`飞书审批`) captures deal-level information before it becomes public:
      - Payment approvals show confirmed amounts and client names (e.g., "网易实况足球世界杯合作-80万", "付款审批-百威10.6万")
      - Qualification requests (资质申请) reveal which clients are executing orders and need stamped documentation
      - Travel/expense approvals hint at field activity (e.g., World Cup on-site teams)
      - Scan for keywords: "审批", "付款", "资质", "回款主体", "世界杯" in approval titles

   e. **微信文件预览 (WeChat File Preview) — pre-public partnership docs** (verified 2026-05-27): Strategic cooperation documents opened in WeChat (e.g., "比亚迪X懂球帝美加墨世界杯战略合作权益说明.xlsx") reveal partnership terms, payment schedules, and activation timelines before any public announcement. When OpenChronicle captures a WeChat file preview with a brand+世界杯 filename, treat it as HIGH-confidence execution intel.

4. **Cross-verify with local project files** — search the user's Desktop/ project directories and Obsidian vault for brand-related files:
   ```python
   # Look for brand project files that may contain execution-level intel
   search_files(pattern='*百威*', path='/Users/gu/Desktop', target='files')
   search_files(pattern='*世界杯*', path='/Users/gu/Library/Mobile Documents/iCloud~md~obsidian', target='files')
   ```
   Local project files may reveal ad orders, content calendars, or partnership docs not yet announced publicly — offering execution-level intel that web search can't capture.

5. **Cross-day pattern recognition** (verified 2026-05-30): When reading event logs for a 24h briefing window, scan **two calendar days** (e.g., May 29 + May 30 for a May 30 evening briefing). Cross-day patterns indicate sustained execution activity:
      - Same brand/file appearing on consecutive days = higher confidence the deal is actively moving
      - Same person discussing same topic across days = timeline is being tracked
      - Payment mentions on Day 1 + follow-up on Day 2 = payment likely processed
      - Example: 剑南是 file appeared in Feishu chat on May 29 and was viewed again on May 30, confirming sustained execution

6. **产品开发信号 (Product Development Signals) — platform capability intel** (verified 2026-05-30): For platform-side marketing teams, product development signals are as valuable as brand signals. Watch for:
      - New tab launches (世界杯tab, 竞猜tab) — affect client resource placement and pitch strategy
      - New livestream/feature capabilities (多美女直播, 互动功能) — become new brand sponsorship inventory
      - Ad product changes (新广告位, 新增资源位规格) — directly impact刊例和客户报价
      - Tag as P1 or P2 depending on immediate client relevance; these signals help the team pitch "我们有XX新功能可以给您做网友互动"

7. **Analyze gaps** — what does the morning session NOT have that the user would expect?
   - P0 brands that weren't covered: search their directory for files
   - Time-sensitive events (cron jobs, sales, deadlines): check `~/.hermes/cron/jobs.json`

6. **Compile with explicit freshness labeling** — tag each finding with when it was first discovered (not when it's being reported). Distinguish three data tiers:
   - **Fresh (today's capture)**: extracted from today's event log or live Feishu activity — highest value
   - **Session-confirmed**: carried forward from this morning's session record, no new signals
   - **Archived intel**: from earlier days' session records — label clearly with original discovery date

7. **Output [SILENT]** only if ALL sources return nothing: recent session records are empty AND local file search found nothing AND OpenChronicle event log has no brand mentions. Otherwise produce the briefing with clear source-footnotes and freshness tags.

**Rationale:** The competitive-intelligence `references/` directory IS the durable record of past research sessions. A 晚报 cron job running in tool-restricted mode should treat these records as a "research cache" rather than failing silently. The user gets value from the 晚报 even without live search — the 晚报's job is consolidation and cross-verification, not original discovery.

**Google CAPTCHA/block pattern:** `browser_navigate` to Google or Google News may redirect to `google.com/sorry/` (CAPTCHA challenge page). This happens especially from headless browsers without residential proxies. When you see `google.com/sorry/` in the URL, **do not retry** — Google will continue blocking.

**Recommended fallback when Google + Playwright work: Bing via Playwright**

```
https://www.bing.com/search?q=<url-encoded-query>&setlang=zh-cn
```

Bing consistently works with Playwright browser MCP and returns comparable results. For Chinese-language queries, use `setlang=zh-cn` and add `&filters=ex1%3a%22ez1%22` for time-based filtering.

**Bing's Chinese news index** is thinner than Google's but adequate for daily briefings on World Cup/domestic topics. Expect fewer specialist/ad-trade results (ADWEEK, LBBOnline) but sufficient mainstream news coverage.

**Additional fallback notes:**
- **MiniMax web_search API rate limit**: when it returns `usage limit exceeded` (error 2056), switch immediately to Playwright browser MCP. Do not retry MiniMax — it will remain exhausted for the session.
- **Google tbs=qdr:d Chinese search may return zero results** with `tbs=qdr:d` + Chinese keywords. Fall back to English queries or remove the time filter.
- **竞品搜索零结果是信号，不是失败** (2026-05-31 验证)：当百度新闻 rtt=4 对竞品关键词返回 0 结果时（如直播吧/虎扑/腾讯体育+世界杯），这本身就是一条情报——说明竞品在世界杯营销层面处于静默期。不要当作搜索失败处理，应写入日报「竞品动态」或「竞品沉默」板块。
- **But this is NOT always true**: 2026-05-25 verified that Google search with `tbs=qdr:d&hl=zh-CN` for Chinese queries (世界杯 营销 蒙牛 百威 海信 2026) returned fresh results including 虎嗅 (4h ago), 网易 (3h ago). The key is using `google.com.hk` + `hl=zh-CN` (not Google News' Chinese index). Try standard Google Search with `tbs=qdr:d&hl=zh-CN` before falling back.
- **Google redirects to `google.com.hk`** from China IPs — cached `.hk` results may differ from `.com` results. This is usually fine but note the variance.
- **Rate limiting**: keep to 5-8 page loads per session; no rapid-fire navigation.
- **MiniMax web_search rate limit fallback (multi-channel parallel)**: When `mcp_minimax_web_search` returns `API Error: 2056-usage limit exceeded`, do NOT retry or wait. Immediately launch all three backup channels in parallel: (1) `delegate_task` to Intelligence agent (has separate web tool quota), (2) Playwright browser `browser_navigate` to Google search results, (3) `mcp_scrapling_fetch` to scrape known-reliable article URLs from search result snippets. This triple-channel approach produced a complete briefing on 2026-05-25 with zero web_search calls. Each channel covers the others' blind spots: Intelligence agent can access Obsidian/project files, Playwright gets search results, Scrapling deep-reads articles.
- **Sina finance URLs break frequently**: The redirect URL from search results often leads to "页面没有找到". If the first URL fails, move to the next source rather than retrying.

### Reliable Chinese News Sources (Deep-Dive Ready)

These sources consistently return readable article content via `browser_navigate` + `browser_snapshot`:

| Source | URL Pattern | Reliability | Notes |
|--------|-------------|-------------|-------|
| 腾讯新闻 (QQ.com) | `news.qq.com/rain/a/...` | High | Full article text readable; heavy page elements (sidebars, ad slots) but main article content is accessible |
| 澎湃新闻 (thepaper.cn) | `thepaper.cn/newsDetail_*` | High | Already documented in skill — consistently readable. ⚠️ URL must be verified; wrong newsDetail URLs may redirect to unrelated articles |
| 北京日报 (BJD.com.cn) | `news.bjd.com.cn/...` | High | Reliable access |
| 直播吧 (zhibo8.com) | `news.zhibo8.com/...` | Medium | Sports news aggregator; readable |
| CCTV | `tv.cctv.com/...` | High | Official broadcaster — reliable |
| 央视广告频道 | `1118.cctv.com/...` | High | CCTV advertising/marketing channel; publishes World Cup media plans, sponsor event coverage (总台总经理室). Critical source for sponsor intelligence: content matrix, program sponsorship inventory, 300+ attendee lists |
| 虎嗅 (Huxiu.com) | `huxiu.com/article/...` | High | 商业/科技深度分析。微信公众号「深响」等作者常驻。全文可通过 Scrapling `s_fetch_page` 完整读取（已验证 2026-05-25），无付费墙拦截。适合做趋势分析和行业评论内容 |
| 网易公众号转载 (163.com/dy) | `163.com/dy/article/...` | Medium | 微信公众号文章在网易的转载镜像。可通过 Google 搜索结果 snippet 获取摘要，全文抓取偶尔成功 |
| 百度百家号 (baijiahao.baidu.com) | `baijiahao.baidu.com/s?id=...` | Medium-High | 百度内容平台，大量正规媒体（红星新闻、北青网、封面新闻等）在此发布。**可通过 Scrapling `s_fetch_page` basic mode 直接全文抓取**（已验证 2026-05-27：咪咕官宣文章 2161 字符 100% 检索）。注意：百家号上既有正规媒体也有自媒体——检查发布者身份判断可靠性，正规媒体标记为 High，自媒体/企业号标记为 Medium |

**Sources that remain snippet-only** (as already documented): sina.com.cn, 163.com (主站), campaignasia.com, adage.com, yicaiglobal.com, designrush.com, fastcompany.com, jdsupra.com — do not attempt deep-dive. Fast Company returns empty content via scrapling (0 chars, not 404). JD Supra returns generic 404 for Bing-news-linked article URLs.

### Reliable English Sources (Deep-Dive Ready)

These English-language sources consistently return readable article content. Add to this list as new sources are verified:

| Source | URL Pattern | Reliability | Notes |
|--------|-------------|-------------|-------|
| ESPN | `espn.com/soccer/story/_/id/...` | High | Full article text readable; paywall on some features but news stories are accessible |
| SB Nation | `*.sbnation.com/...` | Medium-High | Sports blog network (Vox Media). Article text fully readable; heavy page elements (sidebars, widgets) but main content accessible |
| Branding in Asia | `brandinginasia.com/...` | Medium | Marketing trade publication; readable |
| Reuters | `reuters.com/...` | High | Full article; may have paywall after N articles |
| Bloomberg | `bloomberg.com/...` | High | Paywall on most articles; use snippet for deep content |
| Australian FinTech | `australianfintech.com.au/...` | Medium | Finance/marketing trade publication. Full article text readable via Scrapling `s_fetch_page`. Verified 2026-05-25 with Visa World Cup campaign article. |
| Campaign Asia | `campaignasia.com/article/...` | Medium | Marketing trade (Haymarket). Full article readable via Scrapling `s_fetch_page` with markdown format. May truncate long articles (>8000 chars). Verified 2026-05-25 with Verizon/TikTok/Home Depot World Cup article. |
| SportsPro | `sportspro.com/news/...` | High | Sports business trade publication. Full article accessible via Scrapling `s_fetch_page` basic mode (no JS required for article text). May truncate >10K chars — use `start_index` to fetch remainder. Listing pages (`/sponsorship-marketing/`) are also readable. Hot-linked related posts in article body surface additional stories. Verified 2026-05-27 with FIFA Fan ID article (26 May) and FIFA-CCTV deal article (18 May). |
| Communicate Online | `communicateonline.me/insights/...` | Medium | MENA marketing trade publication. Found via Bing News search; articles relevant to global brand marketing. Full article may timeout on scrapling (30s) — use Bing News snippet for briefing content. Verified 2026-06-01 with World Cup 2026 marketing battleground article. |

**Snippet-only sources** (do not attempt deep-dive): Forbes (cookie wall blocks full content after headline — Bing News snippet is adequate for daily briefing), Fast Company (returns 0 chars via scrapling), JD Supra (returns generic 404 for Bing-linked URLs), AdAge (paywall/timeout), **MSN/WWD** (scrapling stealth returns empty content with only "Continue reading" buttons — 2026-06-02 verified), **Yahoo Finance** (geo-blocked from mainland China; snippet sufficient for daily briefing — 2026-06-02 verified).

**SB Nation verification note (2026-05-25):** Article loaded fully via Google News redirect without paywall, CAPTCHA, or 404. Navigation path: Google News search → `browser_navigate(google_news_read_url)` → auto-redirect to `cominghomenewcastle.sbnation.com` → full article readable.

## GitHub & Technical Competitive Intelligence

When the research target is **open-source projects, technical tools, Desktop App enhancers, or AI coding agents** (rather than brand marketing), the source-gathering approach shifts from news sites to code repositories and technical communities.

### Primary Sources

| Source | What it provides | Reliability |
|--------|----------------|-------------|
| **GitHub Search API / `gh search repos`** | Repo stars, forks, last-update, README content, issue activity | High (for official repos) |
| **GitHub Topics** (`topic:codex-cli`, `topic:claude-code`) | Curated project lists | High |
| **Local filesystem scan** (`search_files` on user's machine) | Discover related projects the user already has cloned | Very High (confirmed local existence) |
| **README & source code** (`read_file`) | Feature confirmation, architecture details | Very High |
| **Comparison articles** (Dev.to, Hacker News, Reddit) | Community sentiment, feature comparisons | Medium |
| **MCP registries** | Claude Code / Codex CLI integrations | Medium-High |

### Research Workflow

1. **Local scan first** — Search user's filesystem for related projects (`search_files` with regex keywords)
2. **Read local READMEs** — Confirm feature sets and architectures
3. **Knowledge-base cross-reference** — Map discovered projects against known ecosystem players (Cline, Aider, Continue.dev, Roo Code, Cursor, Windsurf, Zed, etc.)
4. **Build comparison matrix** — Categories: direct competitors, CLI wrappers, multi-model orchestrators
5. **GitHub live verification** (when terminal is available) — Run `gh search repos` queries to confirm stars and discover new entrants
6. **Assess competitive barriers** — Technical differentiation, ecosystem lock-in, official-app dependency

### Comparison Table Format

For technical competitive research, use a feature-oriented table:

```markdown
| Project | Platform | Stars | Description | Key differentiators vs target |
```

Include at minimum:
- **Platform / language** — Rust, TypeScript, Python, etc.
- **Architecture** — IDE plugin, standalone app, CLI wrapper, Desktop enhancer
- **Model support** — Single-model (Codex only) vs multi-model (Codex + Claude + Gemini + ...)
- **Enhancement method** — CDP injection, source modification, standalone client, CLI bridge

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
- **竞品沉默即信号**：当竞品搜索返回0结果时，这是有价值的情报——应在品牌动态与启示之间插入「🔍 竞品动态」板块，用1-2句说明竞品在世界杯营销层面的静默/活跃状态。❌ 不写「暂无竞品动态」 ✅ 「24小时内竞品世界杯营销零动作，懂球帝占据先发窗口」
- **当有内部情报时**（飞书群聊/审批/MCN/微信文件），在「启示与行动」之前加一节「📊 飞书内部执行情报」表格，汇总所有内部捕获的执行级信息（品牌、金额、时间节点、来源群/审批号、捕获时间）。这是offline fallback模式下最有价值的差异化内容。
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

| 报次 | 时间 | 覆盖范围 | 预期工具集 |
|------|------|---------|-----------|
| 早报 | 08:30 | 欧美夜盘（美股收盘到亚洲开盘）+ 前一天亚洲未覆盖信息 | 全工具（web_search, browser, terminal, file） |
| 晚报 | 18:00 | 中国日盘 + 欧洲上午动态 | 可能受限（仅 file/skill-management 工具） |

**关键设计原则：**
- **早报做原创新闻发现** — 所有 web search、browser 抓取、原文深读都放在早报
- **晚报做交叉验证 + 深度分析** — 利用早报 session records + 本地项目文件。晚报可以不跑任何 web search 而产出有价值的 briefing
- **⚠️ 工具可用时晚报也可做原创发现** (2026-05-27 验证)：当 Playwright Browser 在晚报 session 可用时，Baidu News rtt=4 + Scrapling 深读可产出不亚于早报的原创内容。早/晚报的角色由工具集决定，不由时间决定——判断依据是 session 中实际可用的工具，不是报次标签。
- 两个 cron job 使用相同的 prompt 模板（仅 `{早报/晚报}` 标记不同），时间窗口均为过去12小时

## Signal Patterns to Watch For

These are recurring intelligence patterns that, when spotted, generate high-value briefing content and actionable recommendations:

- **Non-traditional sponsor activation** (verified 2026-06-02 with Dove case): When a brand from outside the traditional World Cup categories (beer, auto, electronics, sportswear) activates sponsorship with a social-issue angle rather than match-centric content. Dove ("The Game Is Ours," girl sports confidence) is the archetype — personal care brand + values-based messaging. These are high-value briefing items because (a) they signal sponsor roster diversification, (b) their social-issue angle is a reusable proposal template for懂球帝 clients with female/family demographics (伊利, 小米生态链). Tag as P1, extract the campaign name and angle, and suggest a 复盘 memo for the client-facing team.

- **Automotive sponsor activation** (verified 2026-06-02 with Hyundai): When a car brand sponsor launches a named, multi-channel campaign (TV + social + experiential). Hyundai "Next Starts Now" is the archetype. These directly inform pitches to 比亚迪 (P0 client). Extract: campaign name, channels used, CMO quotes, and produce a one-page competitor analysis for the client team within the briefing's 启示与行动 section.

- **Retail terminal activation** (verified 2026-06-02 with Korea): When retailers in a market begin World Cup-themed consumer promotions (beer, snacks, watch-party essentials). This signals the "last mile" of sponsorship activation and confirms commercial timelines. Use to trigger outreach to P0 FMCG clients (百威, 蒙牛, 伊利).

- **Competitor silence window** (verified across 2026-05-31, 2026-06-02): When all P1 competitor searches return zero fresh results within 24h. This is NOT a search failure — it's a competitive advantage signal. Write into briefing as "竞品在世界杯营销层面处于完全静默状态，懂球帝占据内容+商务双重先发窗口" and pair with a content-density recommendation for the editorial team.

## Common Pitfalls

- **早报/晚报 toolset asymmetry**: The 早报 cron job (08:30) typically has full web/browser toolset. The 晚报 cron job (18:00) may run with restricted tools (file-only) due to subagent configuration. **Plan for this**: put original discovery in 早报, make 晚报 a cross-verification + deeper analysis run that works offline using session reference files and local project directories.
- scrapling_fetch basic mode: Historically unreliable for news gathering (times out on Google, marks server as "unreachable"). HOWEVER (verified 2026-05-27): basic mode WORKS on WordPress-based trade publications that don't require JS for content delivery — specifically SportsPro (sportspro.com). Use this as a direct-article retrieval tool, NOT as a search engine. Navigate to known article URLs directly; do NOT use scrapling with search engines (Bing/Google/Yahoo — all either return garbage results or time out). Stealth mode requires Playwright and will likely fail with a "Playwright not installed" error — fall back to basic mode or skip.
- Google News snapshots are text-only — images and video embeds cannot be extracted from snapshots
- Timestamps are relative — "3 days ago" means relative to crawl time, not absolute. Multiple relative timestamps in one report may confuse if cross-referenced later
- Chinese language searches from China IP may have lower recall — Google News' Chinese index is thinner; supplement with English queries
- Don't over-query — 5-8 page loads max per session to avoid rate limiting
- Don't re-ask the user — cron jobs have no user present; make reasonable decisions on scope and depth
- **"Stay on search results" technique**: After browser_navigate to Google search results, read article summaries from the browser_snapshot directly. Individual article links (sina.com.cn, 163.com, adage.com, campaignasia.com, designrush.com) frequently return 404, redirect to homepage, or hit paywalls. The search result snippets alone contain 70-80% of actionable intelligence for a daily briefing. Only deep-dive articles from reliably accessible sources (thepaper.cn, reuters.com, bloomberg.com).
- When a browser_navigate to an external article returns 404 or paywall, do NOT waste turns trying alternative routes. Return to the search results page and use snippet data.
- Chinese news site URL fragility: sina.com.cn, 163.com URLs from Google search results frequently return "页面没有找到" or redirect to homepage. Prefer thepaper.cn articles which are reliably readable (but verify the URL — wrong newsDetail URLs redirect to unrelated articles). For paywalled sources (campaignasia.com, yicaiglobal.com, adage.com, fastcompany.com, jdsupra.com), the Google/Bing News snippet may be your best data source. Fast Company returns empty via scrapling (0 chars), JD Supra returns generic 404 — both are snippet-only.
- Google News "展开" button is fragile: Clicking the expand button on a Google News article card may fail with Playwright (both ref= and text= selectors). Do not fight it — instead, use browser_navigate with the full Google News read URL (https://news.google.com/read/... from the link's href). This auto-redirects to the actual article page for many sources. If the redirect works, you get full article text. If it fails (404/paywall), fall back to snippet data.
- Google News when=1d filter is directional, not strict: Google News' time filter is approximate — especially for Chinese-language queries, it frequently returns results from 4 to 21+ days ago. Do not dismiss older articles that appear within this filter; they are often the best available intelligence for a narrow window. Supplement Chinese queries with English searches (which have stricter time filtering) to find truly recent items.
- **Chinese Bing News consistently returns zero results for brand-specific marketing queries** (verified 2026-05-31, 2026-06-01): Searches on Bing News Chinese interface with P0 brand keywords (蒙牛, 伊利, 百威, 海信, vivo) return "我们未找到任何结果" even when English Bing News queries for the same topic during the same time window find fresh articles. This is now confirmed across multiple sessions — **do not rely on Chinese Bing News for brand marketing intel**. Use English Bing News queries with brand names instead, or fall back to Baidu News via Playwright browser (if CAPTCHA doesn't block).
- **Intelligence agent delegation may not perform actual web searches** (verified 2026-06-01): When delegating web research via `delegate_task(agent_id='intelligence', toolsets=["web","browser"])`, the Intelligence subagent may default to using only skill tools (skill_view, skills_list, skill_manage) without ever calling web_search or browser_navigate. It will produce a report from historical session records but never fetch live data. **Mitigation**: Either (a) do web research directly from the main agent instead of delegating, or (b) add explicit instructions in the goal/context to use mcp_scrapling_fetch or browser tools first before falling back to skill references.
- **MiniMax auth failure is distinct from rate limit** (verified 2026-05-27): `login fail: Please carry the API secret key in the 'Authorization' field` means the API key is not being sent — this is a different error from `2056-usage limit exceeded`. If you see this error on every call, do not retry MiniMax at all — switch immediately to the multi-channel fallback chain.
- **Playwright "Target closed" error**: When browser_navigate returns `Target page, context or browser has been closed`, the Playwright browser instance is not running. This requires external intervention (restarting the MCP server or launching a new browser instance) — you cannot fix this from within the agent. Fall back to scrapling basic mode for known-reliable direct article URLs (e.g., SportsPro).
- **Local project files as supplementary source**: The user's Desktop/ project directories and Obsidian vault often contain brand activity intel not yet public — ad orders, content calendars, partnership docs. Search these when web results are thin. Use `search_files(pattern='*百威*', path='/Users/gu/Desktop', target='files')` or similar. Cross-reference file timestamps to determine freshness. This is particularly valuable for the 晚报 run when web tools may be unavailable.
- **飞书审批中心 + 微信文件预览 = 最高价值离线情报** (verified 2026-05-27/28): When web tools are unavailable, the OpenChronicle event log's Feishu Approval Center captures and WeChat file previews are the SINGLE most valuable offline data source — they reveal deal amounts, payment status, and partnership terms BEFORE any public announcement. Scan event logs for "审批", "付款", "资质", "回款主体" keywords and WeChat file previews with brand+世界杯 filenames. This was confirmed across two consecutive sessions (May 27 evening and May 28 morning).
- **飞书内部执行情报表格** (new Format A section, verified 2026-05-28): When the briefing contains internal intel (Feishu chats, approvals, MCN, WeChat files), add a "📊 飞书内部执行情报" table between "行业趋势" and "启示与行动". Format: `| # | 情报 | 来源 | 时间 |` — this gives readers a quick-reference view of execution-level signals that web search cannot provide.
- **Tool-restricted technical competitive research is viable** (verified 2026-05-30): When web_search/browser/terminal are unavailable, competitive intelligence on open-source projects can still be produced by scanning the local filesystem for related repos, reading their READMEs/source, and cross-referencing with the knowledge base. The resulting report should explicitly label star counts as estimates and declare the limitation. See `references/github-technical-comp-intel-2026-05-30.md` for a worked example.
- **Skill scope mismatch for technical vs marketing intel**: This skill covers both marketing intelligence (brand campaigns, sponsorships) and technical/product intelligence (GitHub repos, feature matrices, open-source landscapes). The source reliability scale and primary tools differ between the two modes. When doing technical research, news-site reliability ratings do not apply — use GitHub commit activity, release cadence, and README completeness instead.

## Related Skills

- `last30days` — 30-day community/social trend research (uses bundled Python engine, different source coverage)
- `hermes-cron-management` — cron job lifecycle and troubleshooting

## Reference Files

- `references/world-cup-daily-briefing-cron-template.md` — 懂球帝世界杯营销日报 cron prompt 模板（三层结构 + P0/P1/P2 + 早/晚报拆分）
- `references/world-cup-2026-05-27-session.md` — 2026-05-27早报session记录：工具严重受限环境下的回退策略
- `references/world-cup-2026-05-27-evening-session.md` — 2026-05-27晚报session记录：Baidu News→Scrapling高效管道验证、baijiahao新源确认、晚报工具全时的原创发现能力
- `references/world-cup-2026-05-26-evening-session.md` — 2026-05-26晚报session记录
- `references/world-cup-2026-05-26-session.md` — 2026-05-26早报：Baidu News主入口验证、关键发现（华帝/剧星传媒/伊利蒙牛/长安汽车）、工具使用经验
- `references/world-cup-2026-05-25-session.md` — 2026-05-25早报：搜索查询、关键发现、FIFA赞助商层级体系知识库、工具使用经验
- `references/world-cup-2026-05-25-evening-session.md` — 2026-05-25晚报session记录（离线回退模式）：工具受限时的备选工作流、本地文件交叉验证经验
- `references/world-cup-2026-05-25-evening-v2-session.md` — 2026-05-25晚报v2 session记录（多通道并行回退模式）：web_search限流后的三通道并行策略（Intelligence + Playwright + Scrapling）、虎喻/Australian FinTech 新源验证
- `references/world-cup-2026-05-23-session.md` — 2026-05-23 session记录
- `references/world-cup-2026-05-16-session.md` — 2026-05-16 session记录
- `references/world-cup-2026-05-14-session.md` — 2026-05-14 session记录
- `references/world-cup-2026-06-01-morning-session.md` — 2026-06-01早报session记录：Bing News+scrapling stealth = 最佳英文实时发现源（5h前Forbes文章）、中文Bing News系统性空结果、Intelligence agent委托陷阱、Google News RSS仅适用于档案研究
- `references/world-cup-2026-05-31-morning-session.md` — 2026-05-31早报：蒙牛暗战深度分析、咪咕/小红书入局转播、DoorDash三平台联合campaign、竞品沉默模式、deep-dive 0/6成功率记录
- `references/world-cup-2026-05-30-evening-session.md` — 2026-05-30晚报session记录：纯离线模式验证（跨日模式识别、产品开发信号、PlayStation排期/剑南春合同/竞猜tab/多美女直播等内部执行情报）
- `references/offline-intelligence-sources.md` — 离线情报源完整目录：飞书审批中心、微信文件预览、MCN平台、销售群聊的捕获模式与提取技巧
- `references/world-cup-2026-05-28-session.md` — 2026-05-28早报session记录：纯离线模式验证（零web工具产出13条情报）、飞书审批中心/微信文件新源确认、offline-intelligence-sources参考文件创建
- `references/github-technical-comp-intel-2026-05-30.md` — **Technical/product competitive intelligence reference**: GitHub repo research workflow, feature comparison matrices, local-filesystem scanning approach for tool-restricted sessions, worked example from CodexPlusPlus competitor research. Use when researching open-source projects, AI coding tools, Desktop App enhancers, or technical tool landscapes.
