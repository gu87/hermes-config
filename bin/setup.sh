#!/usr/bin/env bash
set -euo pipefail
# ============================================================================
# hermes-config setup.sh — 一键部署 Hermes 多Agent系统
# ============================================================================
# 用法:
#   1. 安装 Hermes Agent: pip install hermes-agent
#   2. 克隆配置仓库:    git clone https://github.com/gu87/hermes-config.git ~/.hermes
#   3. 运行本脚本:      cd ~/.hermes && bash bin/setup.sh
#   4. 填写 API 密钥:   cp .env.example .env && vim .env
#   5. 启动网关:        bash bin/start-gateway.sh
# ============================================================================

HERMES_CONFIG_HOME="$(cd "$(dirname "$0")/.." && pwd)"
echo "==> Hermes 配置目录: $HERMES_CONFIG_HOME"

# ── 1. 检测 Hermes Agent 安装位置 ──────────────────────────────────────────
HERMES_AGENT_DIR=""
if [ -d "$HERMES_CONFIG_HOME/hermes-agent" ]; then
  HERMES_AGENT_DIR="$HERMES_CONFIG_HOME/hermes-agent"
  echo "==> 检测到本地源码安装: $HERMES_AGENT_DIR"
elif command -v python3 &>/dev/null; then
  AGENT_PATH=$(python3 -c "import hermes_cli; print(hermes_cli.__path__[0])" 2>/dev/null || echo "")
  if [ -n "$AGENT_PATH" ]; then
    HERMES_AGENT_DIR="$(dirname "$(dirname "$AGENT_PATH")")"
    echo "==> 检测到 pip 安装: $HERMES_AGENT_DIR"
  fi
fi

if [ -z "$HERMES_AGENT_DIR" ]; then
  echo "✗ 未找到 Hermes Agent 安装。请先安装: pip install hermes-agent"
  echo "  或克隆源码到 ~/.hermes/hermes-agent/"
  exit 1
fi

# ── 2. 部署 managed_agents 配置 ────────────────────────────────────────────
AGENTS_YAML_SRC="$HERMES_CONFIG_HOME/config/managed-agents.yaml"
AGENTS_YAML_DST="$HERMES_AGENT_DIR/configs/managed_agents/agents.yaml"

if [ -f "$AGENTS_YAML_SRC" ]; then
  mkdir -p "$(dirname "$AGENTS_YAML_DST")"
  cp "$AGENTS_YAML_SRC" "$AGENTS_YAML_DST"
  echo "==> managed_agents 配置已部署: $AGENTS_YAML_DST"
else
  echo "✗ 缺少 config/managed-agents.yaml，部署中止"
  exit 1
fi

# ── 3. 检查核心配置文件 ───────────────────────────────────────────────────
REQUIRED_CONFIGS=(
  "$HERMES_CONFIG_HOME/config.yaml"
  "$HERMES_CONFIG_HOME/config/agent-registry.json"
  "$HERMES_CONFIG_HOME/config/models.yaml"
  "$HERMES_CONFIG_HOME/SOUL.md"
  "$HERMES_CONFIG_HOME/memories/MEMORY.md"
  "$HERMES_CONFIG_HOME/memories/user-profile.md"
)

MISSING=0
for f in "${REQUIRED_CONFIGS[@]}"; do
  if [ ! -f "$f" ]; then
    echo "✗ 缺少: $f"
    MISSING=$((MISSING + 1))
  fi
done

if [ $MISSING -gt 0 ]; then
  echo "✗ 缺少 $MISSING 个核心配置文件，部署中止"
  exit 1
fi
echo "==> 核心配置文件检查通过 ($(( ${#REQUIRED_CONFIGS[@]} )) 个)"

# ── 4. 创建 .env 模板 ──────────────────────────────────────────────────────
if [ ! -f "$HERMES_CONFIG_HOME/.env" ]; then
  cat > "$HERMES_CONFIG_HOME/.env.example" << 'EOF'
# Hermes Agent API 密钥 — 复制为 .env 并填入实际值
# .env 文件不会被 git 追踪

# 必填: 默认模型提供者
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxxxxxx

# 可选: 其他模型提供者
ANTHROPIC_API_KEY=
VOLCANO_ARK_API_KEY=
KIMI_API_KEY=
DQD_FLASHAPI_API_KEY=

# 可选: 飞书应用凭证（用于 gateway 模式）
FEISHU_APP_ID=
FEISHU_APP_SECRET=

# 可选: GitHub token（用于 gh CLI 和 GitHub MCP）
GITHUB_TOKEN=

# 可选: OpenChronicle 本地记忆服务
# OpenChronicle 需单独安装: https://github.com/gu87/OpenChronicle
EOF
  echo "==> .env.example 模板已创建。请复制并填入密钥:"
  echo "    cp ~/.hermes/.env.example ~/.hermes/.env"
  echo "    vim ~/.hermes/.env"
fi

# ── 5. macOS: 安装 launchd 服务 ────────────────────────────────────────────
if [[ "$OSTYPE" == "darwin"* ]]; then
  LAUNCHD_DIR="$HERMES_CONFIG_HOME/launchd"
  LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

  if [ -d "$LAUNCHD_DIR" ] && ls "$LAUNCHD_DIR"/*.plist &>/dev/null; then
    for plist in "$LAUNCHD_DIR"/*.plist; do
      DST="$LAUNCH_AGENTS_DIR/$(basename "$plist")"
      cp "$plist" "$DST"
      launchctl load "$DST" 2>/dev/null || true
      echo "==> launchd 服务已安装: $(basename "$plist")"
    done
  else
    echo "→ 跳过 launchd（无 plist 文件或非 macOS）"
  fi
fi

# ── 6. 验证 MCP 服务器 ────────────────────────────────────────────────────
echo ""
echo "==> 验证 MCP 服务器连接..."
if [ -f "$HERMES_CONFIG_HOME/config.yaml" ]; then
  # 检查 OpenChronicle
  if grep -q "openchronicle" "$HERMES_CONFIG_HOME/config.yaml" 2>/dev/null; then
    if curl -s http://127.0.0.1:8742/mcp &>/dev/null; then
      echo "  ✓ OpenChronicle MCP: 在线"
    else
      echo "  ⚠ OpenChronicle MCP: 未运行（可选，用于本地记忆搜索）"
    fi
  fi
fi

# ── 完成 ──────────────────────────────────────────────────────────────────
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Hermes 多Agent系统配置部署完成"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "  后续步骤:"
echo "  1. 填写 API 密钥:  cp ~/.hermes/.env.example ~/.hermes/.env && vim ~/.hermes/.env"
echo "  2. 启动飞书网关:    bash ~/.hermes/bin/start-gateway.sh"
echo "  3. 验证连接:        hermes gateway list"
echo "  4. 运行自检:        在飞书中对 Hermes 说 '自检'"
