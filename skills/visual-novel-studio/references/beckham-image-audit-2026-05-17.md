# Beckham VNS 全量图片审计实录（2026-05-17）

## 背景

Beckham 篇 H5 游戏（1998-2002 四年的救赎之旅）29 张图片全部由 AI 生成后，用户逐张验收发现大量失实问题。本 session 首次实践"Kanban 透明化 + 每步用户审核"工作流。

## 发现的问题

### 球衣颜色错误（5张）
hero_1, hero_2, hero_3, panel_1, panel_2 的 prompt 写了"England white #7"
→ 实际英格兰 1998 年对哥伦比亚/阿根廷穿的是红色客场球衣

### 发型年代错误（8张——含新增的1998年错误）
hero_1~hero_5, panel_1/2/3/p7204: 1998 年写「短漂白板寸」→ 实际是金色中长发侧分（耳下长度，非板寸）。**该错误已在 SKILL.md 发型时间线表中修正。**
hero_8: 2001 年写「短刺头」→ 实际是侧分中长金发
hero_9, hero_10, panel_8, panel_9: 2002 年写「莫西干」→ 实际是极短金色板寸

### 时间线超范围（3张）
hero_11 (Real Madrid 2003-04), hero_12 (Euro 2004), hero_13 (Triptych to 2004)
→ 剧本只到 2002 年

### 日文文字（所有 manga 风格图片）
manga-style prompt 导致 AI 生成日文招牌/标语

## 修复清单

### P0 必须重做（5张）
hero_2, panel_2 → 球衣颜色改红色客场
hero_8 → 发型改侧分中长金发
hero_9, panel_8 → 发型改短板寸

### P1 建议修（5张）
hero_1, hero_3, panel_1 → 球衣颜色改红色客场
hero_10, panel_9 → 发型改短板寸

### P3 时间线修正（3张）
hero_11, hero_12, hero_13 → 改为 2002 线

## 参考照片搜索

最终共找到 15 张真实历史照片，来源分布：
- Getty Images editorial (browser mode): 8张
- Wikipedia Commons: 5张（含高质量 1.7MB）
- 新闻文章嵌入图: 2张

### 搜索技巧
1. Getty 用 browser 模式（curl 被拦截）
2. Wikipedia Commons 搜比赛条目
3. BBC/Guardian 回顾文章内嵌图
4. max_iterations 从 50 调到 150

### 找不到的图
- 谢林汉姆/索尔斯克亚特定进球瞬间 → Wikipedia 只有比赛缩略图
- 西蒙尼换球衣 → 版权照片
- 《太阳报》头版 → 新闻档案版权

## 工作流改进

### 第2轮审计（2026-05-17）：叙事流审计 + 章节重构 + 线索照片复用

#### 发现的新问题

**章节归属错误（结构性）**：hero_2（任意球罚出）和 panel_2（任意球场景）描述的是哥伦比亚任意球首球——正面时刻，却被放在「坠入深渊」章节。正确归属：「闪耀新星」。

**根因**：只检查了单张图的事实维度（球衣、发型、情绪），没有检查该图所在的章节是否符合叙事流。

**修复流程**：全量重构 6 个章节：
1. ch1 闪耀新星：罗马尼亚首秀 + 哥伦比亚首球（含 hero_2/panel_2 移入）
2. ch2 坠入深渊：阿根廷红牌事件（原 ch3 内容移入）
3. ch3 全英公敌：震惊 + 离场 + 媒体 + 抑郁（原 ch4+ch5 内容合并）
4. ch4 救赎之路：弗格森谈话 + 1999 三冠王
5. ch5 复仇与和解：队长任命 + 2001 希腊绝平
6. ch6 涅槃重生：2002 世界杯纯享版

#### 复用未引用照片

`photos/` 目录已有 `simeone_shirt_exchange.jpg`（2002 年 Beckham 与西蒙尼赛后交换球衣），之前未被任何卡片引用。发现后用于 panel_9，描述改为「赛后与西蒙尼交换球衣——四年的恩怨在此刻和解」。

#### 无法搜到的参考图

- 《太阳报》"10 HEROES 1 TRAITOR"头版 → 多次搜索无果，版权保护严格

#### 新增功能

- 审计 HTML 上传参考图功能（用户自己找的图拖/选上传到审计板）

### 事实核查教训：首秀数据错误

hero_1 原描述「vs 突尼斯穿白色主场」——实际首秀是对罗马尼亚（小组第二场，Stade de Toulouse）第 32 分钟替补登场，穿红色客场。

**根因**：默认「首秀 = 小组赛第一场」的关联印象，没查 Wikipedia match report 确认出场阵容。

**教训**：首秀/关键里程碑事件不能靠印象写，必须查 match report 的 Starting XI vs Substitutes 名单核实。已在 visual-novel-studio SKILL.md 核查协议中新增「首秀/关键事件核实」维度。

### 新增功能：审计 HTML 自定义参考图上传

用户要求能上传自己找的参考图到审计 HTML。实现：每张卡 ref 区域下方加 upload button → FileReader data URL 内联显示 → 导出 JSON 记录 hasCustomRef + filename。详见 audit-html-toolkit.md。

### 用户核心要求

用户核心要求：每步可查，每步可调，不要一口气做到底再交付。

已实现：
1. Kanban 看板（6 任务链 T1-T6，依赖自动传导）
2. 每步完成后推送飞书摘要，用户确认后才推进
3. HTML 审计板（交互式审核，勾选+写意见→导出 JSON）
4. 可调节审核密度（全人工→关键节点→全自动）

## 技术配置变更

- OpenClaw toolsets: 从 `["terminal","file"]` 改为 `["terminal","file","web","browser"]`
- agent-registry.json capabilities: 新增 `web_browsing`, `image_search`, `visual_analysis`
- config.yaml max_iterations: 50 → 150
