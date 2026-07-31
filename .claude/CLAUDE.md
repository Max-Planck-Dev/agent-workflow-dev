# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent Agile workflow: 10 specialized agents collaborate to build software projects. The primary goal is **observability** — every agent handoff is logged to `logs/agent-workflow.log` so the user can trace the full chain of responsibility. The user provides their project idea during `/maxPlanck-kickoff` (or `/maxPlanck-feeling-lucky`), and the agents take it from there.

**Tech stack (built by agents):** Determined at design time by the Architect agent. Detects existing project stack, respects user preferences stated in the PRD, falls back to defaults defined in `.claude/maxPlanck-default-stack.md` when nothing else is specified.

## Architecture

Agents communicate through files, not direct messages. Each agent reads artifacts from `docs/` produced by earlier phases and writes its own outputs.

```
Product Owner → UX Designer → Architect → Developer → Code Reviewer → Security → DevOps → QA Tester → Scrum Master
                                                                                              (release-cadence) → Release Manager
```

| Agent | Writes To |
|-------|-----------|
| `maxPlanck-product-owner` | `docs/prd.md`, `docs/stories/`, `docs/sprints/.current-sprint` |
| `maxPlanck-ux-designer` | `docs/ux/` |
| `maxPlanck-architect` | `docs/architecture.md` |
| `maxPlanck-developer` | Source directories per `docs/architecture.md` (defaults: `frontend/`, `backend/`) |
| `maxPlanck-code-reviewer` | `docs/sprints/sprint-NN/reviews/` |
| `maxPlanck-security` | `docs/sprints/sprint-NN/security-report.md` |
| `maxPlanck-devops` | `infra/`, `.github/workflows/`, `docs/devops/` |
| `maxPlanck-qa-tester` | test files in source directories, `docs/sprints/sprint-NN/test-plans/` |
| `maxPlanck-scrum-master` | `docs/sprints/sprint-NN/sprint-summary.md`, `docs/sprints/sprint-NN/platform-proposals.md` |
| `maxPlanck-release-manager` | `docs/reports/<date>/` |

**File ownership is strict** — agents must only write to their designated directories. Exceptions, both explicit and narrow: (1) `logs/agent-workflow.log` — all agents append to it; (2) the Scrum Master updates the single `**Status:**` line in `docs/stories/story-NNN.md` files.

## Living Documents vs. Sprint Artifacts

Knowledge must compound across cycles — nothing is regenerated from scratch.

**Living documents** (fixed paths, updated in place, with append-only history):

- `docs/prd.md` — ends with a `## Change Log` table (`| Date | Sprint | Change |`); every edit appends an entry
- `docs/architecture.md` — same Change Log rule
- `docs/stories/story-NNN.md` — sequential numbering continues forever; changes append a `## History` entry, never silently rewrite
- `docs/ux/story-NNN-design.md` — redesigns append a `## Revision <date>` section
- `docs/devops/deployment.md` and `.github/workflows/deploy.yml` — updated incrementally, never regenerated (same rule as `infra/`)

**Sprint-scoped artifacts** (point-in-time, one folder per cycle, prior folders never modified):

```
docs/sprints/sprint-NN/
├── reviews/story-NNN-review.md
├── test-plans/story-NNN-tests.md
├── security-report.md
├── sprint-summary.md
├── platform-proposals.md
└── pipeline-state.json        (orchestrator state, feeling-lucky only)
```

The current sprint number lives in `docs/sprints/.current-sprint` (two digits). `/maxPlanck-kickoff` increments it when the prior sprint's summary exists; every other skill reads it (creating it with `01` if missing). ISR IDs in security reports are stable across the whole project: unresolved ISRs carry forward with their original IDs, new ones continue the sequence.

**Release reports** (`docs/reports/<YYYY-MM-DD>/`) are release-cadence: produced by `/maxPlanck-report` when the human decides to ship, never overwritten (same-day reruns get a `-2` suffix).

## Skills (Slash Commands)

**Step-by-step:** `/maxPlanck-kickoff` → `/maxPlanck-ux` → `/maxPlanck-design` → `/maxPlanck-develop` → `/maxPlanck-review` → `/maxPlanck-audit` → `/maxPlanck-infra` → `/maxPlanck-test` → `/maxPlanck-sprint`

Skills are phase-named; agents are role-named, and the two sets must never collide. The security phase skill is `/maxPlanck-audit` (bound to the `maxPlanck-security` agent) and the infrastructure phase skill is `/maxPlanck-infra` (bound to the `maxPlanck-devops` agent).

**Full auto:** `/maxPlanck-feeling-lucky` — runs the entire pipeline above in one command, no manual triggering between phases.

**Adopting an existing project:** `/maxPlanck-adopt` — for a codebase not started with this workflow (source code exists, no `docs/prd.md`): reverse-engineers the founding docs as-built (PRD with a Current Capabilities inventory, architecture doc with a Known Deviations & Debt section, adoption-baseline sprint-01 summary). Run this before any phase skill on a brownfield project; `setup.sh` detects the situation and recommends it at install time.

**Change requests:** `/maxPlanck-change "<description>"` — runs a post-cycle change through the team (docs updated first, then implement → review → test), so manual asks never drift out of the documented state.

**Release:** `/maxPlanck-report` — the Release Manager produces the 4-report handoff pack (internal release report, client release report, blog-style release note, QA checklist) in Markdown + HTML.

Each phase skill runs in a forked subagent context (`context: fork`) bound to its specific agent. The three **orchestrator** skills (`feeling-lucky`, `adopt`, `change`) intentionally have no fork/agent binding — they must run in the main context to invoke the other skills, and they log as `Agent: orchestrator` (a pseudo-agent name reserved for orchestrators). See `.claude/skills/*/SKILL.md` for details.

## Logging

All agents must log to `logs/agent-workflow.log` using this format:

```
[YYYY-MM-DD HH:MM:SS] <ACTION> | Agent: <full agent name, e.g. maxPlanck-developer> | <what was done> | Output: <repo-relative file path>
```

The `<ACTION>` vocabulary is fixed: `START`, `STOP` (hooks only), `ACTION` (default), `DECISION`, `VERDICT`, `PIPELINE` (orchestrators only). Agent names are always the full `maxPlanck-*` name (or `orchestrator`). Output paths are always repo-relative.

Two layers:

1. **Lifecycle hooks** (automatic `START`/`STOP`): `.claude/settings.json` wires `SubagentStart`/`SubagentStop` to `.claude/hooks/log-agent-lifecycle.sh`, which reads the hook payload from stdin and extracts the agent name from its `agent_type` field.
2. **Semantic logging**: agents log decisions inline via Bash echo, per the Logging section in each agent definition.

A third hook, `check-workflow-version.sh` on `SessionStart`, compares the installed workflow commit (`.claude/maxPlanck-workflow-version.json`, written by `setup.sh`) against the source repo at most once a week and surfaces an update hint when behind. It is a silent no-op in this repo itself and in plugin installs.

This repo is also a Claude Code plugin: `.claude-plugin/plugin.json` points `skills`/`agents`/`hooks` at the `.claude/` directories, so the same files serve script installs, plugin installs, and local development. `setup.sh --prefix <name>` produces a rebranded install (all `maxPlanck` names rewritten); rebranded installs update by re-running the installer with the same prefix.

The log grows without bound — readers (Scrum Master, orchestrators) read only the current sprint's slice, not the whole file.

## Build & Test Commands

Application code is created by agents during `/maxPlanck-develop`. Build and test commands depend on the tech stack chosen by the Architect — see the Build & Run Commands section in `docs/architecture.md`.

**When the default stack is used (see `.claude/maxPlanck-default-stack.md`):**

- **Frontend:** `cd frontend && npm install && npm run dev` (dev server), `npm run build` (build)
- **Backend:** `cd backend && npm install && npm run start:dev` (dev server), `npm run build` (build)
- **Frontend tests:** `cd frontend && npx vitest`
- **Backend tests:** `cd backend && npx jest`

## Definition of Done Per Phase

- **Adopt** (brownfield only): `docs/prd.md` as-built with a Current Capabilities inventory and adoption Change Log entry, `docs/architecture.md` as-built with verified build/run commands and a Known Deviations & Debt section, `docs/sprints/.current-sprint` at `01`, adoption-baseline sprint summary
- **Kickoff:** `docs/prd.md` with a Change Log entry for the current sprint + at least 3 prioritized stories with testable acceptance criteria + `docs/sprints/.current-sprint` correct
- **UX:** Design files (or this-sprint revisions) in `docs/ux/` for P0/P1 stories (wireframes, component specs, interaction patterns)
- **Design:** `docs/architecture.md` with data models, API endpoints, folder structure, scaffolding commands, and a Change Log entry for the current sprint
- **Develop:** Code in the source directories specified by the architecture doc that compiles and follows the architecture doc exactly; all critical feedback from this sprint's reviews/security/test reports addressed
- **Review:** Reports in `docs/sprints/sprint-NN/reviews/` with severity-categorized findings and APPROVED/NEEDS CHANGES verdict
- **Security:** Security report in `docs/sprints/sprint-NN/security-report.md` with OWASP-mapped findings, ISR table (carried + new, stable IDs), and CLEAR/WARNINGS/CRITICAL FINDINGS verdict
- **DevOps:** Terraform in `infra/`, CI/CD in `.github/workflows/deploy.yml`, deployment doc in `docs/devops/deployment.md` with ISR compliance mapping covering the current sprint's ISRs and READY/BLOCKED verdict
- **Test:** Test files covering all acceptance criteria, executed with results in `docs/sprints/sprint-NN/test-plans/`
- **Sprint:** `docs/sprints/sprint-NN/sprint-summary.md` with artifact inventory, story statuses updated, Bugs section, Undocumented Changes section (commits that bypassed the workflow, from the git-log vs activity-log cross-check), Blockers section listing every unresolved failure verdict, and next-step recommendations; `platform-proposals.md` with carried-over + new proposals
- **Report:** 8 files (4 reports × Markdown + HTML) in a new dated folder under `docs/reports/`, correct per-audience branding, open items surfaced
