#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────
# MaxPlanck Agent Workflow Installer
#
# Adds the agent team into any project's .claude/ directory.
# Safe to run on projects that already have their own agents, skills,
# and settings — everything is namespaced with the chosen prefix and merged.
#
# Usage (from your project root):
#
#   git clone git@github.com:Max-Planck-Dev/agent-workflow-dev.git /tmp/agent-workflow \
#     && bash /tmp/agent-workflow/setup.sh . \
#     && rm -rf /tmp/agent-workflow
#
# Options:
#   --prefix <name>   Rebrand the agent team: every "maxPlanck" in file
#                     names, skill/agent names, and content becomes <name>
#                     (e.g. --prefix acme gives you /acme-kickoff etc.).
#                     Letters, digits, and dashes; must start with a letter.
#
# Updating: re-run the exact same install command (same --prefix if you
# used one). The installer overwrites the workflow's own files, removes
# renamed/legacy leftovers, and leaves everything else alone. A weekly
# SessionStart check tells you when the source repo has moved ahead.
#
# What it does:
#   1. Copies prefixed agent and skill files into .claude/
#   2. Copies shared config: <prefix>-default-stack.md, hooks/, and
#      CLAUDE.md (only if absent)
#   3. Merges lifecycle + update-check hooks into existing settings.json
#      (and removes the legacy broken $CLAUDE_AGENT_NAME hooks)
#   4. Creates docs/ and logs/ directories agents write to
#   5. Adds log files and Terraform state to .gitignore
#   6. Writes .claude/<prefix>-workflow-version.json (source repo + commit)
#      so the update check knows what you have
#
# What it does NOT touch:
#   - Your existing agents, skills, or an existing CLAUDE.md
#   - Any source code or dependencies
# ─────────────────────────────────────────────────────────

SRC_PREFIX="maxPlanck"
PREFIX="$SRC_PREFIX"
TARGET="."

BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
NC='\033[0m'

info()  { echo -e "${BOLD}$1${NC}"; }
ok()    { echo -e "${GREEN}✓${NC} $1"; }
warn()  { echo -e "${YELLOW}!${NC} $1"; }
fail()  { echo -e "${RED}✗${NC} $1"; exit 1; }

# ── Parse arguments ──────────────────────────────────────

while [ $# -gt 0 ]; do
  case "$1" in
    --prefix)
      [ $# -ge 2 ] || fail "--prefix requires a value"
      PREFIX="$2"
      shift 2
      ;;
    --prefix=*)
      PREFIX="${1#--prefix=}"
      shift
      ;;
    -*)
      fail "Unknown option: $1"
      ;;
    *)
      TARGET="$1"
      shift
      ;;
  esac
done

if ! [[ "$PREFIX" =~ ^[A-Za-z][A-Za-z0-9-]*$ ]]; then
  fail "Invalid prefix '$PREFIX' — use letters, digits, and dashes, starting with a letter."
fi

# ── Locate source .claude/ ───────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ ! -d "$SCRIPT_DIR/.claude" ]; then
  fail "Cannot find .claude/ directory next to this script ($SCRIPT_DIR). Is the repo intact?"
fi

# Record where this install came from, for the update check.
SRC_COMMIT="$(git -C "$SCRIPT_DIR" rev-parse HEAD 2>/dev/null || echo unknown)"
SRC_URL="$(git -C "$SCRIPT_DIR" remote get-url origin 2>/dev/null || echo 'git@github.com:Max-Planck-Dev/agent-workflow-dev.git')"

# ── Determine target directory ───────────────────────────

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

# ── Detect brownfield project (existing code, no founding docs) ──

# A project with source code but no docs/prd.md needs the adopt skill first:
# the founding docs must describe what exists before the phase skills can
# judge code against them.
BROWNFIELD=0
if [ ! -f "docs/prd.md" ]; then
  for cfg in package.json pyproject.toml Cargo.toml go.mod pom.xml build.gradle Gemfile composer.json mix.exs; do
    if [ -f "$cfg" ]; then
      BROWNFIELD=1
      break
    fi
  done
  if [ "$BROWNFIELD" -eq 0 ]; then
    for dir in src app lib frontend backend; do
      if [ -d "$dir" ]; then
        BROWNFIELD=1
        break
      fi
    done
  fi
fi

# ── Rendering helpers ────────────────────────────────────

# render <src> <dst>: copy a text file, rewriting the source prefix to the
# chosen one (identity when no --prefix was given). Filenames are rewritten
# by the callers the same way.
render() {
  sed -e "s/${SRC_PREFIX}/${PREFIX}/g" "$1" > "$2"
}

# rebrand <name>: rewrite the prefix inside a file/dir name
rebrand() {
  echo "${1//${SRC_PREFIX}/${PREFIX}}"
}

# ── Install agents ───────────────────────────────────────

if [ "$PREFIX" = "$SRC_PREFIX" ]; then
  info "Installing ${PREFIX} agent workflow..."
else
  info "Installing agent workflow rebranded as '${PREFIX}'..."
fi

mkdir -p .claude/agents .claude/skills

for agent_file in "$SCRIPT_DIR"/.claude/agents/${SRC_PREFIX}-*.md; do
  [ -f "$agent_file" ] || continue
  render "$agent_file" ".claude/agents/$(rebrand "$(basename "$agent_file")")"
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

# Copy only the workflow's skill directories (won't touch existing skills).
# Every file inside travels, with the prefix rewritten in names and content.
for skill_dir in "$SCRIPT_DIR"/.claude/skills/${SRC_PREFIX}-*/; do
  [ -d "$skill_dir" ] || continue
  dst_dir=".claude/skills/$(rebrand "$(basename "$skill_dir")")"
  mkdir -p "$dst_dir"
  find "$skill_dir" -type f | while read -r f; do
    rel="${f#"$skill_dir"}"
    dst="$dst_dir/$(rebrand "$rel")"
    mkdir -p "$(dirname "$dst")"
    case "$f" in
      *.md|*.sh|*.json|*.txt|*.yml|*.yaml) render "$f" "$dst" ;;
      *) cp "$f" "$dst" ;;
    esac
  done
done

ok "Installed skills (${PREFIX}-*)"

# ── Install shared config the agents depend on ───────────

# Default tech stack — referenced by the Architect and DevOps agents.
render "$SCRIPT_DIR/.claude/${SRC_PREFIX}-default-stack.md" ".claude/${PREFIX}-default-stack.md"
ok "Installed ${PREFIX}-default-stack.md"

# Hook scripts — lifecycle logging + weekly update check.
mkdir -p .claude/hooks
for hook_script in "$SCRIPT_DIR"/.claude/hooks/*.sh; do
  [ -f "$hook_script" ] || continue
  dst=".claude/hooks/$(rebrand "$(basename "$hook_script")")"
  render "$hook_script" "$dst"
  chmod +x "$dst"
done
ok "Installed hook scripts"

# Workflow conventions (ownership table, log format, Definition of Done).
# Never clobber an existing CLAUDE.md — the workflow depends on these
# conventions, so ask the user to merge manually instead.
if [ ! -f ".claude/CLAUDE.md" ]; then
  render "$SCRIPT_DIR/.claude/CLAUDE.md" ".claude/CLAUDE.md"
  ok "Installed .claude/CLAUDE.md (workflow conventions)"
else
  warn ".claude/CLAUDE.md already exists — not overwritten."
  warn "  Merge the workflow conventions from $SCRIPT_DIR/.claude/CLAUDE.md into it manually."
fi

# ── Write version stamp ──────────────────────────────────

# Read by .claude/hooks/check-workflow-version.sh (weekly SessionStart
# check) and by humans wondering what's installed. Committed on purpose:
# the whole team shares one installed version.
cat > ".claude/${PREFIX}-workflow-version.json" <<EOF
{
  "source": "$SRC_URL",
  "commit": "$SRC_COMMIT",
  "prefix": "$PREFIX",
  "installedAt": "$(date '+%Y-%m-%d')"
}
EOF
ok "Wrote ${PREFIX}-workflow-version.json (commit ${SRC_COMMIT:0:7})"

# ── Merge settings.json hooks ────────────────────────────

SETTINGS=".claude/settings.json"

merge_hooks() {
  python3 - "$SETTINGS" <<'PYEOF'
import json, sys

settings_path = sys.argv[1]

# Stable identifying keys: any hook command that calls one of our scripts
# belongs to this workflow, regardless of exact quoting. This keeps the
# merge idempotent even when the command string changes between versions.
# Legacy broken hooks from older installs ($CLAUDE_AGENT_NAME never
# existed) are removed so they don't produce agent-less log lines.
LEGACY_KEY = "$CLAUDE_AGENT_NAME"

workflow_hooks = {
    "SubagentStart": ("log-agent-lifecycle.sh", {
        "hooks": [{
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/log-agent-lifecycle.sh START"
        }]
    }),
    "SubagentStop": ("log-agent-lifecycle.sh", {
        "hooks": [{
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/log-agent-lifecycle.sh STOP"
        }]
    }),
    "SessionStart": ("check-workflow-version.sh", {
        "hooks": [{
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check-workflow-version.sh"
        }]
    }),
}

try:
    with open(settings_path) as f:
        settings = json.load(f)
except (FileNotFoundError, json.JSONDecodeError):
    settings = {}

if "hooks" not in settings:
    settings["hooks"] = {}

for event, (hook_key, hook_entry) in workflow_hooks.items():
    entries = settings["hooks"].get(event, [])

    entries = [
        e for e in entries
        if not any(
            LEGACY_KEY in h.get("command", "") and "agent-workflow.log" in h.get("command", "")
            for h in e.get("hooks", [])
        )
    ]

    already_installed = any(
        hook_key in h.get("command", "")
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
ok "Merged lifecycle + update-check hooks into settings.json"

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
  ".claude/.${PREFIX}-last-update-check"
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
info "Agent workflow installed! Available commands:"
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
echo "  /${PREFIX}-adopt          — Adopts an existing codebase (reverse-engineers founding docs)"
echo "  /${PREFIX}-change         — Runs a change request through the team (docs stay in sync)"
echo "  /${PREFIX}-report         — Generates the 4-report release pack (internal / client / release note / QA)"
echo ""
if [ "$BROWNFIELD" -eq 1 ]; then
  warn "Existing project detected without founding docs (no docs/prd.md)."
  warn "The workflow needs docs that describe what already exists before any"
  warn "phase can run honestly."
  echo ""
  info "To get started, open Claude Code and run: /${PREFIX}-adopt"
else
  info "To get started, open Claude Code and run: /${PREFIX}-kickoff"
fi
if [ "$PREFIX" != "$SRC_PREFIX" ]; then
  echo ""
  warn "Rebranded install: to update later, re-run this installer with the SAME"
  warn "prefix (--prefix ${PREFIX}). Hand-edits to the installed workflow files"
  warn "will be overwritten on update — customize upstream instead."
fi
