#!/usr/bin/env bash
# Open Design production launcher — 内存节省版
set -e
cd /Users/gu/open-design
export HOME=/Users/gu
export PATH="/Users/gu/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin"
export NODE_ENV=production

# Start daemon on 14733
cd apps/daemon
OD_WEB_PORT=17456 node dist/cli.js --port 14733 --no-open &
DAEMON_PID=$!
echo "[OD] daemon PID: $DAEMON_PID"

# Serve static web on 17456
cd ../web/out
python3 -m http.server 17456 &
WEB_PID=$!
echo "[OD] web PID: $WEB_PID"

while kill -0 $DAEMON_PID 2>/dev/null && kill -0 $WEB_PID 2>/dev/null; do
  sleep 5
done

echo "[OD] One process exited, stopping both..."
kill $DAEMON_PID $WEB_PID 2>/dev/null
wait 2>/dev/null
