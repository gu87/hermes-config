#!/usr/bin/env bash
set -euo pipefail
# 启动 Hermes Gateway（飞书入口）
# 前提: 已运行 bin/setup.sh 并填写 .env

HERMES_CONFIG_HOME="$(cd "$(dirname "$0")/.." && pwd)"

# 确认 .env 存在
if [ ! -f "$HERMES_CONFIG_HOME/.env" ]; then
  echo "✗ 请先填写 API 密钥: cp ~/.hermes/.env.example ~/.hermes/.env"
  exit 1
fi

# 检测 Hermes CLI
if [ -f "$HERMES_CONFIG_HOME/hermes-agent/venv/bin/python" ]; then
  PYTHON="$HERMES_CONFIG_HOME/hermes-agent/venv/bin/python"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
else
  echo "✗ 未找到 Python"
  exit 1
fi

echo "==> 启动 Hermes Gateway..."
"$PYTHON" -m hermes_cli.main gateway start

echo "==> 检查状态..."
sleep 2
"$PYTHON" -m hermes_cli.main gateway list
