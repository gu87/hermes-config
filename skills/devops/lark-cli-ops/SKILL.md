---
name: lark-cli-ops
version: 1.0.0
description: "lark-cli 运维操作：更新排障、代理配置、替代安装路径。当 `lark-cli update` 因网络失败、需要从 npmmirror 手动替换二进制、或需要排查代理问题时使用。"
---

# lark-cli 运维操作

## 更新失败排障

`lark-cli update` 在国内网络环境常因以下原因失败：

| 失败模式 | 典型错误 | 根因 |
|---------|---------|------|
| 网络超时 | `context deadline exceeded` | Go 二进制硬编码 `registry.npmjs.org`（Cloudflare CDN），国内受限 |
| SSL 超时 | `SSL connection timeout` | 同上 |
| 代理无效 | 设了代理仍超时 | Go 二进制内建 HTTP 客户端不读 `HTTP_PROXY` 环境变量 |

**核心原则**：不要反复重试 `lark-cli update`。Go 二进制的 HTTP 请求不通过环境变量代理，设代理对 update 命令无效。

## 代理排查流程

当怀疑网络问题时，按顺序排查：

```bash
# 1. 查 macOS 系统代理设置
networksetup -listallnetworkservices
networksetup -getwebproxy "Wi-Fi"

# 2. 查代理进程是否在跑（常见端口 7890/7891/1080）
lsof -i :7890 | head -5

# 3. 查环境变量中是否已设代理
env | grep -i proxy

# 4. 查 ~/.zshrc 中是否有代理配置
grep -i proxy ~/.zshrc
```

Gu 机器配置：Clash Verge（verge-mih）跑在 127.0.0.1:7890，~/.zshrc 已配 HTTP_PROXY 但 terminal 新会话可能不自动加载。

## 手动替换二进制步骤

当 `lark-cli update` 失败时，从 npmmirror CDN 手动下载替换：

### 1. 查版本和架构

```bash
VERSION=$(curl -sL "https://registry.npmmirror.com/@larksuite/cli/latest" | \
  python3 -c "import sys,json; print(json.load(sys.stdin)['version'])")
echo "最新版本: $VERSION"

# macOS M1/M2/M3 → darwin-arm64
# macOS Intel → darwin-amd64
ARCH="darwin-arm64"
```

### 2. 下载二进制

```bash
# 直接下载（国内可用）
curl -L --connect-timeout 10 --max-time 300 \
  "https://cdn.npmmirror.com/binaries/lark-cli/v${VERSION}/lark-cli-${VERSION}-${ARCH}.tar.gz" \
  -o /tmp/lark-cli.tar.gz

# 或走本地代理（更慢但更稳定）
curl -L --connect-timeout 10 --max-time 300 \
  --proxy "http://127.0.0.1:7890" \
  "https://cdn.npmmirror.com/binaries/lark-cli/v${VERSION}/lark-cli-${VERSION}-${ARCH}.tar.gz" \
  -o /tmp/lark-cli.tar.gz
```

### 3. 提取和替换

```bash
cd /tmp && tar xzf lark-cli.tar.gz
file lark-cli  # 确认: Mach-O 64-bit executable arm64

# 找到 Go 二进制位置
# which lark-cli → Node.js wrapper
# 真实二进制在: <npm_prefix>/lib/node_modules/@larksuite/cli/bin/lark-cli
BIN_DIR="$(dirname "$(dirname "$(which lark-cli)")")/lib/node_modules/@larksuite/cli/bin"
cp lark-cli "$BIN_DIR/lark-cli" && chmod 755 "$BIN_DIR/lark-cli"
```

### 4. 同步版本号（可选）

```bash
python3 -c "
import json
pkg = '$BIN_DIR/../package.json'
d = json.load(open(pkg))
d['version'] = '$VERSION'
json.dump(d, open(pkg, 'w'), indent=2)
"
```

### 5. 验证

```bash
lark-cli --version
# 预期输出: lark-cli version ${VERSION}
```

### 6. 清理

```bash
rm -f /tmp/lark-cli /tmp/lark-cli.tar.gz
```

## 注意事项

- 该操作只替换 Go 二进制，不改变 npm 包结构
- `lark-cli --version` 从二进制内读取版本号，不受 package.json 影响
- 更新后**必须退出并重新打开 AI Agent** 以加载最新 Skills
- 下次 `lark-cli update` 仍会尝试连接 npmjs.org（可能继续超时），这是已知限制
- 如 `skill_manage` 操作 `lark-shared` 报 not found（但 `skill_view` 能找到），可能是 skill 注册表索引问题，需 curator 修复