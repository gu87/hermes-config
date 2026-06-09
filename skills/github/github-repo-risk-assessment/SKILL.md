---
name: github-repo-risk-assessment
description: 在决定部署/集成一个 GitHub 项目之前，系统性地从 README、issues、commits、环境、端口冲突五个维度评估风险。形成结构化报告，给出部署难度、已知风险、兼容性结论。
category: github
agents:
- deepseek-tui
- claude
- codex
- hermes-internal
---

# GitHub 仓库风险评估

## 适用场景
- 用户问"能不能用 / 好不好用 / 部署有什么风险"
- 决定是否要把一个开源项目引入当前系统
- 集成前评估兼容性和维护状态

## 核心原则
**先研究再判断** — 不凭感觉推荐，给出可量化的风险指标。

## 工作流（5步）

### Step 1：README 探测
通过 GitHub API 获取 README，提取：
- 项目定位和功能列表
- 依赖要求（Node/Python/Docker 版本）
- 认证方式、安全机制
- 明确标注的风险（"Alpha Software" / "breaking changes"）

```bash
# 获取 README
curl -s "https://api.github.com/repos/{owner}/{repo}" | jq -r '.description, .stargazers_count, .pushed_at, .language'

# 获取 README 内容
curl -s "https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
```

### Step 2：Issues 健康度检查
抓取 open issues，分析：
- 数量多少（>100 活跃 = 高）
- 是否有 security 标签
- 高频 bug 类型（性能？兼容性？UI？）
- 最近是否有未关闭的功能请求

```bash
# 最近 10 条 open issues
curl -s "https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=10" \
  | jq '.[] | {number, title, labels: [.labels[].name]}'
```

### Step 3：Commit 活跃度分析
看最近 5 条 commit：
- 是否每天都有（高活跃）
- 最近一次 commit 时间
- 是否在修已知的 bug（说明维护认真）

```bash
curl -s "https://api.github.com/repos/{owner}/{repo}/commits?per_page=5" \
  | jq '.[] | {date: .commit.author.date, message: .commit.message | split("\n")[0]}'
```

### Step 4：环境与端口冲突检查
在目标机器上运行，检查是否与现有服务冲突：

```bash
# 检查常用端口是否被占用
lsof -i -P -n | grep LISTEN | grep -E "(3000|4000|5000|8080|8090|8888|8000)"

# 如果是已知的 gateway/agent 进程，检查其监听端口
lsof -p <PID> -i -P -n | grep LISTEN

# 查看 gateway_state.json 了解其端口
cat ~/.hermes/gateway_state.json
```

### Step 5：兼容性评估
- 官方支持的集成列表 vs 你的现有系统
- 是否需要 adapter / bridge
- 认证机制是否兼容

## 输出格式

```
## {项目名} 风险评估

**基本情况**
- Stars / 语言 / License
- 最后更新

**部署难度：X/10**
- 安装方式
- 依赖要求
- 实际难度说明

**已知风险**

| 风险 | 等级 | 说明 |
|------|------|------|
| ... | ... | ... |

**可能的 Bug（来自 issues）**
- #xxx: 描述
- #xxx: 描述

**结论**
是否建议使用 / 需要什么前提条件
```

## 支持文件
- `references/port-conflict-check.md` — 本地服务端口冲突检查常用命令，含常见端口参考表
- `references/mission-control-deployment.md` — builderz-labs/mission-control 部署记录，含 gateway 端口不匹配处理

## 注意事项
- 不替用户做决定，只给结构化事实
- 报告要诚实，不只卖产品，风险要明说
- 如果是 Alpha/Beta 软件，明确告知升级风险

## 常见坑

### GitHub API (`api.github.com`) curl 在国内超时
**症状：** `curl -s "https://api.github.com/repos/{owner}/{repo}"` 等命令 15-30s 后报 `Connection timed out` 或被 BLOCKED。terminal 和 browser 工具均可能超时。
**原因：** 国内网络环境直连 GitHub API 不稳定，TCP 握手经常失败。
**正确做法——多通道并行回退：**

| 需要的信息 | 优选通道 | 命令/工具 |
|-----------|---------|----------|
| README / 源码 / 配置文件 | `raw.githubusercontent.com` | `curl -sL "https://raw.githubusercontent.com/{o}/{r}/main/README.md"` |
| Stars / Forks / 语言占比 / Topics | `mcp_anysearch_extract` | 直接抓 `https://github.com/{owner}/{repo}` 页面 |
| 仓库发现 / 基本信息确认 | `mcp_anysearch_search` | query: `"{owner} {repo} github repository"` |
| Commits 历史 | `mcp_anysearch_extract` | GitHub 页面本身含最近 commit 信息 |
| 官方文档 | `mcp_anysearch_extract` | 抓项目文档站（如 `goose-docs.ai`） |
| Issues | 次选方案：看 GitHub 页面本身 | 页面侧栏含 Open Issues 数量 |

**验证：** 如果 `curl api.github.com` 连续 2 次超时，不要重试，直接切换到上述多通道策略。这些通道在本会话已实战验证可恢复约 90%+ 的仓库调研数据。
**注意：** 这不是 "api.github.com 永远不可用"——这只是网络条件差时的回退策略。网络恢复后优先用 API（更结构化）。

### Scrapling 抓 GitHub 页面返回导航栏垃圾
**症状：** 用 `scrapling_fetch` 或 `mcp_scrapling_fetch_s_fetch_page` 抓 GitHub 仓库页面（如 `github.com/owner/repo`），返回内容只有 13-29% 是 README 正文，其余全是 GitHub 导航栏、页脚、Sign in 提示等页面框架。
**原因：** GitHub 页面是动态渲染的 SPA，请求返回的是完整 HTML 页面，导航/sidebar/footer 占了大量字符。
**正确做法：** 直接用 raw.githubusercontent.com 取 README 源文件：
```bash
curl -sL 'https://raw.githubusercontent.com/{owner}/{repo}/main/README.md'
```
**验证：** 对比两种方式返回的内容量——raw 方式 README 正文占比接近 100%，scrapling 方式 README 正文占比 <30%。

### npm/pnpm install 在国内超时
**症状：** `pnpm install` 或 `npm install` 卡在下载阶段，30s~300s 后报 timeout。
**原因：** 官方 npm registry (registry.npmjs.org) 在国内访问极慢。
**解法：**
```bash
cd <项目目录>
pnpm config set registry https://registry.npmmirror.com
pnpm install
```
npmmirror（阿里镜像）是国内最快的 npm 镜像，回源官方且实时同步。pnpm/npm/yarn 均适用。
**验证：** 换源后 `pnpm install` 应在 60s 内完成（正常项目）。

### 国内 Node.js 生态其他慢的场景
- `pnpm approve-builds` 也会卡 — 同上，换 registry
- 如果 `pnpm install` 换源后仍然慢，检查是否触发了 `postinstall` 脚本（如 native addon 编译），这种情况只能等，或者在 install 后手动 `pnpm rebuild`

### 首次启动需要 /setup 的项目
有些项目（如 Mission Control）不会预置管理员账号，首次启动时：
1. 访问 `http://localhost:<port>/setup` 创建第一个账号
2. 如果启动日志里没有输出密码，检查 `.env` 里是否已定义 `AUTH_USER`/`AUTH_PASS`
3. 没有的话，手动访问 setup 页面
