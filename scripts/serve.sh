#!/usr/bin/env bash
# Start (or restart) the web app in the background on PORT (default 8000).
set -euo pipefail
cd "$(dirname "$0")/../backend"
PIDFILE=/tmp/onboarding-webapp.pid
if [ -f "$PIDFILE" ] && kill -0 "$(cat "$PIDFILE")" 2>/dev/null; then kill "$(cat "$PIDFILE")"; sleep 1; fi
nohup uv run python -m onboarding_demo.web.main > /tmp/onboarding-webapp.log 2>&1 &
echo $! > "$PIDFILE"
echo "web app pid $(cat "$PIDFILE"), log /tmp/onboarding-webapp.log"
