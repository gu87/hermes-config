---
name: gitlab-devops-operations
title: GitLab DevOps 操作
description: 自托管 GitLab (gitlab.dongqiudi.com) 的日常 DevOps 操作 — 文件下载、SSH Key 生成、代码克隆、静态网站 CI/CD 发布
tags:
  - gitlab
  - ssh-keygen
  - git-clone
  - raw-url
  - devops
triggers:
  - "从 GitLab 下载文件"
  - "生成 GitLab SSH Key"
  - "克隆 GitLab 仓库"
  - "gitlab.dongqiudi.com"
  - "aidocs 仓库下载"
  - "帮我发布"
  - "部署上线"
  - "推送到 GitLab"
  - "发布新版本"
  - "静态网站发布"
  - "静态网页部署"
---

# GitLab DevOps Operations

适用于公司自托管 GitLab (`gitlab.dongqiudi.com`) 的日常操作。

---

## 1. 从 GitLab 下载文件（Raw URL 转换）

**场景**：用户给出一个 GitLab blob 页面 URL，要求下载到本地。

**问题**：`/-/blob/main/path/file.md` 是 HTML 页面，curl 下载会拿到页面 HTML 而非文件内容。

**修复**：将 `/-/blob/` 替换为 `/-/raw/`，用 raw 端点直接下载：

```
# ❌ blob URL（HTML 页面，curl 超时或拿到 HTML）
https://gitlab.dongqiudi.com/share/aidocs/-/blob/main/devops/deploy/.ssh-keygen.md

# ✅ raw URL（直接下载文件内容）
https://gitlab.dongqiudi.com/share/aidocs/-/raw/main/devops/deploy/.ssh-keygen.md
```

**命令模板**：
```bash
curl -sL -o /path/to/local/file.md "https://gitlab.dongqiudi.com/share/aidocs/-/raw/main/<path-to-file>"
```

**注意**：即使 curl 能访问 blob URL（返回 200），内容也是 HTML 而非文件原文。**必须使用 raw URL**。

---

## 2. SSH Key 生成（用于 GitLab）

公司规范文档：`aidocs/devops/deploy/.ssh-keygen.md`

### 要求
- 算法：RSA
- 长度：4096
- Passphrase：不设置（空）
- 邮箱格式：`<系统用户名>@company.local`

### 执行流程

1. **检查是否已存在**：
   ```bash
   ls ~/.ssh/id_rsa ~/.ssh/id_rsa.pub
   ```
2. **已存在**：直接读取并打印 `~/.ssh/id_rsa.pub` 内容
3. **不存在**：
   ```bash
   mkdir -p ~/.ssh
   ssh-keygen -t rsa -b 4096 -C "$(whoami)@company.local" -f ~/.ssh/id_rsa -N "" -q
   ```
4. 打印完整公钥内容
5. 提示粘贴到：GitLab → Preferences → SSH Keys

---

## 3. 代码克隆（GitLab）

公司规范文档：`aidocs/devops/deploy/.code-clone.md`

### 流程

1. **前置校验**：
   - 确认用户提供的 Git SSH 地址格式：`git@gitlab.dongqiudi.com:group/repo.git`
   - **项目名称必须以 `dongqiudi-` 开头**，否则拒绝克隆并提示
   - 检查 `~/Desktop/git_data/` 目录是否存在，不存在则创建

2. **克隆操作**：
   ```bash
   mkdir -p ~/Desktop/git_data
   cd ~/Desktop/git_data
   git clone <SSH_URL>
   ```

3. **路径提取**：进入克隆目录，获取绝对路径

4. **回显信息**：
   - 执行状态
   - 项目本地绝对路径
   - 部署引导提示

### 注意
- 必须是 SSH 协议克隆（需提前配置 SSH Key）
- `dongqiudi-` 前缀校验是硬性要求

### 常见坑点

#### SSH 主机密钥验证失败
首次连接 GitLab 时，`~/.ssh/known_hosts` 中没有该服务器的主机密钥，导致：
```
Host key verification failed.
fatal: Could not read from remote repository.
```

**修复**：先添加主机密钥到 known_hosts：
```bash
ssh-keyscan -H gitlab.dongqiudi.com >> ~/.ssh/known_hosts
```
之后重新克隆即可。

#### Git 用户身份未配置
首次在电脑上使用 git 时，`user.email` 和 `user.name` 未设置，导致：
```
Author identity unknown
*** Please tell me who you are.
```

**修复**：在仓库目录下配置身份（或使用 `--global` 全局配置）：
```bash
git config user.email "gu@company.local"
git config user.name "Gu"
```

---

## 4. 静态网站 CI/CD 发布流程

公司规范文档：`aidocs/devops/deploy/.static-web-deploy.md`

### 场景
用户说"帮我发布"时，对 `~/Desktop/git_data/dongqiudi-*` 项目执行完整发布流程。

### 项目结构要求
- `index.html` — 页面源文件
- `.gitlab-ci.yml` — CI 配置
- `.gitignore` — 必须包含 `.claude/`
- `README.md` — 项目说明

### 执行流程（按顺序，无需用户逐条确认）

1. **检查 `.gitlab-ci.yml`**，不存在则创建，内容固定为：
   ```yaml
   include:
     - project: 'devops/gitlab-ci-pipeline'
       ref: main
       file: 'templates/static-web-pipeline.yml'
   ```

2. **检查 `.gitignore`**，不存在则创建（写入 `.claude/`）；存在但缺少 `.claude/` 则追加该行。macOS 环境建议同时添加 `.DS_Store`。

3. **`git add -A`**

4. **语义化提交**：
   - 执行 `git diff --cached --name-only` 分析暂存区文件
   - 生成符合 Conventional Commits 格式的信息（如 `feat: update index.html content`）
   - **禁止使用固定字符串 "release"**

5. **版本号管理**：
   - 读取最新 tag：`git tag --sort=-v:refname | head -1`
   - 递增 patch 位（如 `v1.0.0` → `v1.0.1`）
   - 进位规则：Patch > 10 → Minor+1，Minor > 10 → Major+1
   - 无现有 tag 则从 `v1.0.0` 开始

   **版本示例**：
   | 当前 | 变更 | 新版本 |
   |------|------|--------|
   | v1.0.0 | 首次发布 | v1.0.1 |
   | v1.0.10 | 第 11 次 patch | v1.1.0 |
   | v1.10.0 | 第 11 次 minor | v2.0.0 |

6. **打 tag**：`git tag -a <new-version> -m "<tag描述>"`

7. **推送**：`git push origin main --tags`

### 触发方式
推送 `v*` 格式的 tag（如 `v1.0.0`）到 `main` 分支后，GitLab CI 自动拉取共享 pipeline 模板完成部署。

### 坑点
- 首次发布前可能遇到 git 身份未配置问题——先配置 user.email / user.name（见第 3 节 "Git 用户身份未配置"）
- `.gitignore` 遗漏 `.claude/` 会导致本地 Agent 工作目录被跟踪

### CI/CD 共享模板访问被拒

**现象**：推送到 GitLab 后流水线报错：
```
Project `devops/gitlab-ci-pipeline` not found or access denied!
```

**排查方向**（按优先级）：
1. **项目路径问题** — `.gitlab-ci.yml` 中 `project: 'devops/gitlab-ci-pipeline'` 可能路径不正确，确认完整路径（可能在 `share/` 或用户命名空间下，如 `share/aidocs` 是公开项目）
2. **权限问题** — `devops/gitlab-ci-pipeline` 是**私有项目**，CI Job Token 没被授权访问，需联系管理员授权 CI Job Token 访问该私有项目
3. **项目不存在** — 通过浏览器登录 GitLab 确认该模板项目是否真实存在
4. **确认**：Share/aidocs 是公开项目，但 devops/gitlab-ci-pipeline 非公开，权限配置不在配置文件本身，而在 GitLab 后端

> 扩展参考：`references/aidocs-source-files.md` 汇总了 aidocs 源代码文件

---

## 参考文件

- `references/gitlab-raw-url.md` — GitLab raw URL 转换详细说明
- `references/aidocs-source-files.md` — 懂球帝 aidocs 部署源文档汇总（SSH Key、代码克隆、静态部署规范）
