#!/usr/bin/env bash
# Lifecycle logging hook for the maxPlanck agent workflow.
#
# Called from .claude/settings.json on SubagentStart / SubagentStop with the
# event name as $1. The hook payload arrives as JSON on stdin; the subagent
# name is in its "agent_type" field (there is no $CLAUDE_AGENT_NAME env var).
#
# Never fails the hook: any parse problem logs "unknown" instead.
set -u

EVENT="${1:-EVENT}"
ROOT="${CLAUDE_PROJECT_DIR:-.}"
LOG_FILE="$ROOT/logs/agent-workflow.log"

mkdir -p "$ROOT/logs"

AGENT="$(python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    print(d.get("agent_type") or d.get("subagent_type") or "unknown")
except Exception:
    print("unknown")
' 2>/dev/null || echo unknown)"

echo "[$(date '+%Y-%m-%d %H:%M:%S')] $EVENT | Agent: $AGENT" >> "$LOG_FILE"
exit 0
