#!/bin/bash
# Chrome CDP Launcher - persistent profile with remote debugging
# Usage: ./chrome-cdp.sh [--wait]
CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
PROFILE="$HOME/.hermes/chrome-profile"
PORT=9222

# Already running?
if curl -s --max-time 1 http://127.0.0.1:$PORT/json/version >/dev/null 2>&1; then
    echo "Chrome CDP already running on port $PORT"
    exit 0
fi

mkdir -p "$PROFILE"

# Launch Chrome with persistent profile
"$CHROME" \
    --remote-debugging-port=$PORT \
    --user-data-dir="$PROFILE" \
    --no-first-run \
    --no-default-browser-check \
    --new-window "https://www.xiaohongshu.com" &

CHROME_PID=$!

if [ "$1" = "--wait" ]; then
    # Wait for CDP to be ready
    for i in $(seq 1 30); do
        if curl -s --max-time 1 http://127.0.0.1:$PORT/json/version >/dev/null 2>&1; then
            echo "Chrome CDP ready on port $PORT (PID: $CHROME_PID)"
            exit 0
        fi
        sleep 1
    done
    echo "Timed out waiting for Chrome CDP"
    exit 1
fi
