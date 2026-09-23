# Multi-Agent Agile Workflow

A demonstration of Claude Code's multi-agent capabilities using Agile role-based subagents that collaborate to build an app.

## Installation

### Script install (recommended today)

From your project root:

```
d=$(mktemp -d) && git clone https://github.com/Max-Planck-Dev/agent-workflow-dev.git "$d" && bash "$d/setup.sh" .; rm -rf "$d"
```

The installer copies the agents, skills, hooks, and shared config into your project's `.claude/`, merges the logging hooks into your `settings.json` without touching your own hooks, and records what it installed in `.claude/maxPlanck-workflow-version.json`.

### Plugin install

The repo is also a Claude Code **plugin** (`.claude-plugin/plugin.json`): skills, agents, and the logging hooks load directly from a versioned source instead of being copied into each project. Install goes through a plugin marketplace — ours is coming soon; once it exists, installation is `/plugin marketplace add <marketplace>` + `/plugin install maxplanck`, and updates flow through the plugin system automatically (every commit is a new plugin version).

Note: plugin-installed skills are invoked with the plugin namespace (`/maxplanck:maxPlanck-kickoff`), while script installs use the bare names (`/maxPlanck-kickoff`).

### Make it your own (rebranding)

This is an open project — you can install the whole team under **your** name:

```
d=$(mktemp -d) && git clone https://github.com/Max-Planck-Dev/agent-workflow-dev.git "$d" && bash "$d/setup.sh" . --prefix acme; rm -rf "$d"
```

Every file name, skill name, agent name, and cross-reference is rewritten from `maxPlanck` to your prefix: you get `/acme-kickoff`, `/acme-feeling-lucky`, `.claude/acme-default-stack.md`, and so on. Brand the reports too via `.claude/<prefix>-brand.json`.

**Updates still work for rebranded installs** — with one rule: update by re-running the installer with the *same* `--prefix`, and don't hand-edit the installed workflow files (the update overwrites them; customize by forking the source repo instead). The weekly update check knows your prefix and prints the right command. What a rebranded install can't use is the *plugin* route, which ships fixed names.

## Multi-component projects

Your product does not have to be one folder. The Architect scans the project root one level
down, proposes which folders are part of the product and which are not, and asks you to
confirm — then records the answer in `docs/architecture.md` as a `## Components` table plus
an `### Excluded Paths` list. From then on every agent routes through it: builds and tests
run from each component's own directory with that component's own commands, and anything
under Excluded Paths is never read, tested, or reported on.

The project root itself does not need to be a git repository — the components can carry the
repositories, and each one gets its own CI pipeline in its own repo. A single-folder project
gets a one-row table and behaves exactly as before.

## Staying up to date

Script installs record their source repo and commit in `.claude/maxPlanck-workflow-version.json`. A `SessionStart` hook checks the source repo at most **once a week** (silently, offline-safe) and, when the installed commit is behind, tells you at the start of your session — with the exact re-install command to run. Updating is just re-running the installer: it overwrites the workflow's own files, cleans up renamed/legacy leftovers, and leaves your project files, your hooks, and your `CLAUDE.md` alone.

## What Is This?

Ten specialized AI agents — Product Owner, UX Designer, Architect, Developer, Code Reviewer, Security Reviewer, DevOps Engineer, QA Tester, Scrum Master, and Release Manager — work together through a standard Agile pipeline. Each agent has a defined role, reads artifacts from previous phases, and produces its own outputs. Knowledge compounds across cycles: living docs (PRD, architecture) keep append-only change logs, while per-cycle artifacts (reviews, test results, security reports, sprint summaries) land in `docs/sprints/sprint-NN/` folders. Two orchestration skills (`feeling-lucky`, `change`) drive multi-phase runs, and `report` produces the release-handoff pack.

**No pre-scaffolding.** Agents handle everything from requirements through implementation.

## Commands

| Command | What it does |
|---------|--------------|
| `/maxPlanck-kickoff` | Product Owner writes PRD + stories from your idea |
| `/maxPlanck-ux` | UX Designer creates wireframes and component specs |
| `/maxPlanck-design` | Architect designs the technical system |
| `/maxPlanck-develop` | Developer scaffolds the project and implements features |
| `/maxPlanck-review` | Code Reviewer audits the implementation |
| `/maxPlanck-audit` | Security Reviewer audits and writes Infrastructure Security Requirements |
| `/maxPlanck-infra` | DevOps creates IaC and CI/CD pipelines |
| `/maxPlanck-test` | QA writes and runs tests |
| `/maxPlanck-sprint` | Scrum Master reviews everything and summarizes |
| `/maxPlanck-feeling-lucky` | Runs the entire pipeline end-to-end automatically |
| `/maxPlanck-adopt` | Adopts an existing codebase — reverse-engineers the founding docs as-built |
| `/maxPlanck-change` | Runs a change request through the team — docs update first, then implement → review → test |
| `/maxPlanck-report` | Release Manager generates the 4-report release pack: internal report, client report, blog-style release note, QA checklist |

## Tech Stack (Built by Agents)

Determined at design time by the **Architect** agent:
1. Detects existing project stack (scans for `package.json`, `pyproject.toml`, `go.mod`, etc.)
2. Respects user preferences stated in the PRD
3. Falls back to defaults defined in `.claude/maxPlanck-default-stack.md`
4. Records every independently-buildable **component** (path, kind, git repo, CI workflow, stack) in a `## Components` table in `docs/architecture.md`, so a project root holding several separate folders — or several separate repositories — works the same way a single one does

## Agent Pipeline

```
Product Owner → UX Designer → Architect → Developer → Code Reviewer → Security → DevOps → QA Tester → Scrum Master
```

When you decide a feature set is ready to ship, the **Release Manager** (`/maxPlanck-report`) produces the client-facing handoff pack — a release-cadence step outside the sprint loop.

## Observability

Every agent handoff is logged to `logs/agent-workflow.log` via two mechanisms:

1. **Lifecycle hooks** — Automatic `START`/`STOP` entries when any subagent runs (`.claude/hooks/log-agent-lifecycle.sh` extracts the agent name from the hook payload)
2. **Semantic logging** — Agents log their decisions and outputs inline

## Quick Start

See [QUICKSTART.md](./QUICKSTART.md) for usage instructions.
