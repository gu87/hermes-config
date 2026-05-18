---
name: visual-novel-studio
description: VisualNovelStudio —— 懂球帝站内文章→互动H5剧本小游戏的完整工作流。从选题到打包上线，由 Hermes Agent 团队协同执行。
category: content-production
---

# VisualNovelStudio - Hermes 工作流

## 概述

将懂球帝站内深度文章转化为带激励视频变现的互动 H5 小游戏。每篇产出：
- `dist/index.html`（图片 base64 内嵌、SDK 内嵌）
- `dist/assets/`（BGM、音效 mp3 外链）
- 推广素材（banner、信息流封面、圈子封面）

**耗时**：~4h / 篇（熟练后目标 1h）
**样板项目**：game3/另一场决赛、game6/最后一球

## ⚠️ 图片真实性和准确度审计协议（Beckham 篇踩坑沉淀）

### 背景

Beckham 篇的 29 张图（14 hero + 9 panel + 6 bg）是用 prompt 直接生成的。用户验收后发现大量失实问题：球衣颜色错误（英格兰 1998 客场是红色，prompt 写了白色）、发型年代错乱（2001 写成了莫西干、2002 写成了短刺）、时间线超出剧本范围（写到 2004 但剧本只到 2002）。

**根因**：prompt 只靠文字描述没查真实照片对照，AI 凭训练数据自由发挥。

### 触发条件

- 生成历史人物/真实场景的图片
- 用户反馈"图片失实"、"跟真实的不一样"
- 涉及特定年份、球衣、发型的图片

### 审计流程（含 Kanban 透明化工作流）

```
                 ┌─────────────────────────────────────┐
                 │  T1 OpenClaw 事实对比                 │
                 │  (每张图→搜真实照片→出绿/黄/红评级表)   │
                 │  使用 web + browser 工具集搜图         │
                 └───────────┬─────────────────────────┘
                             │ 用户审报告
                 ┌───────────▼─────────────────────────┐
                 │  T2 皮尔洛 出修正方案                 │
                 │  基于评级表圈定：改prompt / 重做 / OK  │
                 └───────────┬─────────────────────────┘
                             │ 用户确认
                 ┌───────────▼─────────────────────────┐
                 │  T3 内斯塔 修正 prompt JSON           │
                 │  改球衣、发型、反日文、时间线          │
                 └───────────┬─────────────────────────┘
                             │
                 ┌───────────▼─────────────────────────┐
                 │  T4 Claude Code 重做图片              │
                 │  按修正后prompt生成                   │
                 └───────────┬─────────────────────────┘
                             │
                 ┌───────────▼─────────────────────────┐
                 │  T5 安布罗西尼 验收                   │
                 │  检查还有无事实错误                   │
                 └───────────┬─────────────────────────┘
                             │
                 ┌───────────▼─────────────────────────┐
                 │  T6 Claude Code 重建HTML → 用户验收   │
                 └─────────────────────────────────────┘
```

**每步完成后推送到飞书给用户审核**，用户确认后才推进下一步。

### 可调节审核密度模式

这不是二元的「手动 vs 自动」。审核密度是可调的滑动条：

| 阶段 | 审核密度 | 行为 |
|------|---------|------|
| 初期（1-2次） | 全人工 | 每步完成后推送摘要给用户，用户确认后才下一步 |
| 中期（熟悉后） | 关键节点 | 中间步骤自动推进，只在交付节点（验收）需要人工确认 |
| 成熟期 | 全自动 | 全链路自动执行，异常时才通知人工介入 |

判断标准：同类型任务第1-2次走全人工。用户说「这个你熟了」或连续2次无修改意见通过后，可升到关键节点模式。遇到意外错误降回全人工模式。

### 审计输出格式

审计完成后，产出两种格式供用户选择：

**方式 A：飞书文档**（适合详细阅读）
- 评级统计 + 按章节逐图对照 + 嵌入真实照片
- 创建命令：`lark-cli docs +create --api-version v2 --doc-format markdown --content "$(cat report.md)"`
- 照片插入：`lark-cli docs +media-insert --doc <doc_id> --file <photo_path> --align center --caption "描述"`

**方式 B：本地 HTML 审计板**（适合交互式审核，推荐）
- 生成独立 HTML 文件放在 `audit/index.html`
- 每张卡片：左侧 AI 生成图 + 右侧真实照片（如有）
- 每张可勾选「保留」/「需要修改」+ 填写修改意见
- 底部「📥 导出意见」按钮 → 导出 JSON 决策清单，发回给 Hermes 按单执行
- 路径修正：HTML 在 `audit/` 目录，AI 图用 `../raw/` 相对路径，真实照片用 `./photos/` 相对路径
- 用户直接本地浏览器打开即可，无需 HTTP 服务（或用 HTTP server 对外提供服务）

#### 自定义参考图上传功能

每张卡片参考图区域下方提供「📤 上传参考图」按钮，让用户可以：

1. **上传本地图片** — 点击按钮选择硬盘上的照片/截图，用 FileReader 读取为 data URL 并内联显示
2. **替换参考图区域** — 上传后自动替换原始的 ref 图片或"暂无参考照片"占位符
3. **移除已上传的图** — 点击「✕ 移除」恢复原始状态（原始 ref 图或占位符）
4. **导出时记录** — 导出的 JSON 中包含 `hasCustomRef: true/false` 和 `customRefFilename: "xxx.jpg"` 字段，方便后端知道这张卡有用户自定义参考图

实现方式：纯前端（HTML + JavaScript），无需后端。通过 `document.addEventListener('change', ...)` 监听文件选择，`FileReader.readAsDataURL()` 读取图片后渲染。上传状态通过 `uploadedRefs` 对象在内存中维护。data URL 仅用于展示，不持久化到磁盘。

该功能解决的是：审计阶段用户可能从懂球帝文章、其他图库找到更好的参考图，直接拖/选到审计板里对比，不用再跑 OpenClaw 额外搜索一轮。

**上传后的文件检索流程**：用户导出的 JSON 中标记了哪些卡片有自定义参考图（`hasCustomRef: true`）。图片在浏览器内存中展示，如果用户也保存到磁盘后会落在 `~/Downloads/`。此时需要从 Downloads 目录找到对应文件，复制到 `audit/photos/` 并更新 HTML 的 ref 链接。详见 [`references/user-photo-retrieval-protocol.md`](references/user-photo-retrieval-protocol.md)。

**两种方式的关系**：飞书文档适合一次性存档查阅；HTML 审计板适合逐张审核+导出决策。先做审计板让用户勾选/写意见，完成后按意见清单修改。

### 章节归属修复协议（叙事流审计）

审计时不仅要检查单张图的维度是否正确，还要检查该图所在的 **章节** 是否符合叙事流。同一张图放在不同章节里含义完全不同。

#### 触发条件

- 用户反馈「章节顺序不对」「这个内容不应该在这里」
- 审计时发现卡片描述的**是正面事件但在负面章节**（或反之）
- 同一场比赛/事件碎片散落在不同章节

#### 修复流程

1. **画时间线** — 按时间顺序列出所有关键事件及其正面/负面属性
2. **检查章节主题** — 每个章节的标题（如「坠入深渊」）和 bgIntro 是否与包含的素材匹配
3. **重分配** — 将素材挪到主题匹配的章节，同时确保时间线不被打乱
4. **同步更新**：
   - 更新被移动卡片的 `rating`（如果事实没变但叙事位置对了，可从 🔴 降为 🟡）
   - 更新被移动卡片的 `desc` 和 `issue`（匹配新章节上下文）
   - 重新编写受影响的章节 `bgIntro`
   - 更新 `bg` 卡片的章节编号引用
   - 重算顶部统计数字（🟢🟡🔴 计数）
5. **验证** — 按新章节顺序读一遍，确认叙事流顺滑

#### 典型错误模式

| 模式 | 症状 | 修复 |
|------|------|------|
| 正面事件放负面章节 | 哥伦比亚首球放在「坠入深渊」 | 挪到「闪耀新星」 |
| 事件碎在多个章节 | 红牌事件分在 ch3（冲突）+ ch4（离场）+ ch5（媒体） | 合并到 ch2（红牌）+ ch3（后果） |
| 跨年事件挤在一个章节 | 1999 欧冠捧杯 + 2002 世界杯挤在 ch6 | 1999 放 ch4 救赎之路，2002 单独 ch6 |

#### 章节映射表（足球人物标准模板，5-6 章）

| 章节 | 适合内容 | 情绪 |
|------|---------|------|
| 第一章·闪耀新星 | 早期成功、首秀、首球、崭露头角 | 🟢 正面、希望 |
| 第二章·坠入深渊 | 关键挫折、红牌、伤病、失败 | 🔴 负面、戏剧冲突 |
| 第三章·全英公敌 / 舆论风暴 | 后果发酵、媒体批评、公众反应 | 🔴 负面、压迫感 |
| 第四章·救赎之路 | 贵人相助、训练、复苏、重返巅峰 | 🟡 低谷→上升 |
| 第六章·涅槃重生 | 最终证明、重大成就、未来展望 | 🟢 圆满、释然 |

### 参考照片搜索策略（Getty + 多来源，避免死磕一家）

审计协议中的 T1（OpenClaw 事实对比）需要为每张 AI 生成图找到真实历史照片做对照。

#### 第一步：先检查本地 photos/ 目录

```bash
ls ~/Projects/vns-game-becks/audit/photos/
```
可能已有从之前 session 下载但未被引用的图。用已存在的图比重新搜索快得多。本 session 发现 `simeone_shirt_exchange.jpg` 已在目录但未被引用，完美匹配 panel_9 的"和西蒙尼交换球衣"场景。

#### 搜索完后：检查是否有新增可用但未引用的文件

OpenClaw 可能多下载了不相关的图。搜索完成后巡检一遍新文件，若发现能匹配其他卡片的，直接更新 ref 链接。

#### 图库优先级

| 优先级 | 来源 | 方法 | 成功率 | 备注 |
|--------|------|------|--------|------|
| P1 | Getty Images editorial | browser_navigate → 搜关键词 → 点图 → browser_console 拿URL → curl下载 | ⭐⭐⭐ 主来源 | 版权的图能看到但不能商用，审计参考够用 |
| P2 | Wikipedia Commons | 搜 `commons.wikimedia.org` 自由图片 | ⭐⭐⭐ | 经典比赛进球庆祝图常有 |
| P3 | 新闻文章（BBC/Guardian/ESPN） | 搜回顾文章，页面里找嵌图 | ⭐⭐ | 比赛瞬间 |
| P4 | Alamy、Reuters、PA Images | 同样browser访问 | ⭐ | 很多被403/风控拦截 |

#### 核心套路（Getty Images 浏览器模式）

Getty 的 Editorial 分类对历史体育照片有最完整的收录。浏览器模式可以绕过 curl 被拦截的问题：

1. `browser_navigate` 打开 Getty 搜索 editorial 图片
2. `browser_click` 点缩略图进详情页
3. `browser_console` 执行 JS 获取大图 URL
4. `terminal` curl 下载

注意 Getty 搜索关键词要够精确（如 `"David Beckham free kick Greece 2001"` 而不是泛搜）。太宽泛返回大量不相关结果。

#### Wikipedia Commons 方法

对经典比赛瞬间（欧冠决赛进球、世界杯标志性庆祝）Wikipdia Commons 有高质量 CC 图片。直接查维基百科比赛条目，从 infobox/正文取图片 URL。

#### 照片搜索命中率经验

| 图片类型 | 最佳来源 | 难度 |
|---------|---------|------|
| 球员发型/肖像特写 | Getty | 容易 |
| 比赛现场全景 | Getty/Wikipedia | 中等 |
| 标志性进球瞬间 | Wikipedia（经典比赛有自己的页面图片） | 中等 |
| 特定比赛瞬间（例如谢林汉姆补射） | Wikipedia 比赛条目 | 难（常只有缩略图） |
| 球员通道握手 | Getty | 难（版权照片） |
| 报纸头版 | 新闻档案网站 | **最难（版权限制）** |
| 球场外景/建筑 | Wikipedia | 容易（CC 协议建筑图多） |

#### 照片搜索坑点

**① 英国小报头版（The Sun / Daily Mail / Mirror）几乎不可能免费搜到**

这些报纸的头版照片受严格版权保护，新闻档案（Newspapers.com、UKPressOnline 等）需要付费订阅。Wikipedia Commons 曾经有但已被删除（版权投诉）。

**替代方案**：让用户自己截图上传（审计 HTML 已内置上传功能）。或者用历史文章中引用的缩略图（质量差但可作为参考）。

**② 搜索前先检查 photos 目录**

本 session 发现 photos/ 目录已有 16 张图片，其中 `simeone_shirt_exchange.jpg` 等数张从未被引用。不要立即开始全网搜索——先 `ls photos/` 看看有没有能直接用的。

**③ 同理：已下载但未引用的图片**

如果 photos/ 目录中有之前 OpenClaw 搜索下载的图片未被 audit HTML 引用，检查它们能否对应其他卡片再更新 `ref` 字段，而不是重新搜索。

**④ max_iterations 要提前调高**

搜索图片需要大量 browser 调用。`config.yaml` 中的 `max_iterations: 50` 对图片搜索任务不够——50 次通常只能搜 6-8 张图。开始搜索前先确认已调到 100-150。

#### 照片下载后插入飞书文档 / 更新 HTML 审计板

飞书：`lark-cli docs +media-insert --doc <doc_id> --file ./photos/filename.jpg --align center --caption "描述"`
HTML：找到 `audit/index.html` 中对应卡片的 `ref: null` 改为 `ref: "photos/filename.jpg"`

#### 搜索不到时的替代方案

自由版权图库找不到 = 该照片是编辑类版权图片。标记为"版权图片未找到可下载版本"，不影响审计决策。

### OpenClaw 工具集要求

OpenClaw 执行事实对比任务时，**必须确认其 toolsets 包含 ["terminal", "file", "web", "browser"]**（不包含 web 和 browser 就搜不到真实照片做对照）。如果缺少，先更新 agent-registry.json：
```json
"openclaw": {
  "subagent_profile": {
    "toolsets": ["terminal", "file", "web", "browser"]
  }
}
```
然后重启 gateway：`hermes gateway run --replace`

### OpenClaw 对照维度

给 OpenClaw 下任务时，必须指定以下核查维度：

| 维度 | 核查内容 | 典型错误 |
|------|---------|---------|
| 🏟 球场 | 剧本节点的比赛发生在哪个具体球场？ | Stade de Marseille 写成 Stade Félix-Bollaert |
| 👕 球衣 | 英格兰/曼联在该场比赛穿什么颜色？ | 1998 客场写白色（实际红色客场） |
| 💇 发型 | 该人物在该年份是什么具体发型？ | 2002 写莫西干（实际短板寸） |
| 👤 年龄 | 当时多少岁？ | 2001 年写 28 岁（实际 26 岁） |
| 😤 表情 | 该节点的真实情绪（查比赛照/视频） | 红牌离场应该是 heartbreaking 不是 angry |
| 📅 时间线 | 这个事件发生在哪一年？ | 写到 2004 超出剧本 1998-2002 范围 |
| 📂 **章节归属** | **这个素材放在正确的章节吗？** | 哥伦比亚首球（正面）放到「坠入深渊」章节 → 叙事不通 |

### 反日文指令（所有 manga 风格图强制加）

```
NO Japanese text, NO kanji, NO signboards with Asian characters
NO Japanese captions, NO Japanese speech bubbles in the image
All visible text must be English (newspaper, stadium signs, jerseys, scoreboards)
NO Japanese-style street signs, NO Japanese shop/store signs
The image background/textures may use manga effects (halftone dots, speed lines)
but must NOT contain any readable text in any language unless it's English and historically accurate
```

### 坑点记录

1. **球衣颜色必须查比赛记录** — 不要凭"主队=主场球衣"推断。1998 英格兰对阿根廷是红色客场球衣
2. **发型查速查表而不是凭印象** — Beckham 2002 短板寸不是莫西干，2000-2001 才是莫西干期
3. **时间线以剧本为准** — 剧本只到 2002 年，hero_11/12/13 不能写到 2004
4. **全部生成后再发现错误 = 浪费大量 API 调用** — 应该先跑审计再动手
5. **⚠️ 首秀≠第一场比赛** — 不要推断「首秀 = 该届赛事的首场比赛」。贝克汉姆 1998 世界杯首秀是对罗马尼亚（第 2 场小组赛，第 32 分钟替补），不是对阵突尼斯（第 1 场小组赛，他 DNP）。**必须查 match report（Wikipedia match sheet 可确认首发/替补/分钟数）**，不能凭「比赛顺序=登场顺序」的直觉下结论。
8. **报纸头版照片几乎不可能免费获取** — The Sun/Daily Mail/Mirror 头版受严格版权保护，Wikipedia Commons 曾有但已被删除。不要在这类图上消耗 OpenClaw/手动搜索时间。替代方案：让用户自己截图上传，或用**现场观众横幅/抗议照片**（如阿森纳球迷「DAVID BECKSCUM」横幅图）作为同等表现力的替代参考。

9. **⚠️ 1998年贝克汉姆发型 ≠ 板寸（已踩坑）** — 上一轮审计错误地把 hero_1~hero_5 的发型验证为"短漂白板寸 ✅"，但 1998 年世界杯时期的贝克汉姆是**金色中长发，侧分**（medium-length side-parted blonde hair），不是板寸。这个错误导致所有 1998 年角色的 prompt 都写成了错误的发型描述，用户发现后需要全量修正。
   - **根因**：审计时只凭模糊印象"90s 贝克汉姆=金发"就打了勾，没有对照真实照片确认具体发型长短和风格
   - **教训**：发型核查不能只确认「金发」这一维度，必须确认「长短」和「风格」。对比真实照片时，**重点看头发长度（耳上/耳下/齐肩）和两侧剃度**，而不是只看颜色
   - **修复方案**：如果在 prompt 中写错了发型描述，需要全量修正 task_regenerate_N.json 和 gen_batch_N.json 中所有受影响图片的 prompt，然后在用户指导下重新生成

### 所有图片统一修正准则

对已有图片进行事实修正时，一次性检查：

- [ ] 球衣颜色 vs 真实比赛记录
- [ ] 发型 vs 该年速查表
- [ ] 时间线 vs 剧本范围
- [ ] 反日文指令 vs prompt
- [ ] 剧本中出现的队友/对手 vs 真实首发

## ⚠️ 多维度质量审计协议（用户反馈"细节有问题"时使用）

### 触发条件

当用户说"细节有问题"、"太差了"、"不对"等模糊负面反馈**且**涉及多个方面时，**不要立刻跳进单一维度修复**。先做全面审计，按优先级从低到高修复。

### 审计四维模型

| 优先级 | 维度 | 典型问题 | 工作量 | 修复特征 |
|--------|------|---------|--------|---------|
| **P3** | UI/交互/视觉 | 字体、颜色、动画节奏、排版 | 小（CSS 调整） | 不改数据，不改逻辑 |
| **P2** | 音效/氛围 | BGM 缺失、音效质量、交互反馈 | 中（新增+配置） | 改引擎/添文件，不改数据 |
| **P1** | 内容/剧情/数据 | 时间线错误、人物名拼写、剧本节奏 | 中（JSON 编辑） | 改剧本数据，不改图片 |
| **P0** | 图片/视觉素材 | 真实人物形象不匹配、场景不精确 | 大（重新生成） | 最贵最耗时，最后做 |

### 执行顺序规则

1. **先审计，后动手** — 四个维度各列出具体问题清单
2. **从 P3 开始修** — UI 调整最快，改完立刻可见
3. **P3→P2→P1→P0** — 由简入繁，用户可以在每个阶段确认
4. **P0 放最后** — 图片生成最耗时最贵，而且 UI/内容修正后可能改变对图片的需求
5. **全部改完后重建 HTML** — 确保所有改动（P3+P2+P1）一次性体现在最终产物中
6. **模板同步** — 引擎相关改动（P3 animation/font, P2 audio）必须同步到 `assemble.py` 的 ENGINE_TEMPLATE，否则下次构建会丢失

---

## 概述

第一条完整管道已跑通。产出：
- `~/Projects/vns-game-becks/dist/index.html` — 1.1MB, 1588行, 80个节点, 5章

### 标准项目目录结构

```
game-name/
├── raw/              ← gen.py 输出（原始 PNG）
├── compressed/       ← compress.py 输出（WebP）
├── assets/           ← 音效文件 mp3
├── dist/             ← assemble.py 输出（最终部署目录）
│   ├── index.html
│   └── assets/
├── script_flat.json  ← flatten.py 输出
├── flatten.py        ← 章节→平面转换脚本
└── (剧本 JSON 源文件)
```

### 各步骤耗时（实测）

| 步骤 | 耗时 |
|------|------|
| 选题评分 | 2min |
| 皮尔洛出剧本 | 6min |
| flatten + 映射图片key | 1min |
| gen.py 生图（5张） | ~4min/张 |
| compress.py 压缩 | 2s/张 |
| assemble.py 构建 | 1s |
| **合计** | **~35min** |

| 🅱 自动验收 | `python accept_test.py dist/index.html` | ✅ 已内置`/Users/gu/.hermes/scripts/vns/accept_test.py` |

---

## ⚙️ 质量控制 — 两道门禁

每次构建必须经过两道门禁。**两道全过才能交付。**

### 🅰 Gate A — 数据格式校验（assemble 之前）

**时机**：皮尔洛出剧本 → flatten → fix_script → **Gate A** → assemble

```bash
cd game-dir/
python /Users/gu/.hermes/scripts/vns/validate_script.py script_flat.json --img-dir compressed/
```

**检查项：**

| 类别 | 检查内容 | 失败后果 |
|------|---------|---------|
| 节点类型 | 是否引擎支持（scene/narrate/dialog/panel/choice/card/hero/gacha/ending） | 无此段，skip |
| 字段名 | data字段与engine handler是否匹配（如 dialog vs text） | 文字消失 |
| 必填字段 | 每个节点类型的必要字段是否存在 | 运行时崩或空 |
| 残留占位符 | `"bg": "?"` → 必须是实际 key | 图片裂 |
| 图片覆盖率 | SCRIPT引用的 key 在 img-dir 中是否有对应文件 | 图片裂 |
| 禁止结构 | panel 内有无 `left/right/illustration` 嵌套 | 引擎跳过 |

**⚠️ Gate A 必须跑。不要跳过。**

### 🅱 Gate B — 自动验收测试（assemble 之后）

**时机**：assemble → **Gate B** → 交付

```bash
cd game-dir/
python /Users/gu/.hermes/scripts/vns/accept_test.py dist/index.html
```

**检查项（headless Chromium）：**

| 测试项 | 验证方式 |
|--------|---------|
| 页面无 JS 错误加载 | 监听 `pageerror` 事件 |
| 启动页正常渲染 | #launch 和 #launch-btn 可见 |
| 点击进入后场景切换 | #launch 消失, cursor≥1 |
| 背景图已设置 | scene.style.backgroundImage 非空 |
| 对话框有文本 | dialog-text.textContent 非空 |
| 多次推进正常 | 10次点击后 cursor>3 |
| 引擎修复完整性 | 检查 `let advancing` / `node.dialog` / `setTimeout(advance,1600)` |

**⚠️ Gate B 必须在有 headless Chromium 的环境运行。**

---

## 标准执行流程（含门禁 + 样张确认）\n\n```\n皮尔洛出剧本 DSL\n    ↓\nflatten.py（章节→平面）\n    ↓\nfix_script.py（标准化）\n    ↓\n🅰 Gate A — validate_script.py    ← 每次必跑\n    ↓\n写图片 prompt（按9维度模板+画风约束）\n    ↓\n👀 样张确认 — 用第 1 张 hero prompt 生成 1 张图给用户看效果\n                    用户确认面部像、风格对、细节准后再继续\n                    （这一步避免方向性全量重做）\n    ↓\n用户确认 prompt + 样张后\n    ↓\ngen.py（批量生图 23张）\n    ↓\ncompress.py（压缩）\n    ↓\nassemble.py（构建 HTML）\n    ↓\n🅱 Gate B — accept_test.py        ← 每次必跑\n    ↓\n交付\n```

### 踩坑记录

1. **皮尔洛输出是章节结构**（5个chapter各含nodes数组），assemble.py 需要平铺数组。必须先用 flatten.py 转换。
2. **图片 key 是占位符 "?"**：皮尔洛的 scene/panel/hero/card 节点里的 bg/src/photo/image 字段值是 "?"。需在 flatten 后用程序映射为真实 key。
3. **中文注释 + terminal 工具冲突**：不要在 terminal 的 bash 命令前面写 `# 中文注释` 行——shell 会把中文当命令执行导致失败。
4. **gen.py 超时**：GPT Image 2 高峰期可能 503，已内置 3 次重试。timeout=300s 够用。
5. **compress.py 工作目录**：必须 cd 到图片所在目录运行，或使用绝对路径。

所有脚本在 `~/.hermes/scripts/vns/`（构建时自动引用）和 `~/.hermes/skills/visual-novel-studio/scripts/`（工作流辅助）下：

| 脚本 | 用途 | 用法 |
|------|------|------|
| `config.py` | API Key + endpoint 配置 | 其他脚本自动导入 |
| `gen.py` | GPT Image 2 文生图 | `python gen.py "prompt" --size 1536x1024 --out bg.png` 或 `--batch batch.json` |
| `edit.py` | 图生图/图片编辑 | `python edit.py input.png "把背景改成夜晚" --out output.png` |
| `compress.py` | 压缩为 VNS 规格 | `python compress.py input.png --type bg --out compressed.webp` 或 `--dir raw/ --out-dir compressed/` |
| `flatten.py` | 章节→平面转换 | `python ~/.hermes/skills/visual-novel-studio/scripts/flatten.py script.json script_flat.json` |
| `fix_script.py` | 标准化剧本（展平章节、简化 panel、补 image key） | `python fix_script.py script_flat.json script_flat.json` |
| `post_gen.py` | 生图完成后的压缩+重建一键流程 | `cd game-dir && python post_gen.py` |
| `validate_script.py` | **🅰 数据格式校验** — assemble前检查字段名/必填/图片key | `python validate_script.py script_flat.json --img-dir compressed/` |
| `accept_test.py` | **🅱 自动验收测试** — assemble后用Playwright验证UI | `python accept_test.py dist/index.html` |
| `rebuild.sh` | **一键重建** — validate → compress → assemble → test | `cd game-dir && bash rebuild.sh` |


**每次构建后必须自检（防止无声 bug 上线）：**
```bash
# 检查图片数量
grep -o '"bg[^"]*"' dist/index.html | sort -u | wc -l    # 应有 ≥5
grep -o '"panel[^"]*"' dist/index.html | sort -u | wc -l  # 应有 ≥4
grep -o '"hero[^"]*"' dist/index.html | sort -u | wc -l   # 应有 ≥3

# 检查引擎关键字符串（确认所有修复已生效）
grep -c 'setTimeout(advance, 2800)' dist/index.html               # 应为 1（锁修复）
grep -c 'node.dialog' dist/index.html                      # 应为 1（dialog 修复）
grep -c 'node.description' dist/index.html                 # 应为 1（card 修复）
grep -c 'let advancing' dist/index.html                    # 应为 1（race condition 修复）
grep -c 'z-index:22' dist/index.html                       # 应为 ≥1（panel z-index 修复）
```

**引擎模板**：内嵌在 `assemble.py` 中（ENGINE_TEMPLATE 常量），基于 game6mldn 部署版提取。

**引擎核心时序参数**（已根据质量反馈优化，任何修改必须同步到 assemble.py ENGINE_TEMPLATE）：
- Hero 展示：5000ms（5s 自动消失，不低于 4000ms）
- Scene 章节过渡：2500ms auto-advance（锁 1500ms，留 1s 重叠）
- Panel 浮层：fade-in 100ms 后 show，4s 后 auto-hide
- Dialog 打字：70ms/字，加粗区 100ms/字
- Choice 选中：400ms 延迟后推进
- 场景切换锁：1500ms（不可交互期）

**已知引擎 Bug 修复记录（v1 → v2）：**
1. 锁冲突：scene 节点 `setTimeout(advance, 800)` 被自身 `locked=true(1500ms)` 吞掉 → 改为 1600ms
2. dialog 字段名：数据用 `"dialog"` 读 `node.text` → 改为 `node.dialog`
3. card 字段名：数据用 `"description"` 读 `node.text` → 改为 `node.description || node.text`
4. choice 评分：数据用 `affinity_effect` 对象 → 改为 `opt.score || sum(affinity_effect values)`
5. card-photo：增加 fallback 到 `IMG_DICT[node.icon_img]`
6. **race condition：hero 自动推进的 200ms 间隙中，点击事件也能触发 advance() 导致双重推进，skip 掉 narrate 节点。** → 新增 `advancing` 互斥锁，`advance()` 执行期间拒绝第二次调用。

7. **z-index 层叠上下文 bug：panel 被 dialog 覆盖**：`.panel` 的 `z-index:15` 低于 `#dialog-box` 的 `z-index:20`。面板节点显示后 200ms 自动推进到下一对话节点，对话框出现覆盖面板，用户看不到。
   - **表现**：面板图已加载、DOM 中存在、图片尺寸正确，但 opacity:0（无"show"类）或 opacity:1 但被对话框挡在背后。用户报告"中间的小图都没有图片"。
   - **根本原因**：panel z-index 15 < dialog z-index 20。面板位置 `bottom:100px; right:12px` 与对话框 `bottom:20px; left:12px; right:12px` 在垂直方向重叠，对话框层级更高。
   - **修复**：`.panel { z-index: 15 → 22 }`（高于 dialog 的 20，低于 hero-box 的 35 和 choice 的 35）。
   - **验证方法**：浏览器 console 检查 `.panel` 的 computed z-index：`getComputedStyle(document.querySelector('.panel')).zIndex` → 应为 "22"。或检查对话框出现时 panel 仍有 "show" class 且 opacity 为 1。
   - **需同步到**：`assemble.py` ENGINE_TEMPLATE 中的 `.panel { z-index: 22; }` CSS。

以上修复已直接打到 `assemble.py` ENGINE_TEMPLATE，后续所有构建自动继承。

**引擎调试清单**：详见 `references/engine-debug-checklist.md`（当游戏"黑屏/不工作"时按六层调试流程排查）。

**SDK 保留口**：引擎代码中 `onReroll()` 函数已标注 `{{SDK_PLACEHOLDER}}` 占位符，接入广告 SDK 时直接替换。

13. **不要自己调查图片生成管线** — 当用户说「重新生成图片」时，**不要自己读 gen.py / workflow JSON / ComfyUI 配置**。这是内斯塔的工作。正确的顺序：派内斯塔调查管线→内斯塔出 prompts + task package→转 gen.py batch→先抽样张给用户确认→确认后 Claude Code 执行批量生成。Hermes 的角色是协调和验收，不是技术执行。

**踩坑记录**：详见 `references/pitfalls.md`（10 条已记录陷阱）。

**引擎调试清单**：详见 `references/engine-debug-checklist.md`（当游戏"黑屏/不工作"时按六层调试流程排查）。
**皮尔洛派单模板**：详见 `references/delegation-prompt-template.md`。

| `task_to_batch.py` | 将内斯塔的 task_regenerate_N.json（章节嵌套格式）转为 gen.py batch 格式（平面[{out, prompt}]） | `python3 task_to_batch.py task_regenerate_18.json -o gen_batch_18.json --size 1024x1024 --quality high` |

**脚本位置**：`scripts/` 目录下（构建时自动引用，也可从 `~/.hermes/skills/visual-novel-studio/scripts/` 中直接调用）。

**新游戏只需要替换 3 样：**
1. `SCRIPT` 数组（皮尔洛按 DSL 生成）
2. `IMG_DICT`（内斯塔用 gen.py 生图 + compress.py 压缩）
3. `SFX_LIST` + 音效文件（OpenClaw 从 pixabay/freepd 找）

**还缺的硬资产：** `unified-reward-bridge.js`（广告 SDK）和懂球帝文章 API cookie。详见 `references/SOP-document-path.md`。

---

## 前提条件（先准备这些才能跑）

| # | 资源 | 获取方式 |
|---|------|---------|
| 1 | GPT Image 2 API Key | ✅ 已配置在 `~/.hermes/scripts/vns/config.py` |
| 2 | H5 引擎模板 + 构建脚本 | ✅ `gen.py` / `edit.py` / `compress.py` / `assemble.py` 全部就绪 |
| 3 | 统一文案 (剧本) | 皮尔洛按 DSL 规范输出 |
| 4 | 音效资源 | OpenClaw 从免费音源下载 |
| 5 | UnifiedRewardSDK | ❌ 待接入（已预留 `{{SDK_PLACEHOLDER}}`） |
| 6 | 懂球帝文章 API | ❌ 需 laravel_session cookie |

---

## Agent 分工

```
总指挥（Hermes / 马蒂尼）
├── ① 选题 → 自评（遵选材标准）
├── ② 出剧本 → 皮尔洛（写剧本 DSL）
├── ③ 画风锚定 → 皮尔洛 + 确认
├── ④ 生图 → 内斯塔（调度 GPT Image 2）
├── ⑤ 音效 → OpenClaw（搜索+下载）
├── ⑥ H5引擎 → 内斯塔 + Claude Code（组装 HTML）
├── ⑦ SDK → 内斯塔（嵌入广告代码）
├── ⑧ 打包 → Claude Code
└── ⑨ 验收 → Codex（代码审查）+ 人工
```

---

## 流程详解

### 阶段① 选题

**选材标准（70分以上进入生产流程）：**

| 维度 | 分值 | 判断标准 |
|------|------|---------|
| 戏剧冲突 | 25 | 是否有明确的欲望、阻碍、反转、代价 |
| 多视角潜力 | 15 | 是否天然存在 ≥3 个不同立场的当事人 |
| 情绪链完整度 | 20 | 轻松→震惊→共情→爽感→沉思 |
| 视觉化程度 | 10 | 是否有可画面化的场景 |
| 互动选择空间 | 10 | 是否能设计关键选择 |
| 社区讨论潜力 | 10 | 是否适合引发争论/分享 |
| 长尾价值 | 10 | 不依赖即时热度 |

**一票否决**：事实无法核验、素材授权不清、涉及现实人物严重污名化、诱导未成年人消费。

**反例**：纯赛事战报、球员转会快讯、纯数据分析

### 阶段② 剧本结构化 — 皮尔洛约束

**⚠️ 关键坑点（实测踩坑，务必注意）：**

皮尔洛输出剧本时，必须明确约束以下格式，否则引擎无法渲染：

1. **不要用 `illustration` 类型**。引擎只支持：scene / narrate / dialog / panel / choice / card / hero / gacha / timeline / ending。皮尔洛倾向输出 `illustration` 类型，需要用 `panel` 替代。
2. **panel 节点必须用简单格式** `{ type:'panel', src:'key', pos:'br' }`。皮尔洛倾向生成复杂嵌套结构（`layout:'split_left_right'`, `left:{illustration:{...}}`），引擎不支持。必须要求输出平铺格式。
3. **hero 节点用 `title`**，不要用 `dialog`。皮尔洛倾向在 hero 节点里写角色台词到 `dialog` 字段，但引擎读的是 `title`。
4. **图片 key 不能写 "?"**。皮尔洛会默认写 `bg:"?"`, `src:"?"`，必须要求他写实际 key（如 `bg01`）或留空由后续脚本填充。
5. **节点不要包含 `id` / `character` / `expression` / `pose` / `duration_seconds` 等元数据**。引擎只读 type-specific 字段。
6. **scene 节点必须包含 `chapter` 字段**用于 HUD 显示章节名。格式：`"第一章：闪耀新星"`。
7. **choice 节点必须包含 `options` 数组**，每个 option 必须有 `text` 和 `score` 字段。

**标准化流程（必须在 assemble 前运行）：**
```bash
python3 fix_script.py script_flat.json script_flat.json
```
该脚本会自动：展平章节 → 简化 panel → 补 image key → 移除元数据 → 加 ending 节点。

#### 章节结构（默认5章）

| 章节 | 作用 | 典型情绪 |
|------|------|---------|
| 第一章 | 建立轻松入口、人物关系 | 好奇、玩梗、轻松 |
| 第二章 | 抛出异常细节或关系裂缝 | 疑惑、站队 |
| 第三章 | 核心冲突或关键选择 | 紧张、代入 |
| 第四章 | 真相反转或情绪高点 | 震惊、爽感 |
| 第五章 | 档案落地、结局分支 | 共情、沉思 |

#### 视角模板

| 模板 | 适合题材 |
|------|---------|
| 固定主角型 | 乙游、社区、调查、成长 |
| 多POV群像型 | 历史复杂事件、争议冠军 |
| 双主角交错型 | 宿敌、搭档、队友冲突 |
| 档案调查型 | 禁药、黑哨、转会内幕 |

#### 剧本 DSL 节点类型

```javascript
// 每个节点都有的通用字段
{ id: 'unique_id', ... }

// 节点类型
{ type:'scene',    bg:'xxx.jpg',  chapter:'第一章：xxx' }       // 场景切换
{ type:'narrate',  text:'内心独白' }                              // 旁白
{ type:'dialog',   speaker:'xxx', text:'对话' }                  // 对话
{ type:'panel',    src:'xxx.jpg', pos:'br' }                     // 浮层插图
{ type:'choice',   question:'xxx', options:[...] }               // 选择题
{ type:'card',     title:'xx档案', text:'...', photo:'xx.jpg' }  // 历史档案卡
{ type:'comic',    panels:[...] }                                 // 漫画分格
{ type:'hero',     title:'xxx', image:'xxx.jpg' }                 // 英雄时刻
{ type:'profile',  name:'xxx', tags:[...], bio:'...' }            // 人物介绍
{ type:'timeline', events:[...] }                                 // 时间轴
{ type:'comments', posts:[...] }                                  // 评论区风暴
{ type:'evidence', items:[...] }                                  // 证据墙
{ type:'map',      points:[...], routes:[...] }                   // 地图推进
{ type:'relationship', nodes:[...], edges:[...] }                 // 关系网
{ type:'archive',  title:'xxx', pages:[...] }                     // 档案翻页
{ type:'scoreboard', home:'xx', away:'xx', events:[...] }         // 赛况面板
{ type:'gacha',    question:'...', pool:[...], rerollCost:[...] } // 抽卡节点
{ type:'paywall' }                                                // 激励视频墙
{ type:'ending' }                                                 // 结局成就卡
```

#### 剧本时间线精确度（已踩坑，重要）

**⚠️ 教训**：贝克汉姆篇的剧本跳过了 1998-99 曼联三冠王赛季（一个 narrate 说"三年过去了"），弗格森电话的时间线也被模糊处理（历史是世界杯结束后立即打，剧本放到了低谷期之后）。

**参考文件**：[`references/script-timeline-accuracy.md`](references/script-timeline-accuracy.md) — 包含详细的时间线检查清单和人物命名规则，皮尔洛出剧本后必须对照核查。

**规则：**
1. **时间线必须清晰标注年份**：每个关键事件前加 `"yyyy年，..."` 旁白，避免时间跳跃让读者困惑
2. **关键事件不能"一笔带过"**：如果真实历史中一段时期对故事发展至关重要（如 98-99 曼联三冠王赛季），必须用 ≥2 个 narrate 节点或 1 个 card 节点来展现，不能只写一句"三年过去了"
3. **真实人物名必须核对拼写**：Simone → Diego Simeoni（正确的阿根廷姓氏），C.罗 → Cristiano Ronaldo 等
4. **对话/独白要吻合当时的真实历史时间点**：例如"他们说我毁了英格兰"发生在 1998 年 7-8 月，不是 1999 年
5. **重大事件顺序不可调换**：如弗格森电话安抚发生在世界杯结束后立即，并非在全英公敌高峰之后

#### 写作铁律
- 第一人称：所有 narrate 是"我是 XXX"
- 数字模糊化：71483 名 → 7万多名
- 人名本地化：肯佩斯 → 阿肯
- 每段 ≤25 字
- 加粗标记用 **xxx**（引擎渲染抖动特效）
- 每章末尾：1 张历史档案卡 + teaser

#### 选择题设计

每章 1 道，选项分理解度层次：

| 选项 | 理解度 | 含义 |
|------|--------|------|
| A | +0~+5 | 表面认知 |
| B | +15~+25 | 深度共情 |
| C（可选） | +20 | 复杂性思辨 |

最终理解度决定结局分支（≥70 / 30-69 / <30）。

#### 抽卡机制（核心变现）

- 每剧 2-3 个抽卡点
- 卡池：好20% / 中50% / 坏25% / 隐藏5%
- 首抽保底不出"坏"
- 重抽成本：第1次=1激励视频，第2次起=2条，上限5次
- 抽到的可收藏，最终选一个继续主线
- 5次未抽到好结局 → 提示"1元解锁好结局"

### 阶段③ 画风锚定

#### 选择画风路线

| 画风 | 适用场景 | Prompt 风格词特征 |
|------|---------|-----------------|
| **写实体育摄影**（默认） | 真人传记、严肃叙事 | `photorealistic sports photography, 4K, Canon 1D, shallow depth of field` |
| **半写实漫画**（真实人物漫画化的推荐方案） | 真人故事+热血漫画风格，要求保留面部特征时使用 | `Portrait of [person] in manga-inspired style, semi-realistic face with detailed skin texture, his/her recognizable face with [specific facial features], manga effects on background/composition, face must be clearly recognizable as [person]` |
| **日式热血漫画**（纯漫画，仅适合非真人题材） | 虚构角色、青春燃向、夸张情绪 | `Japanese sports manga style, thick black outlines, cross-hatching, halftone dot screen, speed lines, explosive light effects, dynamic diagonal composition` |

#### ⚠️ 画风切换注意事项

如果用户要求从一种画风格式切换到另一种（如从写实→漫画），**所有 hero + panel 的 prompt 必须全部重写**，不能只改前几句。两种画风的构图语言不同：

| 维度 | 写实摄影 | 半写实漫画 | 日式漫画 |
|------|---------|-----------|---------|
| 构图 | `close-up portrait, wide shot, shallow depth of field` | 同写实但加 `dynamic manga-inspired composition` | `dynamic diagonal composition, extreme low angle, manga split-panel, speed lines` |
| 光影 | `golden hour, professional lighting, dramatic lighting` | 同写实 + `thick black rim light, dramatic manga-style lighting` | `dramatic chiaroscuro, high contrast dark-light split, spotlight` |
| 颜色 | 自然色温 | 同写实但加 `high saturation [color palette]` | `high saturation red gold black` |
| 面部 | 保持真人五官精度 | **semi-realistic with detailed skin texture; face must be clearly recognizable** | 日式抽象化，可能失去真人特征 |
| 背景处理 | `stadium crowd in background, bokeh` | 同写实 + `manga speed lines, halftone dot screen` | `halftone dot screen on crowd, silhouettes, black and white flashback` |
| 特殊效果 | 无 | `cross-hatching on shadows, speed lines, golden aura` | `cross-hatching, speed lines, explosive light burst, manga text overlay` |

**重要 — 真实人物漫画化的地雷（已踩坑）：**

纯漫画 prompt（`"Japanese manga style illustration of..."`）会让 GPT Image 2 把真实人物的面部特征抽象成泛化日式角色，导致**完全不肖似**。用户真实反馈：`"不像贝克汉姆了"`。

**解决方案：半写实漫画（semi-realistic manga）** — 面部保持写实精度，背景/光效/构图用漫画元素。已验证通过。

```
✅ 正确做法（半写实漫画 — v2 confirmed）:
Portrait of David Beckham in manga-inspired style, 1998 World Cup, 23 years old, short bleached buzz cut, England white #7, his recognizable face with chiseled jawline, narrow intense eyes, high cheekbones, standing at tunnel entrance..., semi-realistic face with detailed skin texture, dramatic manga-style lighting with thick black rim light, speed lines in background, halftone dot screen on shadows, high saturation red gold black, heroic low angle composition, face must be clearly recognizable as David Beckham

❌ 错误做法（纯漫画 — v1 rejected）:
Japanese sports manga style illustration of David Beckham at 1998 World Cup..., thick black outlines, cross-hatching shadows, halftone dot screen..., Captain Tsubasa style...
```

**半写实漫画 prompt 的四要素（v2 已验证通过 ✅ 不要再用纯漫画）：**
1. **身份锚定开头**：`"Portrait of [真实人物名] in manga-inspired style"`（不是 `"Japanese manga style illustration of..."`）
2. **面部特征锚点**：`"his recognizable face with [下颌线/眼睛/颧骨等具体特征描述]"`
3. **写实面部承诺**：`"semi-realistic face with detailed skin texture"`
4. **保脸硬约束结尾**：`"face must be clearly recognizable as [人物名]"`

这四条缺一不可。尤其是第 4 条是兜底指令，不能省略。

#### ⚠️ 生成前样张确认协议（新增，已踩坑）

在批量为所有 hero/panel 图片执行 gen.py 之前，**必须先抽 1 张 hero 样张让用户确认效果**，确认后再批量跑全部。这避免全部生成后发现方向性错误（如风格不对、面部不似）导致全量重做。

```bash
# 1. 先抽第1张 hero 样张
python3 gen.py "hero_1 的 prompt" --out raw/hero_01_test.png

# 2. 展示给用户看（用 send_message 或浏览器打开截图）
# 3. 用户确认后再跑全部
python3 gen.py --batch gen_all_tasks.json --out-dir raw/
```

**画风约束词模板（写实体育摄影）：**
```
Art style: [具体画风描述].
EYES must be half-lidded with lower sclera visible (sanpaku dead-fish eyes),
heavy brow ridge, blank cold stare, downturned corners of mouth.
NO brand logos, NO team badges, NO visible brand markings on clothing.
```

**画风约束词模板（半写实热血漫画 — 真实人物专用，v2 已验证通过）：**
```
Portrait of [人物名] in manga-inspired style.
[Semi-realistic portrait with face detail]:
  - his/her recognizable face with [具体面部特征: chiseled jawline, narrow intense eyes, high cheekbones 等]
  - semi-realistic face with detailed skin texture
[Manga effects on background/composition]:
  - dramatic manga-style lighting with thick black rim light
  - speed lines for motion
  - halftone dot screen on shadows and midtones
  - explosive golden light for climax moments
  - cross-hatching on fabric folds and shadows
  - dynamic angle composition
[Color palette]: high saturation [red gold black / specific colors per mood]
[Anti-Japanese-text constraint - MANDATORY]:
  - NO Japanese text, NO kanji, NO signboards with Asian characters
  - NO Japanese captions, NO Japanese speech bubbles in the image
  - All visible text must be English (newspaper, stadium signs, jerseys, scoreboards)
  - NO Japanese-style street signs, NO Japanese shop/store signs
  - The image background/textures may use manga effects (halftone dots, speed lines) but must NOT contain any readable text in any language unless it's English and historically accurate
Hard constraint (MUST end prompt): face must be clearly recognizable as [人物名]
```

**背景画风约束词模板（通用）：**
```
Art style: [具体背景画风描述].
COMPOSITION FOR MOBILE PHONE SCREEN:
vertical portrait orientation 9:16 ratio,
key visual elements positioned in UPPER 60% of frame,
LOWER 40% must be empty / dark / negative space (reserved for dialog box overlay),
main focal point at upper-third intersection.
```

**人物身份锚定字典：**
```
角色\t锚定描述
迭戈（瘦版）\t"a short stocky South American male footballer in his 30s, dark messy curly hair..."
```

### ⚠️ 图片生成速度与超时处理协议（踩坑经验）

#### 速度问题

GPT Image 2 API（通过 `gen.py` 调用）单张生成耗时 **1-5 分钟不等**，高峰期（中国晚间）可能持续超时重试。18 张 batch 总耗时可达 **25-40 分钟**。用户会抱怨\"怎么这么慢\"。

**加速方案：**

1. **并行运行多个 gen.py 进程** — 每张图独立，可并行 2-3 路：
   ```bash
   # 将 batch 拆为 N 个子文件，同时运行
   python3 gen.py --batch batch_part1.json --out-dir raw/ &
   python3 gen.py --batch batch_part2.json --out-dir raw/ &
   python3 gen.py --batch batch_part3.json --out-dir raw/ &
   wait
   ```

2. **但前提是 API Key 允许并行**（实测 GPT Image 2 支持至少 2 路并行而不超频）

3. **如果用户中途问\"怎么这么慢\"**：
   - 先检查实际生成了几张（`ls -lt raw/*.png | grep "$(date +%Y)"`）
   - 告知已完成数/总数 + 预计剩余时间
   - 如果超时错误堆积，kill 当前进程，重新跑剩余的（`gen.py --batch` 会自动 skip 已存在的文件）

#### 超时处理

`gen.py` 内置 3 次重试，每次超时 300s。如果 API 持续超时：

1. 检查网络/API 是否正常：`curl -s --max-time 5 https://ai.flashapi.top/v1/models`（或 config.py 中配置的 endpoint）
2. 如果个别图片反复超时，单独重试：
   ```bash
   python3 ~/.hermes/scripts/vns/gen.py "prompt_here" --size 1024x1024 --quality high --out raw/hero_?.png
   ```
3. 如果批量超时率高，降低 quality（`high`→`medium`）可加快速度

#### 中断恢复

gen.py 的 skip-if-exists 机制：`gen.py --batch batch.json --out-dir raw/` 如果 `raw/hero_X.png` 已存在就自动跳过。适用于中断后继续。

但注意：**生成了一半的 PNG 文件也会被视为\"已存在\"而跳过**。如果杀死进程时某张图正在写入（文件不完整），需手动删除该文件再重跑。

```bash
# 检查今日生成的文件，确认大小正常（hero/panel 通常 2-3MB）
ls -lh raw/*.png | grep "$(date +%Y)"
# 如果文件 <100KB 就是不完整的，手动删掉
```

**⚠️ 不要在用户表示\"慢\"时杀死进程重新搞** — 生成的图不会丢失，先汇报进度让用户知情。确认要中断后再 kill 并用剩余 batch 续跑。

### 阶段④ 视觉素材生成

**素材清单（每篇）：**

| 类型 | 数量 | 尺寸 |
|------|------|------|
| 场景背景图 | 5张（每章1张） | 1024×1024 → 压缩420px |
| 关键浮层插图 | 4-8张 | 1024×1024 → 压缩800px |
| 组件素材 | 按需 | 视组件而定 |
| 历史档案照片 | 3-5张 | 用户自上传 |

**Prompt 构造规范（真实人物必须遵守）：**

**⚠️ 已踩过的坑**：用户反馈贝克汉姆 H5 的图片"不匹配那几年的形象"。根因是 prompt 只写了 `"A dramatic portrait of David Beckham" + 中文对话`，没有年份/发型/球衣/年龄信息。GPT Image 2 自由发挥了通用形象，与 1998-2004 各时期的实际形象完全不符。

为真实人物写图片 prompt 时，**必须**包含全部身份锚定维度，不能只写 `"A portrait of XXX" + 剧情文本`。

| # | 维度 | 必须包含 | 示例 |
|---|------|---------|------|
| 1 | 年份/赛事 | 具体年份+比赛名 | "1998 FIFA World Cup" |
| 2 | 发型 | 具体描述 | "short bleached blonde buzz cut" |
| 3 | 球衣 | 球队+款式+号码 | "England white #7 jersey" |
| 4 | 年龄 | 数字年龄 | "23 years old" |
| 5 | 场景/球场 | 具体地名 | "at Stade de Marseille" |
| 6 | 情绪/表情 | 对应剧情情绪 | "young determined expression" |
| 7 | 构图 | 特写/中景/全景 | "close-up portrait" / "wide shot" |
| 8 | 光照/时段 | 自然光/黄昏/夜间 | "bright summer sunlight" / "floodlights" |
| 9 | 画风 | 写实体育摄影 或 日式热血漫画（见阶段③） | `photorealistic sports photography, Canon 1D look` 或 `Japanese sports manga style, thick black outlines, cross-hatching, speed lines` |

**反面案例**（踩坑重现——不要这样写）：
```
"A dramatic portrait of David Beckham. [对话]. cinematic digital painting, dramatic sports portrait, photorealistic, 4K..."
```
→ 只有名字 + 中文对话 + 通用画风词 → 无时代锚点 → GPT 自由发挥 → 形象与历史不符 → 用户体验差。

**正确案例**（9 个维度全齐 — 写实体育摄影风）：
```
"David Beckham in 1998, 23 years old, short bleached blonde buzz cut hair, England national team white jersey #7, standing on the pitch at Stade Félix-Bollaert, Lens during the 1998 FIFA World Cup group stage against Colombia, young determined expression, bright summer sunlight, photorealistic sports photography, 4K, Canon 1D, shallow depth of field, green grass background, emotional moment, wide shot"
```

**正确案例**（9 个维度全齐 — 日式热血漫画风）：
```
"Japanese sports manga style illustration of David Beckham at 1998 World Cup, 23 years old, short bleached buzz cut, England white #7, standing at the tunnel entrance of Stade Félix-Bollaert Lens, dramatic side lighting, thick black outlines, cross-hatching shadows, halftone dot screen on shadows, speed lines radiating from behind, explosive golden light from the stadium entrance, high saturation red white gold, dynamic low angle shot looking up at him, heroic determined expression, Captain Tsubasa style, confident smirk, overwhelming protagonist presence"
```

**⚠️ 重要：prompt 写完必须先给用户过目再生成。** 不要直接提交批量生成。用户要检查 prompt 中的年份、球队、发型等细节是否准确。这是硬性要求。如果用户需要检查所有 prompt，应使用飞书表格列出每条 prompt 的完整各项供用户逐条核查。

**每张 hero/panel prompt 写完后逐项自检（已踩坑检查表）：**

**中文对话文本禁止塞入英文 prompt**：中文对话/旁白文本放入 GPT Image prompt 会导致 GPT 错误解析，生成不可预测的内容。prompt 必须纯英文。

#### ⚠️ 历史人物 prompt 事前核查协议（真实人物必做，已踩坑）

**触发条件**：剧本涉及真实历史人物（球员/教练/名人）且需要生成真人形象图片时，在写 prompt 之前必须先执行此协议。

**背景**：贝克汉姆篇因为直接写 `"A portrait of David Beckham"` 未查年份/发型/球衣，导致生成的图与 1998-2004 的真实形象完全不匹配。用户反馈"图片有问题，不匹配那几年的形象"。后续修正中发现**1998年发型也被写成了板寸（实际为中长发）**，审计环节同样漏检。

**核查七步：**

| # | 步骤 | 核查内容 | 反面案例 |
|---|------|---------|---------|
| 1 | 赛事/年份 | 该人物在剧本节点的年份效力于哪支球队？参加什么比赛？ | 把 2001 年预选赛写成 "2002 FIFA World Cup" |
| 2 | 球衣/号码 | 该年份穿哪个俱乐部/国家队的几号球衣？颜色？ | 1999 欧冠决赛写 "曼联客场球衣" → 实际穿主场红色 |
| 3 | 发型/造型 | 该年份该人物的具体发型特征（查图片参考） | 2001 年希腊预选赛写 "莫西干头" → 莫西干是 2002 世界杯专属发型 |
| 4 | **首秀/关键事件核实** | **该具体比赛是 player 的哪一场关键里程碑？具体信息：对阵谁、第几分钟出场、首发还是替补、穿什么颜色、进球时间** | 贝克汉姆首秀写 "vs 突尼斯" → 实际是对罗马尼亚第 32 分钟替补登场。凭印象以为首秀就是第一场比赛，没查 match report |
| 5 | 球场/地点 | 当时在哪个具体球场踢的比赛 | hero_1 写 "Stade de Marseille" → 实际是 Stade Félix-Bollaert, Lens |
| 6 | 年龄/状态 | 人物当时的实际年龄和竞技状态 | 2004 欧洲杯时 29 岁，不是 2003 年的 28 岁 |
| 7 | **发型细节深入** | 不止确认发色和大致风格，要确认：长度（耳上/耳下/齐肩）、两侧剃度、偏分方向、有无定型产品（竖立/自然垂落） | 把 1998 年耳下中长发写成板寸 |

**参考搜索方法**：
- Wikipedia 人物页（"Club career" 章节列出年份→球队）
- Wikipedia 比赛条目（"Venue" 字段列出球场名）
- 比赛照片/视频搜索（确认发型、球衣等视觉细节）
- 该人物 Iconic Hairstyles 文章/图集（确认各时期发型）

**球员发型时间线速查表（足球人物通用参考框架）：**

足球运动员的发型随时间变化很快，同一人物可能赛季之间判若两人。不要假定"这个人长发/短发/光头"。必须按年份核查。

```
核查维度：Year → Hairstyle → Kit/Uniform → Age → Venue
```

**贝克汉姆发型时间线（已验证，已修正1998年错误）：**

| 年份 | 发型 | 球衣 | 赛事/场景 |
|------|------|------|----------|
| 1998 | **金色中长发，侧分（medium-length side-parted blonde hair）** ⚠️ 曾误记为"板寸" | 英格兰红客场#7 / 白主场#7 | 法国世界杯（首秀vs罗马尼亚，首球vs哥伦比亚） |
| 1999 | 稍长金发偏分（longer blonde, side-parted） | 曼联红 | 赛季/三冠王/欧冠 |
| 2000 | 相似风格，发色更自然 | 英格兰白#7 / 曼联红 | 欧洲杯/赛季 |
| 2001 | 侧分中长金发（side-parted medium-length blonde）⚠️ 曾误记为"短刺头" | 英格兰白#7 / 曼联红 | 希腊预选赛绝平 |
| 2002 | 极短漂白板寸（very short bleached buzz cut #1-2 length）⚠️ 曾误记为"莫西干" | 英格兰白#7 | 韩日世界杯 |
| 2003-04 | 偏分深金发（longer darker blonde, roots showing） | 皇马白 | 转会皇马初期 |
| 2004 | 短发鬓角剃（short with shaved sides） | 英格兰白#7 | 欧洲杯 |

**每个查询结果保存为 prompt 的具体维度**，不是泛泛的 "根据真实历史修改"。核查完成后逐行填入 9 维度 prompt 模板。

**⚠️ 重要：prompt 写完必须先给用户过目再生成。** 不要直接提交批量生成。用户要检查 prompt 中的年份、球队、发型等细节是否准确。这是硬性要求。

**每张 hero/panel prompt 写完后逐项自检（已踩坑检查表）：**
- [ ] 年份明确指定（数字年份，不是"in the 90s"）
- [ ] 发型精确到该年份的发型特征
- [ ] 球衣/制服匹配该年份
- [ ] 年龄数字准确
- [ ] 场景/球场地名具体（查阅了比赛记录确认）
- [ ] 情绪/表情对应剧本当前节点
- [ ] 构图类型明确（portrait/scene/wide shot/close-up）
- [ ] 每张 prompt **独立编写**，不复制粘贴统一模板
- [ ] 同一角色的不同年代节点有明显视觉区分度
- [ ] prompt 为纯英文，无中文文本
- [ ] **已对照 Wikipedia 或可靠来源核查过年份/球队/球场/发型**（这一步是新加的，前面踩过坑）
- [ ] 比赛性质准确（预选赛 vs 正赛，不要混）
- [ ] 球场/地点的名具体且正确（查 Wikipedia match page 的 `Venue` 字段确认）
- [ ] 发型精确到该年份的发型特征（足球运动员发型变化快，不要用最出名的造型覆盖所有年代）
- [ ] **prompt 已展示给用户审阅再生成**（用户要逐条确认）
- [ ] 画风统一（所有 hero/panel 都用同一种画风，不要写实和漫画混用）

**自检清单**（每张 hero/panel prompt 写完后逐项打勾）：
- [ ] 年份明确指定（数字年份，不是"in the 90s"）
- [ ] 发型精确到该年份的发型特征
- [ ] 球衣/制服匹配该年份
- [ ] 年龄数字准确
- [ ] 场景/球场地名具体
- [ ] 情绪/表情对应剧本当前节点
- [ ] 构图类型明确（portrait/scene/wide shot/close-up）
- [ ] 每张 prompt **独立编写**，不复制粘贴统一模板
- [ ] 同一角色的不同年代节点有明显视觉区分度
- [ ] prompt 为纯英文，无中文文本

**GPT Image 2 调用：**
```
Endpoint: https://ai.flashapi.top/v1/images/generations
Model: gpt-image-2
Size: 背景1536x1024 / 人物1024x1024
Quality: medium（关键主视觉用high）
Timeout: 300s
Retry: 3次
```

**图片压缩参数：**
```
背景图: WebP, max_width=828, quality=90
浮层图: WebP, max_width=800, quality=78
hero图: WebP, max_width=900, quality=85
档案照片: JPEG, max_width=800, quality=82
```

### 阶段⑤ 音效

**类型：**
- BGM（循环，切换时淡出/淡入）
- SFX（单次播放）
- AMB（环境音循环）
- Typing（打字机音效）

**规范：**
```
SFX: mono, 48kbps, ≤200KB
BGM: stereo, 128kbps, ≤5MB
存放: dist/assets/（外链，不内嵌）
```

**免费音源：**
- pixabay.com/music（CC0，推荐）
- freepd.com（Public Domain）
- incompetech.com（CC BY）
- uppbeat.io（免费档每月10次）

**Typing 音效（Web Audio API 原生方案，不依赖外部文件）：**

引擎不再依赖 `typing.mp3` 文件。使用 Web Audio API 原生生成 click 音序列：
- 每秒 ~12 次（80ms 间隔）的短促方波 click
- 每次 click 频率在 600-1000Hz 间随机（模拟机械键盘/打字机质感）
- 每 click 时长 50ms，exponentialRampToValueAtTime 平滑衰减
- 自动在 3s 或 40 次 click 后停止（防止无限）
- 静音状态下不创建 AudioContext（节省资源）
- 完全不需要预先加载任何音频文件

**BGM 章节自动切换系统：**

引擎已内建 `BGM_MAP` 对象，将章节名映射到 BGM 文件。当 `scene(chapter)` 节点触发时自动切换 BGM：

```javascript
const BGM_MAP = {
  "第一章：闪耀新星": { file: "bgm_01.mp3" },
  "第二章：坠入深渊": { file: "bgm_02.mp3" },
  // ... 按章节命名 bgm_01~bgm_06.mp3
};
```

**BGM 文件命名规则**：`bgm_01.mp3` ~ `bgm_06.mp3`，放在 `dist/assets/` 目录。每篇 H5 根据章节数决定用几个文件。对应关系维护在项目内的 `dist/assets/README.md` 中，标注原始曲目名和来源。

**场景过渡音效：**

`playTransitionTone()` 在 `scene(chapter)` 触发时自动播放：0.5s 升调 sine wave（220Hz→330Hz），提示玩家章节切换。

**免费音源推荐（CC BY 4.0）：**
- Scott Buckley (scottbuckley.com.au) — 史诗管弦乐，适合足球叙事。推荐曲目：Bring Me The Sky, The Distant Sun, The Creator, A New Beginning
- pixabay.com/music（CC0）
- freesound.org — 球场环境音（stadium crowd atmosphere）

**署名要求**：Scott Buckley 曲目需注明 "Music by Scott Buckley – released under CC BY 4.0"

### 阶段⑥ H5 引擎

引擎模板（找小李飞蛋拿 `game3/index.html` 或 `game6/index.html`）。

**核心组件清单：**
- HUD（章节名+主角信息+理解度进度条）
- 场景层（渐变背景+图片叠加）
- 对话框（打字机 70ms/字，加粗抖动）
- 浮层插图（4角浮动）
- 选择题面板
- 历史档案卡
- 抽卡面板（含翻转动画）
- 激励视频墙
- 结局成就卡
- 音效控制（静音开关）

**情节展示组件库：** comic / hero / profile / evidence / comments / timeline / map / relationship / archive / scoreboard

**动画节奏（已微调优化质量）：**
- Hero 展示：**5s** 自动消失（不低于 4s，给情绪节点呼吸空间）
- Scene 章节：**2.5s** 过渡 + 章节标题充分展示
- Panel 浮层：出现时 fade-in 100ms，4s 后自动淡出
- Dialog 打字速度：70ms/字，** 加粗标记 ** 用 100ms/字
- 场景切换锁定：1.5s 内不可交互（比 2.5s auto-advance 有 1s 重叠，不漏帧）

**字体规范（CSS 变量体系）：**
- 在 `:root` 中定义：`--font-serif: "Noto Serif SC", "Songti SC", Georgia, serif` 和 `--font-sans: -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`
- **标题/正文主字体**：`var(--font-serif)`（足球杂志庄重感）——应用于 body、dialog 文本、hero 标题、card 标题、choice 按钮、gacha 问题
- **辅助文本/小字**：`var(--font-sans)`（中文清晰可读）——应用于启动页副标题等
- 导入方式：Google Fonts CDN 或系统字体回退，不用 `@import` 以免阻塞渲染
- `#hud .chapter`：font-weight 700, font-family var(--font-serif), letter-spacing 0.5px
- `#hero-title`：font-size 22px, font-weight 800, color gold shadow, line-height 1.5
- `#launch-title`：font-size 28px, font-weight 900, letter-spacing 1px

**渲染铁律（不遵守则出 bug）：**
- 图片必须先于文字出现（panel/narrate 顺序不可颠倒）
- 场景切换清空所有浮层（clearPanels 必须在 setBg 前调用）
- 对话框使用 textContent 累加（不用 innerHTML，防 XSS 且兼容打字机）
- 照片/浮层使用 object-fit: contain（防止拉伸变形）
- 场景切换锁定 1.5s（不可交互期，防止双击跳过 scene）
- 选择题选中后高亮 0.4s 再推进（给玩家视觉反馈）

### 阶段⑦ 激励广告接入

**SDK：UnifiedRewardSDK**（找小李飞蛋拿 `unified-reward-bridge.js`）

**策略：仅抽卡重抽触发广告，正片无广告**

**关键配置：**
```javascript
window.__UNIFIED_REWARD_CONFIG = {
  platform: 'auto',
  sceneId: 'leagueCollect_14',
  behavior: {
    callbackTimeout: 3000,
    preloadCallbackTimeout: 3000,
    showCallbackTimeout: 3000,
    preloadAllowTimeout: true,
    showAllowTimeoutAsSuccess: true,
    preloadMaxAge: 600000
  }
};
```

### 阶段⑧ 打包

**产出结构：**
```
dist/
├── index.html          # 主文件（图片base64内嵌、SDK内嵌）
└── assets/
    ├── bgm.mp3
    └── ... (音效文件)
```

**大小控制：**
```
HTML ~2-2.5MB（4G网络≤3s加载）
音效 ~3-5MB（异步加载不阻塞首屏）
总计 ~5-7MB
```

### 阶段⑨ 验收

**量化标准：**
- 首屏 ≤2s（4G）/ ≤4s（弱网）
- 低端 Android 无掉帧
- 广告失败不阻塞主线
- 埋点完整：enter/chapter/node/ad/end

**必备埋点：** game_enter / chapter_start / node_choice / card_open / gacha_draw / ad_request / ad_complete / game_end

**推广素材：** banner（750×421）/ 信息流封面（360×270）/ 圈子封面（600×800）

---

## 故事模板库（快速选题参考）

| 模板 | 情绪链 | 适合文章 |
|------|--------|---------|
| 爽文逆袭型 | 被轻视→蓄力→打脸→加冕 | 冷门爆冷、老将复出 |
| 真假白月光 | 美好→裂缝→反转→理解 | 传奇人物、经典比赛 |
| 群像热血型 | 集结→分歧→目标→燃点 | 世界杯、球迷文化 |
| 悬疑扒皮型 | 异常→追问→冲突→揭底 | 黑哨、禁药、转会内幕 |
| 救赎陪伴型 | 低谷→试探→伤口→托举 | 伤病复出、退役回望 |
| 宿敌拉扯型 | 看不顺眼→合作→碰撞→惺惺相惜 | 队友竞争、教练球员 |
| 命运遗憾型 | 高光→失误→不可逆转→回望 | 悲剧比赛、告别 |
| 反派洗白型 | 厌恶→处境→代价→复杂评价 | 争议人物 |

---

## 执行入口命令

Gu 触发一句话即可启动全流程：

> "把这篇 [文章URL] 做成互动H5游戏，用 [模板类型] 模板"

Hermes 自动调度：
1. 读取文章内容（懂球帝 API）
2. 皮尔洛输出剧本 DSL
3. 展示画风样张给 Gu 确认
4. 内斯塔批量生图
5. OpenClaw 找音效
6. Claude Code 组装 HTML
7. 打包输出
8. Codex 验收
