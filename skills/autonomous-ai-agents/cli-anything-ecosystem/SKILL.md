---
name: cli-anything-ecosystem
description: CLI-Anything 生态系统 —— 本地 32+ App Harness 的位置、能力矩阵、Mac/Win 兼容性、与 Hermes Agent 的集成路径。覆盖办公文档自动化（Writer/Calc/Impress）、评估新 harness 的决策框架。
---

# CLI-Anything Ecosystem

## 是什么

[CLI-Anything](https://github.com/HKUDS/CLI-Anything) 是一个让 AI Agent 通过 CLI 命令操控桌面应用的开源框架。基于 7 阶段 Harness 方法论，把 GUI 软件的功能封装为 `--json` 输出的命令行接口。

## 本地位置

```
/Users/gu/Desktop/AI AGENT/CLI-Anything-main/CLI-Anything-main/
```

含 **32+ 个 App Harness**，包括：LibreOffice、GIMP、Blender、OBS Studio、Audacity、Inkscape、Kdenlive、DrawIO、Mermaid、MuseScore、FreeCAD、CloudCompare 等。

**harness 可通过 `pip install -e .` 安装，LibreOffice 已验证可用（2026-05-28）。** 其他 harness 状态各异，使用前需逐一检查。

## 关键 Harness 速查

| Harness | 路径 | 状态 | Mac 可用 | 备注 |
|---|---|---|---|---|
| LibreOffice | `libreoffice/agent-harness/` | ✅ 已安装并验证（2026-05-28） | ✅ | 需 LibreOffice.app 做格式转换，brew cask 可能失败用 direct download |
| GIMP | `gimp/` | — | ✅ | — |
| Blender | `blender/` | — | ✅ | — |
| OBS Studio | `obs-studio/agent-harness/` | — | ✅ | — |
| DrawIO | `drawio/` | — | ✅ | — |
| Mermaid | `mermaid/` | — | ✅ | — |
| 其余 26+ | 各自目录 | 未逐一审查 | 视情况 | — |

## Mac 上办公文档自动化的路径决策

### 场景：需要 AI Agent 创建/编辑 Word/Excel/PPT 文档

```
决策树：

需要真实渲染（和手动操作效果一致）？
├── YES → LibreOffice headless（brew install --cask libreoffice）
│         用途：把 .odt/.ods/.odp 转 DOCX/XLSX/PPTX/PDF
│         注意：CLI-Anything harness 用纯 Python 生成 ODF，转换时才需要 LO 本体
│
├── NO，只要 ODF 格式 → CLI-Anything LibreOffice harness 纯 Python 模式
│         无需安装任何办公套件，直接 `pip install -e .`
│         输出 .odt / .ods / .odp（ZIP 压缩的 XML）
│
└── 必须用 WPS/Office 原生格式 → Windows COM 路径（cli-anything-wps）
          当前 Mac 不可用，需要 Windows 执行节点
```

### 为什么不走 AppleScript + iWork？

AppleScript 对 Pages/Numbers/Keynote 的脚本字典稀疏，大规模自动化不稳定，仅适合简单原型演示，不适合生产级批量生成。

### Windows 对照

cli-anything-wps（yb2460/cli-anything-wps）通过 COM 接口操控 WPS Office，Windows 独占。功能对标 LibreOffice harness，但平台受限。在 Hermes 架构中归属 TARS（桌面操作员），但因 OS 限制当前无法使用。

## Agent 归属

| Harness | 推荐 Agent | 理由 |
|---|---|---|
| LibreOffice / WPS | **TARS**（桌面操作员） | 本质是桌面应用自动化 |
| GIMP / Blender / Inkscape | TARS | 同上 |
| OBS Studio | TARS | 桌面录制/直播控制 |
| DrawIO / Mermaid | Claude 主程或直接调用 | 图表生成 |
| MuseScore | 特殊场景，Claude 主程 | 乐谱生成 |

## LibreOffice Harness 快速启动

```bash
# 1. 安装 LibreOffice（含 headless 模式用于格式转换）
# 注意：brew cask 可能因版本漂移失败，见 libreoffice-cli skill 的 fallback 方案
HOMEBREW_NO_AUTO_UPDATE=1 brew install --cask libreoffice

# 2. 安装 harness（必须用 Python 3.11+，系统 python3 是 3.9 会失败）
cd "/Users/gu/Desktop/AI AGENT/CLI-Anything-main/CLI-Anything-main/libreoffice/agent-harness"
/Users/gu/.hermes/hermes-agent/venv/bin/python -m pip install -e .

# 3. 验证（注意：不是 cli.libreoffice_cli，那是错的——有命名空间冲突）
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice --help
```

### 核心能力（参见 `references/libreoffice-harness-architecture.md`）

- **Writer**：段落/标题/列表/表格/图片/分页、字体/字号/颜色/粗体/斜体/对齐、查找替换、页眉页脚
- **Calc**：工作表增删改名、单元格读写（单个+批量）、公式/合并、排序/筛选/条件格式
- **Impress**：幻灯片增删排序、内容编辑、形状绘制、文本框
- **通用**：`--json` 输出、REPL 模式、会话持久化、撤销重做（50 步）
- **导出**：ODT/ODS/ODP → DOCX/XLSX/PPTX/PDF（需 LibreOffice headless）

### 格式转换限制

Harness 纯 Python 只生成 ODF 原始格式。导出 DOCX/XLSX/PPTX/PDF 依赖 LibreOffice headless 做 `--convert-to`。如果只装 harness 不装 LO，只能产出 `.odt/.ods/.odp`。

## 评估新 Harness 的决策框架

收到一个新的 CLI-Anything 相关项目（如 cli-anything-wps）时：

1. 读 README → 确认操控方式（COM/UNO/AppleScript/headless）
2. 检查平台限制 → Windows-only / Mac / 跨平台
3. 检查依赖链 → 需要安装什么宿主软件？什么 Python 包？
4. 匹配 Agent → 归属桌面操作（TARS）还是代码执行（Claude）？
5. 给出可行性结论 → **可用/需适配/不可用** + 替代方案

## 参考文档

- `references/cli-anything-wps-analysis.md` — cli-anything-wps 的完整评估（为什么归 TARS、为什么 Mac 不可用）
- `references/libreoffice-harness-architecture.md` — LibreOffice harness 的架构、能力边界、格式转换链
- `references/mac-libreoffice-dmg-install.md` — brew cask 失败时的直接 DMG 下载安装流程（含版本号自动探测）
