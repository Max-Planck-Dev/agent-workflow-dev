# Multi-Agent Agile Workflow

A demonstration of Claude Code's multi-agent capabilities using Agile role-based subagents that collaborate to build an app.

## How to use?

Install command for teammates:                                                                                                     
``` 
  git clone git@github.com:Max-Planck-Dev/agent-workflow-dev.git /tmp/agent-workflow && bash /tmp/agent-workflow/setup.sh . && rm -rf /tmp/agent-workflow       
```

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
| `/maxPlanck-change` | Runs a change request through the team — docs update first, then implement → review → test |
| `/maxPlanck-report` | Release Manager generates the 4-report release pack: internal report, client report, blog-style release note, QA checklist |

## Tech Stack (Built by Agents)

Determined at design time by the **Architect** agent:
1. Detects existing project stack (scans for `package.json`, `pyproject.toml`, `go.mod`, etc.)
2. Respects user preferences stated in the PRD
3. Falls back to defaults defined in `.claude/maxPlanck-default-stack.md`

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
