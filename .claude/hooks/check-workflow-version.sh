#!/usr/bin/env bash
# SessionStart hook: once a week, check whether this project's installed
# maxPlanck workflow is behind its source repo, and surface an update hint.
#
# Reads .claude/maxPlanck-workflow-version.json (written by setup.sh).
# Silent no-op when that file is absent — which covers the source repo
# itself and plugin-based installs (plugins update through the plugin
# system, not this check).
#
# Never fails the hook and never blocks: offline, auth prompts, or a
# missing python3 all end in a silent exit.
set -u

ROOT="${CLAUDE_PROJECT_DIR:-.}"
VERSION_FILE="$ROOT/.claude/maxPlanck-workflow-version.json"
[ -f "$VERSION_FILE" ] || exit 0

# Rate limit: at most one remote check per week per project.
STAMP="$ROOT/.claude/.maxPlanck-last-update-check"
NOW="$(date +%s)"
if [ -f "$STAMP" ]; then
  LAST="$(cat "$STAMP" 2>/dev/null || echo 0)"
  case "$LAST" in *[!0-9]*) LAST=0 ;; esac
  [ $(( NOW - LAST )) -lt 604800 ] && exit 0
fi
echo "$NOW" > "$STAMP" 2>/dev/null || true

field() {
  python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2],""))' \
    "$VERSION_FILE" "$1" 2>/dev/null || true
}

SRC_URL="$(field source)"
LOCAL_SHA="$(field commit)"
PFX="$(field prefix)"
[ -n "$SRC_URL" ] && [ -n "$LOCAL_SHA" ] || exit 0
[ -n "$PFX" ] || PFX="maxPlanck"

REMOTE_SHA="$(GIT_TERMINAL_PROMPT=0 GIT_SSH_COMMAND='ssh -oBatchMode=yes -oConnectTimeout=4' \
  git ls-remote "$SRC_URL" HEAD 2>/dev/null | cut -f1)"
[ -n "$REMOTE_SHA" ] || exit 0

if [ "$REMOTE_SHA" != "$LOCAL_SHA" ]; then
  # stdout of a SessionStart hook is added to the session context, so
  # Claude can relay this to the user.
  echo "[$PFX workflow] The installed agent workflow (commit ${LOCAL_SHA:0:7}) is behind its source repo (${REMOTE_SHA:0:7})."
  echo "Update by re-running the installer from the project root:"
  echo "  git clone $SRC_URL /tmp/agent-workflow && bash /tmp/agent-workflow/setup.sh . --prefix $PFX && rm -rf /tmp/agent-workflow"
fi
exit 0
