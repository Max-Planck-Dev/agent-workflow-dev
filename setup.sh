#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────
# MaxPlanck Agent Workflow Installer
#
# Adds the maxPlanck agent team into any project's .claude/ directory.
# Safe to run on projects that already have their own agents, skills,
# and settings — everything is namespaced with "maxPlanck-" and merged.
#
# Usage (from your project root):
#
#   git clone git@github.com:Max-Planck-Dev/agent-workflow-dev.git /tmp/agent-workflow \
#     && bash /tmp/agent-workflow/setup.sh . \
#     && rm -rf /tmp/agent-workflow
#
# What it does:
#   1. Copies maxPlanck-* agent and skill files into .claude/
#   2. Copies the shared config the agents depend on:
#      maxPlanck-default-stack.md, hooks/, and CLAUDE.md (only if absent)
#   3. Merges lifecycle hooks into existing settings.json
#      (and removes the legacy broken $CLAUDE_AGENT_NAME hooks)
#   4. Creates docs/ and logs/ directories agents write to
#   5. Adds log files and Terraform state to .gitignore
#
# What it does NOT touch:
#   - Your existing agents, skills, or an existing CLAUDE.md
#   - Any source code or dependencies
# ─────────────────────────────────────────────────────────

PREFIX="maxPlanck"

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${BOLD}$1${NC}"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}!${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }

# ── Locate source .claude/ ───────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$SCRIPT_DIR/.claude" ]; then
  fail "Cannot find .claude/ directory next to this script ($SCRIPT_DIR). Is the repo intact?"
fi

# ── Determine target directory ───────────────────────────

TARGET="${1:-.}"

if [ ! -d "$TARGET" ]; then
  fail "Target directory '$TARGET' does not exist."
fi

TARGET="$(cd "$TARGET" && pwd)"

if [ "$TARGET" = "$SCRIPT_DIR" ]; then
  fail "Target is the same as the agent-workflow repo. Run this from your project directory instead."
fi

cd "$TARGET"

if [ ! -d ".git" ]; then
  warn "Not a git repository. The agent workflow expects to run inside a git repo."
  read -rp "Continue anyway? (y/N) " answer
  [[ "$answer" =~ ^[Yy]$ ]] || exit 0
fi

# ── Install agents ───────────────────────────────────────

info "Installing ${PREFIX} agent workflow..."

mkdir -p .claude/agents .claude/skills

# Copy only maxPlanck-* agent files (won't touch existing agents)
for agent_file in "$SCRIPT_DIR"/.claude/agents/${PREFIX}-*.md; do
  [ -f "$agent_file" ] || continue
  cp "$agent_file" .claude/agents/
done

ok "Installed agents (${PREFIX}-*)"

# ── Install skills ───────────────────────────────────────

# Upgrade path: phase skills were renamed to stop colliding with agent names
# (maxPlanck-security → maxPlanck-audit, maxPlanck-devops → maxPlanck-infra).
# Remove the old skill dirs so upgraded projects don't keep both.
for legacy in "${PREFIX}-security:${PREFIX}-audit" "${PREFIX}-devops:${PREFIX}-infra"; do
  old_name="${legacy%%:*}"
  new_name="${legacy##*:}"
  if [ -d ".claude/skills/$old_name" ]; then
    rm -rf ".claude/skills/$old_name"
    warn "Removed legacy skill $old_name (renamed to $new_name)"
  fi
done

# Copy only maxPlanck-* skill directories (won't touch existing skills).
# Copy the whole directory so reference files/assets travel with SKILL.md.
for skill_dir in "$SCRIPT_DIR"/.claude/skills/${PREFIX}-*/; do
  [ -d "$skill_dir" ] || continue
  skill_name=$(basename "$skill_dir")
  mkdir -p ".claude/skills/$skill_name"
  cp -R "$skill_dir". ".claude/skills/$skill_name/"
done

ok "Installed skills (${PREFIX}-*)"

# ── Install shared config the agents depend on ───────────

# Default tech stack — referenced by the Architect and DevOps agents.
cp "$SCRIPT_DIR/.claude/${PREFIX}-default-stack.md" ".claude/${PREFIX}-default-stack.md"
ok "Installed ${PREFIX}-default-stack.md"

# Lifecycle logging hook script — referenced by settings.json hooks.
mkdir -p .claude/hooks
cp "$SCRIPT_DIR/.claude/hooks/log-agent-lifecycle.sh" ".claude/hooks/log-agent-lifecycle.sh"
chmod +x ".claude/hooks/log-agent-lifecycle.sh"
ok "Installed hooks/log-agent-lifecycle.sh"

# Workflow conventions (ownership table, log format, Definition of Done).
# Never clobber an existing CLAUDE.md — the workflow depends on these
# conventions, so ask the user to merge manually instead.
if [ ! -f ".claude/CLAUDE.md" ]; then
  cp "$SCRIPT_DIR/.claude/CLAUDE.md" ".claude/CLAUDE.md"
  ok "Installed .claude/CLAUDE.md (workflow conventions)"
else
  warn ".claude/CLAUDE.md already exists — not overwritten."
  warn "  Merge the workflow conventions from $SCRIPT_DIR/.claude/CLAUDE.md into it manually."
fi

# ── Merge settings.json hooks ────────────────────────────

SETTINGS=".claude/settings.json"

merge_hooks() {
  python3 - "$SETTINGS" <<'PYEOF'
import json, sys

settings_path = sys.argv[1]

# Stable identifying key: any hook command that calls our script belongs to
# this workflow, regardless of exact quoting. This keeps the merge idempotent
# even when the command string changes between versions.
HOOK_KEY = "log-agent-lifecycle.sh"

# Legacy broken hooks from older installs ($CLAUDE_AGENT_NAME never existed) —
# remove them so they don't produce duplicate, agent-less log lines.
LEGACY_KEY = "$CLAUDE_AGENT_NAME"

workflow_hooks = {
    "SubagentStart": {
        "hooks": [{
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/log-agent-lifecycle.sh START"
        }]
    },
    "SubagentStop": {
        "hooks": [{
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/log-agent-lifecycle.sh STOP"
        }]
    }
}

# Load existing or start fresh
try:
    with open(settings_path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

if "hooks" not in settings:
    settings["hooks"] = {}

for event, hook_entry in workflow_hooks.items():
    entries = settings["hooks"].get(event, [])

    # Drop legacy broken workflow hooks (but nobody else's hooks).
    entries = [
        e for e in entries
        if not any(
            LEGACY_KEY in h.get("command", "") and "agent-workflow.log" in h.get("command", "")
            for h in e.get("hooks", [])
        )
    ]

    already_installed = any(
        HOOK_KEY in h.get("command", "")
        for e in entries
        for h in e.get("hooks", [])
    )
    if not already_installed:
        entries.append(hook_entry)

    settings["hooks"][event] = entries

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
PYEOF
}

merge_hooks
ok "Merged lifecycle hooks into settings.json"

# ── Create directory structure ───────────────────────────

# Living docs live at docs/ top level; sprint-scoped artifacts (reviews,
# test plans, security reports, summaries) go under docs/sprints/sprint-NN/,
# created by the agents. Release reports go under docs/reports/<date>/.
dirs=("docs/stories" "docs/ux" "docs/sprints" "docs/reports" "logs")
for dir in "${dirs[@]}"; do
  mkdir -p "$dir"
done
touch logs/.gitkeep

ok "Created docs/ and logs/ directories"

# ── Update .gitignore ────────────────────────────────────

# Line-by-line so a partially-present block is completed, not duplicated.
# Terraform entries matter because the DevOps agent generates infra/ code:
# state files contain plaintext secrets and must never be committed.
gitignore_lines=(
  "logs/*.log"
  "*.tfstate"
  "*.tfstate.*"
  ".terraform/"
  "*.tfvars"
  "!*.tfvars.example"
  ".claude/settings.local.json"
)

touch .gitignore
added=0
for line in "${gitignore_lines[@]}"; do
  if ! grep -qxF "$line" .gitignore 2>/dev/null; then
    if [ "$added" -eq 0 ]; then
      { echo ""; echo "# Agent workflow (logs + generated Terraform)"; } >> .gitignore
    fi
    echo "$line" >> .gitignore
    added=1
  fi
done
if [ "$added" -eq 1 ]; then
  ok "Updated .gitignore (logs + Terraform state)"
fi

# ── Done ─────────────────────────────────────────────────

echo ""
info "${PREFIX} agent workflow installed! Available commands:"
echo ""
echo "  /${PREFIX}-kickoff        — Product Owner writes PRD + stories from your idea"
echo "  /${PREFIX}-ux             — UX Designer creates wireframes"
echo "  /${PREFIX}-design         — Architect creates technical design"
echo "  /${PREFIX}-develop        — Developer implements the code"
echo "  /${PREFIX}-review         — Code Reviewer checks the implementation"
echo "  /${PREFIX}-audit          — Security Reviewer audits and writes ISRs"
echo "  /${PREFIX}-infra          — DevOps creates infrastructure and CI/CD"
echo "  /${PREFIX}-test           — QA Tester writes and runs tests"
echo "  /${PREFIX}-sprint         — Scrum Master reviews everything"
echo ""
echo "  /${PREFIX}-feeling-lucky  — Runs the entire pipeline automatically"
echo "  /${PREFIX}-change         — Runs a change request through the team (docs stay in sync)"
echo "  /${PREFIX}-report         — Generates the 4-report release pack (internal / client / release note / QA)"
echo ""
info "To get started, open Claude Code and run: /${PREFIX}-kickoff"
