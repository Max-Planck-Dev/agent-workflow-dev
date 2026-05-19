# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Multi-agent Agile workflow: 9 specialized agents collaborate to build software projects. The primary goal is **observability** — every agent handoff is logged to `logs/agent-workflow.log` so the user can trace the full chain of responsibility. The user provides their project idea during `/maxPlanck-kickoff` (or `/maxPlanck-feeling-lucky`), and the agents take it from there.

**Tech stack (built by agents):** Determined at design time by the Architect agent. Detects existing project stack, respects user preferences stated in the PRD, falls back to defaults defined in `.claude/maxPlanck-default-stack.md` when nothing else is specified.

## Architecture

Agents communicate through files, not direct messages. Each agent reads artifacts from `docs/` produced by earlier phases and writes its own outputs.

```
Product Owner → UX Designer → Architect → Developer → Code Reviewer → Security → DevOps → QA Tester → Scrum Master
```

| Agent | Writes To |
|-------|-----------|
| `maxPlanck-product-owner` | `docs/prd.md`, `docs/stories/` |
| `maxPlanck-ux-designer` | `docs/ux/` |
| `maxPlanck-architect` | `docs/architecture.md` |
| `maxPlanck-developer` | Source directories per `docs/architecture.md` (defaults: `frontend/`, `backend/`) |
| `maxPlanck-code-reviewer` | `docs/reviews/` |
| `maxPlanck-security` | `docs/security/` |
| `maxPlanck-devops` | `infra/`, `.github/workflows/`, `docs/devops/` |
| `maxPlanck-qa-tester` | test files in source directories, `docs/test-plans/` |
| `maxPlanck-scrum-master` | `docs/sprint-summary.md` |

**File ownership is strict** — agents must only write to their designated directories. `logs/agent-workflow.log` is the exception: all agents append to it.

## Skills (Slash Commands)

**Step-by-step:** `/maxPlanck-kickoff` → `/maxPlanck-ux` → `/maxPlanck-design` → `/maxPlanck-develop` → `/maxPlanck-review` → `/maxPlanck-security` → `/maxPlanck-devops` → `/maxPlanck-test` → `/maxPlanck-sprint`

**Full auto:** `/maxPlanck-feeling-lucky` — runs the entire pipeline above in one command, no manual triggering between phases.

Each individual skill runs in a forked subagent context (`context: fork`) bound to its specific agent. See `.claude/skills/*/SKILL.md` for details.

## Logging

All agents must log to `logs/agent-workflow.log` using this format:

```
[YYYY-MM-DD HH:%M:%S] ACTION | Agent: <name> | <what was done> | Output: <file path>
```

Two layers: **lifecycle hooks** (automatic `START`/`STOP` via `.claude/settings.json` + `.claude/hooks/`) and **semantic logging** (agents log decisions inline via Bash echo).

## Build & Test Commands

Application code is created by agents during `/maxPlanck-develop`. Build and test commands depend on the tech stack chosen by the Architect — see the Build & Run Commands section in `docs/architecture.md`.

**When the default stack is used (see `.claude/maxPlanck-default-stack.md`):**

- **Frontend:** `cd frontend && npm install && npm run dev` (dev server), `npm run build` (build)
- **Backend:** `cd backend && npm install && npm run start:dev` (dev server), `npm run build` (build)
- **Frontend tests:** `cd frontend && npx vitest`
- **Backend tests:** `cd backend && npx jest`

## Definition of Done Per Phase

- **Kickoff:** `docs/prd.md` + at least 3 prioritized stories with testable acceptance criteria
- **UX:** Design files in `docs/ux/` for P0/P1 stories (wireframes, component specs, interaction patterns)
- **Design:** `docs/architecture.md` with data models, API endpoints, folder structure, scaffolding commands
- **Develop:** Code in the source directories specified by the architecture doc that compiles and follows architecture doc exactly
- **Review:** Reports in `docs/reviews/` with severity-categorized findings and APPROVED/NEEDS CHANGES verdict
- **Security:** Security report in `docs/security/security-report.md` with OWASP-mapped findings, ISR table, and CLEAR/WARNINGS/CRITICAL FINDINGS verdict
- **DevOps:** Terraform in `infra/`, CI/CD in `.github/workflows/deploy.yml`, deployment doc in `docs/devops/deployment.md` with ISR compliance mapping and READY/BLOCKED verdict
- **Test:** Test files covering all acceptance criteria, executed with results in `docs/test-plans/`
- **Sprint:** `docs/sprint-summary.md` with artifact inventory, story status, and next-step recommendations
