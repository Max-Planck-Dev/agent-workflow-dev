#!/usr/bin/env bash
# SessionStart hook: write the agent models of the project's profile
# (.claude/maxPlanck-config.json) into the installed agent files, so changing
# the profile or an override is all it takes.
#
# Claude Code reads a subagent's model from the `model:` line of its agent
# file and nothing else can set it per agent, so the choice has to be copied
# into the files. The copy is idempotent: when everything already matches,
# this prints nothing. When something changed, the helper says which agents
# moved to which model, and that line reaches the session context.
#
# Silent no-op when the config or the helper is absent — which covers the
# source repo itself and plugin installs (a plugin's agent files live in the
# plugin cache and run the shipped defaults). Never fails, never blocks.
set -u

ROOT="${CLAUDE_PROJECT_DIR:-.}"
CONFIG="$ROOT/.claude/maxPlanck-config.json"
HELPER="$ROOT/.claude/bin/maxPlanck-config.py"

[ -f "$CONFIG" ] || exit 0
[ -f "$HELPER" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

python3 "$HELPER" apply --root "$ROOT" --quiet 2>/dev/null || true
exit 0
