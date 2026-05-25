---
name: macos-resource-diagnostics
description: macOS 资源诊断 + 系统扩展排障。检查系统规格、磁盘分析、内存评估、kext/dext 状态。
tags:
- macos
- diagnostics
- disk
- cleanup
- macfuse
- system-extension
agents:
- hermes-internal
- hermes
---

## When to Use

- Gu 拒绝你的软件/工具推荐时 — 先查他机器配置（`system_profiler SPHardwareDataType`）
- Gu 问「硬盘怎么又满了」或「能不能清理」 — 执行完整磁盘分析
- **推荐本地运行的 AI 模型/服务前 — 先查配置再建议，不等他说「不用」才知道跑不动**（典型例子：MOSS-TTS-Nano → 查 MacBook Air M1 8G RAM 后发现确实带不动）
- Gu 说机器卡/慢 — 检查 CPU/Memory 压力和磁盘剩余
- macOS 系统升级后 — 检查 kext/dext 系统扩展是否正常加载

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

### 3. 家目录 Dot-Directory 清理（快速回收）

`~/` 下的隐藏目录是常见的硬盘占用大户，但 `du -sh ~` 太慢。从最可能大的开始查：

```bash
# 常见大 dot-dir 快速扫描
for d in .npm .cache .agent-browser .cargo .conda .local .hermes; do
  size=$(du -sh ~/"$d" 2>/dev/null | cut -f1)
  [ -n "$size" ] && echo "$size\t$d"
done

# 检查是否有旧 Hermes 备份（占几十M，不引用当前版本就没用）
ls -lh ~/.Hermes_backup_*.tar.gz 2>/dev/null
```

| 目录 | 典型大小 | 可清理内容 | 清理命令 |
|------|---------|-----------|---------|
| `~/.npm/` | 500M-1.5G | npm 包缓存（可重建） | `npm cache clean --force` |
| `~/.cache/` | 500M-1G | 系统/应用通用缓存 | `rm -rf ~/.cache/*` |
| `~/.agent-browser/` | 200-500M | Headless 浏览器沙箱数据 | `rm -rf ~/.agent-browser/*` |
| `~/.Hermes_backup_*.tar.gz` | 50-100M | 旧版 Hermes 备份（当前不用则无用） | `rm ~/.Hermes_backup_*.tar.gz` |
| `~/.cargo/registry/` | 100-300M | Rust 包注册表缓存（不用 Rust 编译则可删） | `rm -rf ~/.cargo/registry/*` |
| `~/.conda/pkgs/` | 100-500M | Conda 包缓存 | `conda clean --all` |

> ⚠️ 清理前检查：`.npm/` 清空后首次 `npm install` 会慢一些，但包会重新下载。`.agent-browser/` 清后首次 Playwright 调用稍慢。确定用户确认后再执行写操作。

### 4. 识别可清理 vs 不可清理
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

## macOS 系统扩展 (kext/dext) 检查

macOS 升级后，第三方系统扩展（macFUSE/virtualization 等）可能失效。查 kext 状态：

```bash
# kext 已加载？
kextstat | grep macfuse

# dext 系统扩展已注册？
systemextensionsctl list | grep fuse

# 已安装版本
cat /Library/Filesystems/macfuse.fs/Contents/version.plist

# brew 可用版本
brew info macfuse
```

macFUSE 详细升级排障见 `references/macos-system-extensions.md`。

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

### 10. macOS 升级后忘了检查系统扩展。 系统升级可能让 kext/dext 失效。升级后用 `kextstat` + `systemextensionsctl list` 确认关键扩展状态。

### 11. SIP 保护下 `/System/Applications/` 的 app 删不掉。 Stocks.app（股市）、Chess.app（国际象棋）等预装 app 在 `/System/Applications/` 下，SIP 开启时：
   - `sudo rm -rf` → 需要终端交互输密码，且仍可能被 SIP 拦截
   - `trash /System/Applications/Stocks.app` → 报 Error 512 / paramErr -50
   - `osascript -e 'move to trash'` → 超时无响应
   - **Finder 拖废纸篓 → 也失败**
   - 唯一解法：重启进恢复模式 → `csrutil disable` → 删除 → `csrutil enable`
   - 这些 app 体积很小（几 MB），不值得为此关 SIP。直接告诉用户「动不了，留着不碍事」。

### 12. WPS 云后台（wpscloudsvr）杀掉后会自复活。 `kill` 掉 wpscloudsvr 进程后，主进程 `wpsoffice` 会在几秒内自动重新拉起来（新 PID）。它不是由 LaunchAgent 管理的（检查 `~/Library/LaunchAgents/` 无 WPS 相关 plist），而是主程序内建的自保机制。要彻底关停，需要在 WPS 设置里关掉云同步（WPS → 设置 → 云服务 → 取消「启用云同步」）。如果用户说「我关了怎么又活了」，这就是原因。shell 里只应做临时 kill 释放内存，并建议用户在 WPS 设置里永久关。

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

---

## Memory Pressure 诊断（系统卡顿排查）

用户说「升级系统后变卡」时按此流程诊断。**8GB M1 最常见原因是 RAM 吃满，不是 CPU 或磁盘。**

### 1. 快速诊断命令集

```bash
# 核心四连
memory_pressure                 # 查 pages free / swap I/O 比例
vm_stat                          # 查 active / wired / compressor 细分
ps aux -r | head -8              # 按 CPU 排序，找当前吃资源的进程
uptime && df -h /                # 开机时长 + 磁盘可用
```

### 2. 怎么看结果

| 指标 | 正常 | 危险信号（需要干预） |
|------|------|---------------------|
| **Pages free** | > 5% 总页数 | **< 1%** — 系统已经没空余内存了 |
| **Swapins vs Swapouts** | 接近或 Swapins > Swapouts | **Swapouts > Swapins（4x+）** — 剧烈颠簸，频繁写 SSD |
| **Pages occupied by compressor** | < 100K | **> 150K** — 压缩器满负荷工作 |
| **Pages throttled** | 0 | > 0 — 系统在主动限流 |

**实战判断步骤：**
1. `memory_pressure` → 看 Pages free / 524288（8GB 的总页数）。free < 5K（<1%）说明内存吃满
2. 看 Swap I/O 比例：Swapouts 远大于 Swapins 时，系统在疯狂写 SSD 换出内存，这是「卡」的根本原因
3. `ps aux -r` → 确认哪些进程占用 CPU 和内存，特别是 Lark、WPS、浏览器、Hermes 等后台服务
4. 给出量化建议：列出 TOP 3 内存占用进程，给出可节省的内存估算

### 3. M1 8GB 上常见的内存大户

| 应用/服务 | 典型占用 | 可优化的点 |
|-----------|---------|-----------|
| **Lark（飞书）** | 3-5% + 多个渲染进程 | Command+Q 彻底退出，不只用 Tab 关窗口；关不用的群聊/聊天 |
| **WPS Office** | 主进程 ~0.8% + **wpscloudsvr（云同步）** ~2.7% | 关闭云同步后台（`kill` 后主进程会复活它，需 WPS 设置里关） |
| **WPSFinderMenu** | ~0.2% | Finder 右键菜单插件，可在系统扩展里关 |
| **Hermes 网关** | ~1.5% | 已用 `--replace` 模式，无法再省 |
| **Chrome / Edge** | 每个标签 ~100-300MB | 少开标签页，用 Safari 替代 |
| **WindowServer** | ~0.7% | 窗口渲染服务，无法避免 |

### 4. 推荐行动（按效果排序）

| 操作 | 预计回收内存 | 难度 |
|------|-------------|------|
| **退出 WPS 云同步**（关 wpscloudsvr） | 200-300MB | 简单 |
| **Lark 不用时彻底退出**（Command+Q） | 300-500MB | 习惯 |
| **关掉不用的浏览器标签页** | 取决于数量 | 简单 |
| **减少开机启动项** | 50-200MB | 一次设置 |
| **终极方案：换 16GB+ 机器** | 彻底解决 | 花钱 |

### 5. macOS 版本对 M1 8GB 的适配评估

| 版本 | 代号 | M1 8GB 表现 | 说明 |
|------|------|------------|------|
| **14 Sonoma** | — | ⭐ 甜点版本 | 基线占用低，8GB 运行流畅 |
| **15 Sequoia** | — | 🟡 可用 | 基线稍高，日常使用无明显卡顿 |
| **16+ (26.x)** | Tahoe | 🔴 紧张 | 8GB 用户常见 memory < 1%，swap 颠簸明显 |

**降级的现实判断：** 从 16 (26.x) 降回 14 Sonoma 需要抹盘重装 + 已不再官方签名，操作复杂且数据有风险。**建议优化当前系统而非降级。** 如果长期卡顿影响工作，换 16GB 机器是更务实的方案。

---

## ~/Library/Application Support/ 深度扫描参考

清理磁盘时，App Support 是最大的空间机会（通常 5-20GB）。逐项评估：

| 目录 | 典型大小 | 可清理 | 说明 |
|------|---------|--------|------|
| `LarkShell/` | **8-10G** | ⚠️ 图片/文件/聊天数据缓存 | 清掉可回收大量空间，但再次打开飞书时会重新下载 |
| `LarkShell/Caches/`（~Library/Caches 下） | **1.5-2G** | ✅ 安全 | 飞书临时缓存的色/图片缩略图，清掉不影响功能 |
| `Google/` (Chrome) | **7-10G** | ❌ 用户数据 | 个人资料/书签/扩展，只清 Caches/ 下的缓存 |
| `Google/` (Chrome) → Caches only | **1-1.5G** | ✅ 安全 | 浏览器缓存，安全清 |
| `Quark/` (夸克网盘) | **1-3G** | ✅ 用户确认 | 网盘下载缓存或本地同步文件 |
| `Sports Interactive/` (足球经理) | **2-3G** | ✅ 用户确认 | 游戏存档/战术配置，用户决定 |
| `Trae CN/` | **1-2G** | ⚠️ | IDE 项目数据 |
| `ms-playwright/` (Caches) | **1-2G** | ✅ 安全 | Playwright 浏览器测试引擎二进制文件，不常跑 E2E 测试则可删 |
| `zoom.us/` | **300-500M** | ⚠️ | 会议录制/聊天数据 |
| `obsidian/` | **100-200M** | ❌ | Obsidian 用户数据 |
| `io.github.clash-verge-rev.clash-verge-rev/` | **30-50M** | ❌ | Clash Verge 代理配置 |

**清理建议：** LarkShell 缓存（Caches）+ ms-playwright 通常可安全回收 3-4G。App Support 下的大目录需要用户逐个确认。

---

## Verification Checklist

- [ ] `system_profiler SPHardwareDataType` — 芯片、RAM、型号
- [ ] `diskutil apfs list` — Data 卷真实用量
- [ ] `df -h /` — 当前可用空间 + purgeable 空间
- [ ] 分层 du 扫描大目录并排序
- [ ] 标记安全可清理项 vs 需用户判断项
- [ ] 给出量化可回收空间
- [ ] `kextstat | grep macfuse` + `systemextensionsctl list` — macOS 升级后检查系统扩展
- [ ] M1 8GB 内存/磁盘清理实战（含 App Support 深度扫描）见 `references/m1-8g-macos26-cleanup-2026-05-16.md`
- [ ] CloudDrive 2 配置细节见 `references/clouddrive2-setup-2026-05-13.md`
- [ ] macOS 系统扩展排障见 `references/macos-system-extensions.md`
- [ ] 家目录大 dot-dir 扫描（`.npm/ .cache/ .agent-browser/ 等`）
- [ ] SIP 状态检查（`csrutil status`）— 当用户问能否删系统 app 时<br>- [ ] `csrutil status` — 确认 SIP 状态（回答「为什么删不了系统 app」时必查）
- [ ] **用户说卡/慢时**：`memory_pressure` → `vm_stat` → Swap 颠簸度 → `ps aux -r` → 确定内存瓶颈和优化点
- [ ] **macOS 大版本升级后**：加查 memory_pressure swap I/O 比例 + 核对 macOS 版本适配（14=甜点，15=可用，16+=紧张）