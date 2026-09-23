#!/usr/bin/env bash
# Lifecycle logging hook for the maxPlanck agent workflow.
#
# Called from .claude/settings.json (or the plugin's hooks.json) on
# SubagentStart / SubagentStop with the event name as $1. The hook payload
# arrives as JSON on stdin. All the work happens in pipeline-events.py next to
# this file: it writes the START/STOP line to logs/agent-workflow.log, resolves
# the agent name on STOP (the payload usually lacks it), records machine
# events in logs/pipeline-events.jsonl, and opens the herdr dashboard pane
# when Claude runs inside herdr.
#
# Never fails the hook: without python3 it falls back to a bare "unknown" line.
set -u

EVENT="${1:-EVENT}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if command -v python3 >/dev/null 2>&1 && [ -f "$HERE/pipeline-events.py" ]; then
  exec python3 "$HERE/pipeline-events.py" "$EVENT"
fi

ROOT="${CLAUDE_PROJECT_DIR:-.}"
mkdir -p "$ROOT/logs"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] $EVENT | Agent: unknown" >> "$ROOT/logs/agent-workflow.log"
exit 0
