---
name: obsidian-knowledge-base
description: "Obsidian 知识库文件操作规范 — 文件归类和存放规则。用户 Gu 的个人知识库 + 懂球帝工作库的双 vault 管理。"
tags: [obsidian, knowledge-management, productivity, file-organization]
---

# Obsidian 知识库操作规范

## 🔴 首要规则：写文件前必须先读 CLAUDE.md

**这是最高优先级规则。每次向 Obsidian 写入文件前，必须先做这件事。**

1. 读取 `CLAUDE.md`（个人知识库根目录）
2. 对照当前文件内容，逐条确认归属哪个目录
3. 如果心里有"大概放这里就行"的念头 → **那就是需要确认的信号**
4. 确认判断与 CLAUDE.md 规则一致后，再写入

```bash
# 个人知识库（必须读）
cat "/Users/gu/Library/Mobile Documents/iCloud~md~obsidian/Documents/个人知识库/CLAUDE.md"
```

> ⚠️ 历史教训：这个技能已经写了"写前先读 CLAUDE.md"，但我仍然犯了 3 次文件位置错误。原因不是不知道这条规则，而是**觉得"大概对"就动手了**。如果你读到这里却仍然凭感觉猜目录，把这句话重读一遍：**读 CLAUDE.md 不是可选项。**

## 目录结构（CLAUDE.md 定义）

```
0-收集箱/     ← 快速捕获入口，内容待分类
1-客户/       ← 客户关系资产（跨项目长期有效）
2-项目/       ← 进行中的具体项目（有生命周期）
3-知识/
  ├── raw/    ← 不可变的事实来源，只读不写（AI 不修改此文件夹）
  └── wiki/   ← 由 AI 维护，存放结构化知识
4-归档/       ← 已结束的项目和过期内容
```

## 各目录规则

### 0-收集箱
- **用途**：刚搜集的原材料、还没分类处理的快速捕获内容
- **适合放**：网页剪藏、调研收集、竞品分析、随手记的笔记
- **适合放**：从飞书/网页/搜索引擎收集来的未经加工的信息
- 这是**刚收集的资料**的默认位置

### 1-客户
- **用途**：客户关系资产（跨项目长期有效）
- **适合放**：客户联系人、人物背景、沟通风格、客户关系记录
- **不要放**：具体项目的执行材料、市场调研报告、竞品营销动作分析、行业研究
- `1-客户/` 的规则原文是"存放客户关系、人物背景、沟通风格等跨项目有效的信息"—竞品调研不属于这些
- 与 `2-项目/` 通过 wikilink 互联

### 2-项目
- **用途**：进行中的具体项目（有生命周期）
- **适合放**：方案、执行手册、会议记录等**项目内**的材料
- 项目结束后整体移入 `4-归档/` 
- 每个文件顶部注明所属客户链接

### 3-知识/raw
- **用途**：不可变的事实来源
- **规则**：AI **不修改**此文件夹中的任何内容，作为"原材料仓库"

### 3-知识/wiki
- **用途**：结构化知识，由 AI 维护
- **适合放**：根据 raw/ 素材提炼出的方法论、工具、概念
- 保持精炼、可复用、相互链接
- 入口文件：各主题目录下的 `index.md`
- **注意**：营销方案、竞品调研、客户资料等业务内容，不要放到 `wiki/AI与Agent/` 下

### 4-归档
- **用途**：已结束的项目和过期内容

## 常见错误（pitfalls）

1. ❌ **凭感觉猜分类。不读 CLAUDE.md 就动手。→ 必须先读 CLAUDE.md 再确认。**

   **这是本次对话中犯的最严重的错误。** 用户连续纠正了 3 次文件位置——首先放到 `wiki/AI与Agent/`，然后移到 `懂球帝工作/蒙牛/`，然后移到 `1-客户/蒙牛/`，最后才放对 `0-收集箱/`。用户质问：**"你之前怎么不知道看Claude文件？"**
   
   这个技能里面已经有"写前先读 CLAUDE.md"的规则，我读了，也知道了，但**在下判断时直接绕过**了。原因：心里想的是"大概放这里就行"，没有逐条对照规则做确认。**读 CLAUDE.md 不是走形式，是真的要一条一条对。**

2. ❌ 把工作调研/客户资料放到 `3-知识/wiki/AI与Agent/` 下
   - 这是 AI/Agent 技术区，不是业务资料区
   - **本次教训**：把蒙牛vs伊利世界杯营销动作放到了 AI 技术区

3. ❌ 把竞品调研/市场分析放到 `1-客户/` 下
   - `1-客户/` 只有客户关系资产（联系人、沟通风格），不放市场研究
   - **本次教训**：把蒙牛vs伊利竞品分析放到了 `1-客户/蒙牛/`

4. ❌ 把刚搜集的原始信息直接写到 `3-知识/wiki/`
   - wiki 是精炼后的结构性知识，不是原始收集

5. ❌ 把工作内容放到 `懂球帝工作/` vault 里
   - **用户明确说过：不分个人和工作的库，都是在个人里**
   - 所有内容（个人认知+工作资料）都在**个人知识库**这一个 vault 里
   - 懂球帝工作库仅作为历史遗留或特定用途，**AI 默认不写入**

6. ❌ **用户给了具体反馈后仍然犯同样的分类错。**
   - 用户纠正一次后，应该**停下手检查 CLAUDE.md 规则**，而不是继续凭感觉换位置
   - 第一次放错后，后续每次移动前都应该重新读 CLAUDE.md 确认

## 判断流程图（快速决策）

```
文件内容是什么？
├─ 刚搜集的网页/调研/未分类信息 → 0-收集箱/
├─ 客户联系人/背景/沟通记录 → 1-客户/
├─ 项目方案/执行手册/会议记录 → 2-项目/
├─ 精炼后的概念/方法论/工具知识 → 3-知识/wiki/
├─ 原始素材（微信收藏/剪藏/手动记录）→ 3-知识/raw/（AI 不写）
└─ 已结束项目 → 4-归档/
```

## 双 vault 说明

用户有两个 Obsidian vault：
- **个人知识库**（默认）：iCloud Drive → `/Users/gu/Library/Mobile Documents/iCloud~md~obsidian/Documents/个人知识库/`
  - ❗ **这是唯一 AI 应该写入的 vault**。承载个人认知 + 工作内容（客户、项目）的统一知识库。
- **懂球帝工作库**：`~/Documents/懂球帝工作/`
  - 历史遗留，仅用户手动使用
  - AI 默认不写入此 vault

## 常用路径速查

```bash
# 个人知识库 CLAUDE.md（必须先读）
"/Users/gu/Library/Mobile Documents/iCloud~md~obsidian/Documents/个人知识库/CLAUDE.md"

# 收集箱
"/Users/gu/Library/Mobile Documents/iCloud~md~obsidian/Documents/个人知识库/0-收集箱/"

# 客户目录
"/Users/gu/Library/Mobile Documents/iCloud~md~obsidian/Documents/个人知识库/1-客户/"

# 项目目录
"/Users/gu/Library/Mobile Documents/iCloud~md~obsidian/Documents/个人知识库/2-项目/"
```

## 飞书文档读取（feishu_doc_read 失效时的替代方案）

飞书文档读取的详细方案存储在 `references/feishu-doc-access.md` 中。

> **核心问题**：`feishu_doc_read` 工具仅在"飞书评论回复上下文"中可用，普通对话中无法调用。
> 
> **首选替代方案**：用 `lark-cli`（已安装，见系统环境配置）。一行搞定，不需要手动管理 token。
> ```bash
> lark-cli api GET "/open-apis/docx/v1/documents/{doc_id}/raw_content" --format pretty
> ```
> 
> **fallback**：手动调飞书 API（详见 reference 文件）。只有 lark-cli 不可用时才用这个。

## iCloud 文件死锁（Resource deadlock avoided）

详见 `references/icloud-deadlock-workaround.md`。

**核心问题**：macOS iCloud Drive 同步中文件被临时锁定时，`read_file`/`write_file`/`cat` 均可能报 `Resource deadlock avoided`。

**快速解决**：
1. `brctl evict <file_path>` 从 iCloud 驱逐文件
2. 使用 `write_file` 工具（不走终端，可绕过死锁）
3. 或用 `mv <tmp_file> <target_path>` 替换文件（绕过文件锁）
4. 或用 Python `open()` 重试几次（`time.sleep(1)` 间隙）

## 内容撰写规范

- **提炼而非堆砌**：从 raw/ 中提取核心观点，而非简单复制
- **结构化呈现**：使用表格、列表、分点提升可读性
- **链接为王**：建立 wiki/ 内部双向链接 `[[...]]`，形成知识网络
- **持续进化**：每次对话都可能发现新知识，更新或创建 wiki 条目

## 主动文档化触发器

完成以下类型的任务后，**必须主动**创建或更新 wiki 条目（不等用户要求）：

| 触发事件 | 文档动作 | 示例 |
|---------|---------|------|
| 新工具安装/部署成功 | 创建 wiki 条目，含架构、安装步骤、端口、已知问题 | 安装 Open Design → 创建 [[Open Design笔记]] |
| Bug 修复完成 | 在相关工具文档中更新"已知问题"部分 | better-sqlite3 编译失败 → 更新已知问题表 |
| 飞书/外部文档读取完成 | 在 0-收集箱/ 创建素材笔记，链接到相关工具/客户 | 读取蒙牛方案 → 存 0-收集箱/ |
| 架构/配置变更 | 更新现有 wiki 条目中的相关部分 | API Key 更换 → 更新大模型API配置手册 |
| 用户发链接要求"了解一下"/"你看看这个" | 用 External Content Ingestion 工作流处理（见下方） | 小红书帖子 → 提取→验证→映射→文档化 |

**工作流**：安装验证 → bug 检测 → no bug → 立即更新 wiki → 告知用户已更新

## 外部内容摄入（External Content Ingestion）

当用户发链接要求"了解一下""你看下这个"时（如小红书/博客/视频教程），Obsidian 侧的工作流：

### 触发来源

完整的工作流定义在 `hermes-knowledge-architecture` 技能的 **External Content Ingestion** 段落。

### Obsidian 侧的步骤（摘录）

1. **提取内容** — browser_navigate / browser_get_images / OCR
2. **理解归类** — 判断是工具/方法论/灵感参考
3. **映射到现有工具** — 逐项对比我们的能力
4. **🧪 关键：源码验证** — 在搜索 Hermes Agent 源码确认功能是否存在，**不要仅凭帖子说法就下结论**
5. **文档化** — 创建 `wiki/AI与Agent/<topic>-参考.md`，更新 `index.md`

### 常见错误（新增）

- ❌ **误判帖子归属的系统** — 如果帖子同时提到 Hermes 和 OpenClaw，逐个功能验证它属于哪个系统。不要因为帖子里提到了一个名字就认定所有功能都属于那个系统。
- ❌ **写"缺X"而不先做源码验证** — 帖子里说"缺字幕抓取"但 Hermes 已经有 `youtube-content` skill。写文档前必须确认真缺还是假缺。
- ❌ **创建新文件后不更新 index.md** — 每个新 wiki 文件都要在 `index.md` 的"工具与集成"或主体表格中添加链接。

### 相关技能

- **[[hermes-knowledge-architecture]]** — 完整的外部内容摄入工作流定义，含映射表格式和 pitfall 列表
- **[[browser-automation-for-blocked-sites]]** — 小红书等图片轮播页内容的提取方法
