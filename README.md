# Multi-Agent Agile Workflow

A demonstration of Claude Code's multi-agent capabilities using Agile role-based subagents that collaborate to build an app.

## How to use?

Install command for teammates:                                                                                                     
``` 
  git clone git@github.com:Max-Planck-Dev/agent-workflow-dev.git /tmp/agent-workflow && bash /tmp/agent-workflow/setup.sh . && rm -rf /tmp/agent-workflow       
```

## What Is This?

Nine specialized AI agents — Product Owner, UX Designer, Architect, Developer, Code Reviewer, Security Reviewer, DevOps Engineer, QA Tester, and Scrum Master — work together through a standard Agile pipeline. Each agent has a defined role, reads artifacts from previous phases, and produces its own outputs. Two additional orchestration skills (`feeling-lucky`, `report`) drive the full pipeline and produce release-handoff documents.

**No pre-scaffolding.** Agents handle everything from requirements through implementation.

## Commands

| Command | What it does |
|---------|--------------|
| `/maxPlanck-kickoff` | Product Owner writes PRD + stories from your idea |
| `/maxPlanck-ux` | UX Designer creates wireframes and component specs |
| `/maxPlanck-design` | Architect designs the technical system |
| `/maxPlanck-develop` | Developer scaffolds the project and implements features |
| `/maxPlanck-review` | Code Reviewer audits the implementation |
| `/maxPlanck-security` | Security Reviewer audits and writes Infrastructure Security Requirements |
| `/maxPlanck-devops` | DevOps creates IaC and CI/CD pipelines |
| `/maxPlanck-test` | QA writes and runs tests |
| `/maxPlanck-sprint` | Scrum Master reviews everything and summarizes |
| `/maxPlanck-feeling-lucky` | Runs the entire pipeline end-to-end automatically |
| `/maxPlanck-report` | Generates client update / QA checklist / platform proposals release pack |

## Tech Stack (Built by Agents)

Determined at design time by the **Architect** agent:
1. Detects existing project stack (scans for `package.json`, `pyproject.toml`, `go.mod`, etc.)
2. Respects user preferences stated in the PRD
3. Falls back to defaults defined in `.claude/maxPlanck-default-stack.md`

## Agent Pipeline

```
Product Owner → UX Designer → Architect → Developer → Code Reviewer → Security → DevOps → QA Tester → Scrum Master
```

## Observability

Every agent handoff is logged to `logs/agent-workflow.log` via two mechanisms:

1. **Lifecycle hooks** — Automatic `START`/`STOP` entries when any subagent runs
2. **Semantic logging** — Agents log their decisions and outputs inline

## Quick Start

See [QUICKSTART.md](./QUICKSTART.md) for usage instructions.
