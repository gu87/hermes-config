#!/usr/bin/env bash
# Open Design launcher — called by launchd
cd /Users/gu/open-design
export HOME=/Users/gu
export PATH="/Users/gu/.bun/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin"
export OD_WEB_PORT=17456
/Users/gu/.bun/bin/pnpm tools-dev run web --daemon-port 14733 --web-port 17456
