---
name: libreoffice-cli
description: 通过 CLI-Anything LibreOffice harness 操控办公文档 —— 创建/编辑 Writer/Calc/Impress 文档，导出 ODT/ODS/ODP/DOCX/XLSX/PPTX/PDF。TARS 桌面操作员的办公文档自动化子能力。
trigger:
  - 创建文档 / 生成报告 / 做表格 / 做PPT
  - 导出 PDF / 导出 Word / 导出 Excel
  - 文档自动化 / 批量生成
  - writer / calc / impress / odt / ods / odp
prerequisites:
  - python3.11
  - LibreOffice.app (26.2.3, /Applications/LibreOffice.app)
platform: macOS
agents: [agent-tars]
---

# LibreOffice CLI — TARS 办公文档自动化

## 调用入口

```bash
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice [OPTIONS] COMMAND [ARGS]...
```

全局参数：
- `--json` — JSON 输出，AI Agent 可解析
- `--project FILE` — 指定 .lo-cli.json 项目文件

## 命令树

| 命令组 | 子命令 | 说明 |
|--------|--------|------|
| `document new` | `--type writer\|calc\|impress -n NAME -o FILE` | 创建新文档 |
| `document open` | `-p FILE` | 打开已有项目 |
| `document info` | | 查看文档信息 |
| `writer add-heading` | `-t TEXT -l LEVEL` | 添加标题 |
| `writer add-paragraph` | `-t TEXT` | 添加段落 |
| `writer add-table` | `-r ROWS -c COLS` | 添加表格 |
| `writer add-list` | `-i ITEM1 -i ITEM2` | 添加列表 |
| `writer add-page-break` | | 添加分页符 |
| `writer find-replace` | `-f FIND -r REPLACE` | 查找替换 |
| `calc set-cell` | `REF VALUE --type string\|float` | 设置单元格 |
| `calc get-cell` | `REF` | 读取单元格 |
| `calc set-range` | `RANGE -d JSON_DATA` | 批量设置区域 |
| `calc merge-cells` | `RANGE` | 合并单元格 |
| `impress add-slide` | `-t TITLE -c CONTENT` | 添加幻灯片 |
| `impress add-element` | `INDEX --type TYPE --text TEXT` | 添加元素 |
| `style create` | `-n NAME --font FONT --size SIZE` | 创建样式 |
| `export render` | `OUTPUT -p PRESET [--overwrite]` | 导出文件 |
| `session undo` / `redo` / `history` | | 撤销/重做/历史 |

## 导出预设 (presets)

| preset | 格式 | 需要 LO | 说明 |
|--------|------|---------|------|
| `odt` | ODF Writer | ❌ | 原生生成 |
| `ods` | ODF Calc | ❌ | 原生生成 |
| `odp` | ODF Impress | ❌ | 原生生成 |
| `html` | HTML | ❌ | 原生生成 |
| `text` | 纯文本 | ❌ | 原生生成 |
| `pdf` | PDF | ✅ | LO headless 转换 |
| `docx` | MS Word | ✅ | LO headless 转换 |
| `xlsx` | MS Excel | ✅ | LO headless 转换 |
| `pptx` | MS PPT | ✅ | LO headless 转换 |

## 典型工作流

### Writer → DOCX/PDF
```bash
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice document new --type writer -n "报告" -o doc.json
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice --project doc.json writer add-heading -t "标题" -l 1
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice --project doc.json writer add-paragraph -t "正文"
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice --project doc.json export render output.docx -p docx --overwrite
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice --project doc.json export render output.pdf -p pdf --overwrite
```

### Calc → XLSX
```bash
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice document new --type calc -n "数据" -o data.json
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice --project data.json calc set-cell A1 "列名" --type string
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice --project data.json calc set-cell A2 "42" --type float
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice --project data.json export render data.xlsx -p xlsx --overwrite
```

### AI Agent 模式（加 --json）
```bash
/Users/gu/.hermes/hermes-agent/venv/bin/python -m cli_anything.libreoffice --json document new --type writer -n "test"
```

## 安装路径

- Harness: `/Users/gu/Desktop/AI AGENT/CLI-Anything-main/CLI-Anything-main/libreoffice/agent-harness/`
- LibreOffice: `/Applications/LibreOffice.app/`
- soffice: `/Applications/LibreOffice.app/Contents/MacOS/soffice`

## 注意事项

- `--json` 输出可被 AI Agent 直接解析
- ODT/ODS/ODP/HTML/TEXT 纯 Python 生成，不需要 LibreOffice
- PDF/DOCX/XLSX/PPTX 需 LibreOffice headless（自动调用 `soffice --headless --convert-to`）
- 取消/重做最多 50 步历史
- 无参数运行进入 REPL 交互模式

## 安装陷阱

**brew cask 不可靠**：LibreOffice 的 brew cask 公式经常滞后于上游版本，导致 checksum mismatch 或 404。出现这种情况时，使用直接 DMG 下载方案（见 `cli-anything-ecosystem` skill → `references/mac-libreoffice-dmg-install.md`）。

**Python 版本**：系统默认 `python3` 是 3.9.6，harness 要求 ≥3.10。必须用 `python3.11`（Hermes venv 里就有）。

**CLI 入口**：`python3.11 -m cli.libreoffice_cli` 不行（命名空间冲突），正确入口是 `python3.11 -m cli_anything.libreoffice`。
