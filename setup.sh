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
#   2. Merges lifecycle hooks into existing settings.json
#   3. Creates docs/ and logs/ directories agents write to
#   4. Adds log files to .gitignore
#
# What it does NOT touch:
#   - Your existing agents, skills, or CLAUDE.md
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

# Copy only maxPlanck-* skill directories (won't touch existing skills)
for skill_dir in "$SCRIPT_DIR"/.claude/skills/${PREFIX}-*/; do
  [ -d "$skill_dir" ] || continue
  skill_name=$(basename "$skill_dir")
  mkdir -p ".claude/skills/$skill_name"
  cp "$skill_dir"SKILL.md ".claude/skills/$skill_name/SKILL.md"
done

ok "Installed skills (${PREFIX}-*)"

# ── Merge settings.json hooks ────────────────────────────

SETTINGS=".claude/settings.json"

merge_hooks() {
  python3 - "$SETTINGS" <<'PYEOF'
import json, sys

settings_path = sys.argv[1]

# The hooks we want to ensure exist
workflow_hooks = {
    "SubagentStart": {
        "hooks": [{
            "type": "command",
            "command": "echo \"[$(date '+%Y-%m-%d %H:%M:%S')] START | Agent: $CLAUDE_AGENT_NAME\" >> logs/agent-workflow.log"
        }]
    },
    "SubagentStop": {
        "hooks": [{
            "type": "command",
            "command": "echo \"[$(date '+%Y-%m-%d %H:%M:%S')] STOP  | Agent: $CLAUDE_AGENT_NAME\" >> logs/agent-workflow.log"
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
    if event not in settings["hooks"]:
        settings["hooks"][event] = []

    # Check if this exact hook command already exists
    existing_commands = set()
    for entry in settings["hooks"][event]:
        for h in entry.get("hooks", []):
            existing_commands.add(h.get("command", ""))

    if hook_entry["hooks"][0]["command"] not in existing_commands:
        settings["hooks"][event].append(hook_entry)

with open(settings_path, "w") as f:
    json.dump(settings, f, indent=2)
    f.write("\n")
PYEOF
}

merge_hooks
ok "Merged lifecycle hooks into settings.json"

# ── Create directory structure ───────────────────────────

dirs=("docs/stories" "docs/ux" "docs/reviews" "docs/test-plans" "logs")
for dir in "${dirs[@]}"; do
  mkdir -p "$dir"
done
touch logs/.gitkeep

ok "Created docs/ and logs/ directories"

# ── Update .gitignore ────────────────────────────────────

if [ -f ".gitignore" ]; then
  if ! grep -q "logs/\*.log" .gitignore 2>/dev/null; then
    echo "" >> .gitignore
    echo "# Agent workflow logs" >> .gitignore
    echo "logs/*.log" >> .gitignore
    ok "Added logs/*.log to .gitignore"
  fi
else
  cat > .gitignore <<'EOF'
# Agent workflow logs
logs/*.log
EOF
  ok "Created .gitignore with logs/*.log"
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
echo "  /${PREFIX}-security       — Security Reviewer audits and writes ISRs"
echo "  /${PREFIX}-devops         — DevOps creates infrastructure and CI/CD"
echo "  /${PREFIX}-test           — QA Tester writes and runs tests"
echo "  /${PREFIX}-sprint         — Scrum Master reviews everything"
echo ""
echo "  /${PREFIX}-feeling-lucky  — Runs the entire pipeline automatically"
echo "  /${PREFIX}-report         — Generates client / QA / proposals release pack"
echo ""
info "To get started, open Claude Code and run: /${PREFIX}-kickoff"
