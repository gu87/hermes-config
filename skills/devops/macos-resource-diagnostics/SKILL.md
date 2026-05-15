---
# macOS 资源诊断

## Overview

Gu 的运行环境是 **MacBook Air M1，8GB 内存，228GB 硬盘**。这是一个资源受限的环境，很多本地 AI 模型/工具跑不动或会严重拖慢系统。做任何「本地部署推荐」之前，必须先检查系统规格。

本 skill 定义了一套 APFS 感知的磁盘分析流程 + 系统健康检查方法。

agents: [nesta, hermes]
---
## When to Use

- Gu 拒绝你的软件/工具推荐时 — 先查他机器配置（`system_profiler SPHardwareDataType`）
- Gu 问「硬盘怎么又满了」或「能不能清理」 — 执行完整磁盘分析
- **推荐本地运行的 AI 模型/服务前 — 先查配置再建议，不等他说「不用」才知道跑不动**（典型例子：MOSS-TTS-Nano → 查 MacBook Air M1 8G RAM 后发现确实带不动）
- Gu 说机器卡/慢 — 检查 CPU/Memory 压力和磁盘剩余

**Don't use for**:
- 远程服务器磁盘分析（这是 macOS 专用的）
- 用户明确说「不用查了，帮我/我自己看」

---

## 系统规格速查

```bash
# 硬件概览（RAM、芯片、型号）
system_profiler SPHardwareDataType

# 内存大小（字节转GB：/1024^3）
sysctl hw.memsize

# CPU 核心数
sysctl hw.ncpu

# 磁盘 APFS 真实用量
diskutil apfs list | grep -E "(Capacity In Use|Volume Used|Purgeable)"
```

Gu 的机器底线：
- **M1、8GB RAM** — 大部分本地 LLM/TTS/模型跑不动
- **228GB 硬盘** — 数据卷通常 170-180GB，可用通常 < 40GB
- 无独立 GPU，推理靠 Neural Engine 或 CPU

---

## APFS 磁盘分析流程

### 1. 先查真实数据卷用量

`df -h /` 的 `Used` 列是 APFS **非 purgeable** 已用空间，不是全貌。
用 `diskutil apfs list` 查 Data 卷的 `Capacity Consumed`：

```bash
# 真实用量
diskutil apfs list | grep -A5 "disk3s5"

# 可用空间（含 purgeable）
df -h /
```

### 2. 分层扫描大目录

从最可能大的开始，逐层深入：

```bash
# 用户目录 TOP 级
du -sh ~/Desktop/ ~/Documents/ ~/Downloads/ ~/Movies/ ~/Pictures/
du -sh ~/Library/Caches/
du -sh ~/Library/Application Support/

# 隐藏的大目录
du -sh ~/.hermes/ ~/.deepseek/ ~/.ollama/ ~/.local/share/uv/
du -sh ~/.cache/

# 微信数据（沙箱容器内）
du -sh ~/Library/Containers/com.tencent.xinWeChat/
du -sh ~/Library/Containers/com.tencent.xinWeChat/Data/Library/Application\ Support/com.tencent.xinWeChat/*/*/ 2>/dev/null | sort -rh | head -5
# Message/ = 聊天记录+媒体缓存，Downloads/ = 微信下载，Movies/ = 视频

# 应用程序
du -sh /Applications/*.app | sort -rh | head -15

# 逐层 drill-down（在最大的目录上继续）
du -sh ~/Desktop/*/ | sort -rh | head -10
```

### 3. 识别可清理 vs 不可清理

| 类型 | 安全等级 | 典型路径 | 说明 |
|------|---------|---------|------|
| Cache 缓存 | ✅ 安全 | `~/Library/Caches/*/` | 可全删，应用会自动重建 |
| 模型快照 | ✅ 安全 | `~/.deepseek/snapshots/` | 旧版本检查点，当前不用的可删 |
| 安装包/zip | ✅ 安全 | 桌面/下载的 zip/rar/dmg | 解压后残留 |
| 更新器缓存 | ✅ 安全 | `*‑updater/` | Kimi/OpenClaw 等已停用工具的 |
| 对话会话 | ✅ 安全 | `~/.hermes/sessions/` | Hermes 历史会话，可清旧记录 |
| 浏览器缓存 | ✅ 安全 | Chrome Profile Cache | 可清，不影响书签/密码 |
| 浏览器数据 | ⚠️ 谨慎 | `Application Support/Google/Chrome/` | 含书签、扩展、历史，只清缓存 |
| 飞书缓存 | ⚠️ 谨慎 | `LarkShell/Caches/` | 可清，但数据目录不动 |
| 桌面项目文件 | ⚠️ 用户判断 | `~/Desktop/客户/` 等 | 用户工作文件，只提醒不擅删 |
| 游戏数据 | 用户判断 | `Sports Interactive/` | 足球经理存储，用户决定 |
| 开发 venv | ⚠️ 谨慎 | `hermes-agent/venv/` | 可重装瘦身但别直接删 |

### 4. 检查 APFS purgeable 空间

```bash
# 查看 purgeable 空间
diskutil apfs list | grep Purgeable

# Time Machine 本地快照（占 purgeable）
tmutil listlocalsnapshots /System/Volumes/Data
```

> ⚠️ 如果 purgeable 空间很大，重启后可回收。这类清理不通过删文件实现。

---

## 资源评估（本地部署可行性）

向 Gu 推荐本地运行的工具前，先对照底线评估：

| 模型/工具 | 推荐条件 | Gu 的机器能否跑 |
|-----------|---------|----------------|
| MOSS-TTS-Nano (0.1B) | 8GB RAM + CPU | ❌ 勉强，内存会撑爆 |
| Ollama 7B 模型 | 16GB+ RAM | ❌ 不够 |
| Ollama 1-3B 模型 | 8GB RAM | ⚠️ 可以但需关其他应用 |
| ComfyUI + SDXL | 16GB+ RAM | ❌ 不够 |
| ComfyUI + SD1.5/Turbo | 8GB RAM | ⚠️ 内存紧张 |
| Hermes gateway | 标准 | ✅ 正常跑 |
| Playwright (headless) | 标准 | ✅ 正常跑 |

---

## Common Pitfalls

1. **只看 `df -h` 的 Used 列就下结论。** APFS 的 Used 是 non-purgeable 空间，实际数据卷用量要大得多。始终用 `diskutil apfs list` 确认真实用量。

2. **忽略 purgeable 空间。** 当可用空间突然变少，可能只是 Time Machine 本地快照占位，重启就能回收。在判定「确实满了」之前先查。

3. **用户说「不用」就直接接受。** Gu 的「不用」常带隐含原因（跑不动/资源不够）。先查机器配置再给出替代方案，而不是只说「记住了」。

4. **一上来就 `du -sh ~`。** 这是最慢的做法。先用 `df` 和 `diskutil` 确定问题规模，再从大概率目录（Desktop/Caches/Applications）开始分层钻取。

5. **直接给清理命令而不先确认。** 用户的项目文件、App 数据、浏览器数据，只报告不擅动。清理只做 cache/snapshots/updaters 这些安全区。

### 6. 把 WeChat 容器内 Desktop/ 当成独立数据。 `~/Library/Containers/com.tencent.xinWeChat/Data/Desktop/` 是 macOS 沙箱安全机制把**真实桌面**映射进容器的镜像，不是重复数据。WeChat 容器 Desktop/ 下 24G 就是 `~/Desktop/` 自己的 24G，加一起不会多占。实际微信数据在：`Application Support/com.tencent.xinWeChat/2.0b4.0.9/{Hash}/Message/`（聊天记录 + 缓存）、`Downloads/`（下载文件）、`Movies/`（视频）。

### 7. 建议安装本地模型前不先查配置。 用户说「不用」时往往伴随隐含原因（硬件跑不动/资源紧张）。不等他说，先跑 `system_profiler SPHardwareDataType` 确认硬件底线，再决定推不推荐。典型场景：MOSS-TTS-Nano 推完用户才说「MacBook Air M1 8GB 带不动」。

### 8. ClashX 代理在 shell 不自动生效。 Gu 运行 ClashX Pro (port 7890) 但 shell 环境变量不设 `https_proxy`。需要从 GitHub 下载资源时显式设代理：`export https_proxy=http://127.0.0.1:7890`。npm 会自动走 ClashX，无需额外配置。详见 `references/clouddrive2-setup-2026-05-13.md` 的「GitHub 下载工作流」段落。

### 9. 微信容器内 Desktop/ 不是微信专用。 同 Pitfall 6 的补充：`du -sh` 整个 WeChat Container 时看到 24G Desktop/ 容易误判。解释清楚它是 macOS 沙箱映射。（见 WeChat 沙箱容器清理章节）

---

## WeChat 沙箱容器清理

WeChat 数据在 macOS 应用沙箱容器内：`~/Library/Containers/com.tencent.xinWeChat/Data/`

### 数据结构

| 位置 (相对于 Container) | 典型大小 | 说明 |
|------|---------|------|
| `Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/{hash}/Message/` | 2-3G | 聊天记录数据库(msg_*.db) + 临时缓存(MessageTemp/) + 品牌素材(brand/) |
| `Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/{hash}/Stickers/` | ~165M | 表情包缓存，可安全清 |
| `Downloads/` | ~1G | 微信下载的文件（游戏/文档/照片等） |
| `Movies/` | ~500M | 微信收发视频（JianyingPro/ 通常是最大部分） |
| `Pictures/` | ~86M | 图片缓存（⚠️ 沙箱保护，terminal 直接 rm 会 Permission denied） |
| `Desktop/` | ⚠️ | **不是微信数据**。macOS 沙箱把真实 `~/Desktop/` 映射进容器，不重复占用 |

### 分层回收策略

当 Gu 问「能不能清」时，先列出三层，让他选：

```
1. 纯缓存 — Stickers/MessageTemp/brand/游戏下载/剪映视频 → ~1.3G
2. 缓存+聊天记录 — 含 msg_*.db 数据库 → 永久丢失聊天历史
3. 不碰微信 — 建议用微信内置存储管理
```

**不要直接删聊天记录，除非用户明确确认「不要了」**。聊天记录数据库文件 (`msg_*.db`) 删除后不可恢复。正确做法：先给三级选项，等用户确认。

### 安全清理步骤

```bash
# 容器根路径
WC=~/Library/Containers/com.tencent.xinWeChat/Data

# [Level 1] 纯缓存清理
# 1. MessageTemp — 聊天媒体临时缓存（最大，1-2G）
rm -rf "$WC/Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/"*/Message/MessageTemp/
# 2. Stickers — 表情包缓存（可重建）
rm -rf "$WC/Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/"*/Stickers/
# 3. 游戏下载
rm -rf "$WC/Downloads/游戏/"
# 4. 剪映视频
rm -rf "$WC/Movies/JianyingPro/

# [Level 2] 含聊天记录 — 只有用户明确确认后才执行
# rm -rf "$WC/Library/Application Support/com.tencent.xinWeChat/2.0b4.0.9/"*/Message/*.db
```

### Pitfalls

- **不要删 `msg_*.db` 文件** — 这是聊天记录数据库，删了永久丢失
- **不要删 `fts/` 索引** — 搜索索引，删了微信内搜索不可用直到重建
- **`Data/Desktop/` 不是微信数据** — 是 macOS 沙箱映射真实桌面的接口，不重复占用。du 统计看见 24G 是正常的，不用管
- **`Pictures/` 无法用终端 rm** — 沙箱保护，只能微信内部清理或开 Sandbox 权限

---

## Verification Checklist

- [ ] `system_profiler SPHardwareDataType` — 芯片、RAM、型号
- [ ] `diskutil apfs list` — Data 卷真实用量
- [ ] `df -h /` — 当前可用空间 + purgeable 空间
- [ ] 分层 du 扫描大目录并排序
- [ ] 标记安全可清理项 vs 需用户判断项
- [ ] 给出量化可回收空间
- [ ] CloudDrive 2 配置细节见 `references/clouddrive2-setup-2026-05-13.md`
