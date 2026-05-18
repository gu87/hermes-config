# 参考照片搜索实战模式（2026-05-17 更新）

## 核心原则

1. **先查已有，再搜新** — `ls photos/` 可能已有之前 session 的遗珠
2. **浏览器模式 > curl 模式** — Getty、Alamy 等图库对 curl 拦截严格
3. **版权历史报纸头版基本搜不到** — 直接标记为"需用户提供"
4. **Wikipedia Commons 对经典比赛瞬间有高质量 CC 图**

## Getty Images 浏览器搜索流程

```
browser_navigate → 搜 editorial 图片 → 看缩略图 → click 进详情 → 找大图 URL → curl 下载
```

**关键词策略**：精确到球员名+比赛+年份+事件。例子：
- `"David Beckham" "Greece" "2001" free kick` → 命中率高
- `"England" "Romania" "1998" Beckham debut` → 命中率高
- `"Beckham" "penalty" "Argentina" "2002"` → 命中率高

**避免**：只搜 `"Beckham goal"`（太宽泛，返回大量不相关结果）

## Wikipedia Commons 搜索流程

```
browser_navigate → commons.wikimedia.org → 搜球员名+年份+事件
```

成功率高的搜索模式：
- `贝克汉姆 1998 年世界杯`（中文名称有时比英文更精确）
- `David Beckham penalty Argentina 2002`
- `England Greece 2001`

如搜索返回空结果，直接用英文搜比赛维基百科页面（`en.wikipedia.org/wiki/...`），从页面 infobox 或正文取图 URL。

## 已知失效来源

| 来源 | 原因 | 替代 |
|------|------|------|
| The Sun archives | 付费墙+版权 | ✅ **用户截图上传** 或 **现场观众横幅/抗议照片**（同等表现力） |
| newspaper.com / UKPressOnline | 付费订阅 | ✅ 用户截图上传 |
| BBC Sport 回顾文章 | 风控/404/负载 | 其他新闻网站 |
| Google Images | 风控验证码拦截 | Bing Images 或直接搜来源站 |

### 报纸头版替代方案（推荐）

当需要 "舆论暴力" / "媒体围剿" / "XX报纸头条" 等参考图但搜不到免费版权版本时：

1. **首选替代：现场观众横幅/抗议标语照片** — 比报纸头版更有画面冲击力
   - 例：阿森纳球迷「DAVID BECKSCUM」横幅（1998 慈善盾杯温布利）→ 比 The Sun 头版更直观传达「全英公敌」
2. **次选：观众举报纸封面的照片** — 搜索"球迷举报纸 抗议 XXX"
3. **最后：用户自己截图** — 从报纸数字版/新闻档案截图上传

## 已发现但未引用图的复用模式

本 session 发现的复用案例：
- `photos/simeone_shirt_exchange.jpg`（Beckham 与西蒙尼 2002 年赛后交换球衣）原为 OpenClaw 上次搜索额外下载，未引用 → 这次用于 panel_9，描述改为"赛后与西蒙尼交换球衣——四年的恩怨在此刻和解"

**检查方法**：全量审计完成后，运行 `ls photos/` 对比 audit HTML 的 `ref:` 引用列表。未被任何 ref 引用的照片检查能否匹配其他卡片的描述。

## 搜索超时时的处理

OpenClaw 的默认 `max_iterations=50` 通常只够搜 6-8 张图。如果需要搜 10+ 张，提前调至 150。

如果搜索超时：尽量优先搜关键卡片（用户可能最先看的那几张），非关键卡片标记为"暂无参考图"。用户可通过 audit HTML 自行上传补充。
