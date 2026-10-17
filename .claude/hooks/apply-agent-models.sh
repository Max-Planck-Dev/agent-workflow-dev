#!/usr/bin/env bash
# SessionStart hook: write the models chosen in .claude/maxPlanck-models.json
# into the installed agent files, so editing that file is all it takes.
#
# Claude Code reads a subagent's model from the `model:` line of its agent
# file and nothing else can set it per agent, so the config has to be copied
# into the files. The copy is idempotent: when everything already matches,
# this prints nothing. When something changed, the applier says which agents
# moved to which model, and that line reaches the session context.
#
# Silent no-op when the config or the applier is absent — which covers the
# source repo itself and plugin installs (a plugin's agent files live in the
# plugin cache and are not rewritten; they run with the shipped defaults).
# Never fails the hook and never blocks.
set -u

ROOT="${CLAUDE_PROJECT_DIR:-.}"
CONFIG="$ROOT/.claude/maxPlanck-models.json"
APPLIER="$ROOT/.claude/bin/maxPlanck-models.py"

[ -f "$CONFIG" ] || exit 0
[ -f "$APPLIER" ] || exit 0
command -v python3 >/dev/null 2>&1 || exit 0

# stdout of a SessionStart hook is added to the session context, so a
# changed model (or a broken config) is surfaced to the user.
python3 "$APPLIER" apply --root "$ROOT" --quiet 2>/dev/null || true
exit 0
