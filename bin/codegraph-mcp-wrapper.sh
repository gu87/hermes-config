#!/bin/bash
# Wrapper: keep stdin open indefinitely so the stdio MCP server stays alive.
# launchd would normally close stdin (or connect it to /dev/null), which
# causes codegraph to exit immediately.  tail -f /dev/null blocks forever
# without producing output, so codegraph waits on stdin and stays resident.
exec tail -f /dev/null 2>/dev/null | exec /Users/gu/.local/bin/codegraph serve --mcp --no-watch
