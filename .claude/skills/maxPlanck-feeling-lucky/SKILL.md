---
name: maxPlanck-feeling-lucky
description: Run the entire agent workflow pipeline automatically — from kickoff through sprint review — in one command.
user-invocable: true
---

# Feeling Lucky — Full Pipeline Run

Run the entire agent workflow pipeline automatically, **adapting the next phase based on the output of the previous one**, without waiting for user input between phases.

## Instructions

Start with `maxPlanck-kickoff` and proceed through the pipeline. After each phase completes, **read its output artifacts** to determine what to do next. Do NOT ask the user for input between phases — just proceed automatically.

### Default Pipeline Order

```
maxPlanck-kickoff → maxPlanck-ux → maxPlanck-design → maxPlanck-develop → maxPlanck-review → maxPlanck-security → maxPlanck-devops → maxPlanck-test → maxPlanck-sprint
```

### Phase Routing Rules

After each phase, read the relevant output to decide the next step:

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-kickoff` | `docs/prd.md`, `docs/stories/` | If PRD and 3+ stories exist → `maxPlanck-ux`. Otherwise re-run `maxPlanck-kickoff`. |
| `maxPlanck-ux` | `docs/ux/` | If design files exist for P0/P1 stories → `maxPlanck-design`. Otherwise re-run `maxPlanck-ux`. |
| `maxPlanck-design` | `docs/architecture.md` | If architecture doc exists with models + API endpoints → `maxPlanck-develop`. Otherwise re-run `maxPlanck-design`. |
| `maxPlanck-develop` | Source directories per `docs/architecture.md` | If code exists and compiles → `maxPlanck-review`. Otherwise re-run `maxPlanck-develop`. |
| `maxPlanck-review` | `docs/reviews/` | Read the review verdict. If **APPROVED** → `maxPlanck-security`. If **NEEDS CHANGES** → `maxPlanck-develop` (to address findings). |
| `maxPlanck-security` | `docs/security/security-report.md` | Read the verdict. If **CLEAR** or **WARNINGS** → `maxPlanck-devops`. If **CRITICAL FINDINGS** → `maxPlanck-develop` (to fix vulnerabilities). |
| `maxPlanck-devops` | `docs/devops/deployment.md` | Read the verdict. If **READY** → `maxPlanck-test`. If **BLOCKED** → force-advance to `maxPlanck-test` (infra blockers should not stall app QA). |
| `maxPlanck-test` | `docs/test-plans/` | Read test results. If **all tests pass** → `maxPlanck-sprint`. If **tests fail** → `maxPlanck-develop` (to fix failures). |
| `maxPlanck-sprint` | `docs/sprint-summary.md` | Pipeline complete. |

### Loop Protection

Track how many times each phase has run. If any phase has run **3 times**, force-advance to the next phase in the default order to avoid infinite loops. Log a warning when this happens.

### Between Each Phase

Log the transition:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase <completed> finished → routing to <next> | Reason: <why>" >> logs/agent-workflow.log
```

## After All Phases Complete

Log pipeline completion:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Full pipeline complete" >> logs/agent-workflow.log
```

Tell the user: "Full pipeline complete! Check `docs/sprint-summary.md` for the sprint review and `logs/agent-workflow.log` for the complete activity timeline."
