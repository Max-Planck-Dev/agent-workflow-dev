---
name: maxPlanck-feeling-lucky
description: Run the entire agent workflow pipeline automatically — from kickoff through sprint review — in one command.
user-invocable: true
---

# Feeling Lucky — Full Pipeline Run

Run the entire agent workflow pipeline automatically, **adapting the next phase based on the output of the previous one**, without waiting for user input between phases.

This skill deliberately has no `context: fork` / `agent:` binding: it is an **orchestrator** and must run in the main context so it can invoke the phase skills. It logs as `Agent: orchestrator`.

## Sprint Setup (before any phase)

0. **Brownfield check** — if the project contains source code but no `docs/prd.md`, stop and recommend `/maxPlanck-adopt` first: the founding docs must describe what exists before the pipeline can judge code against them.
1. Read `docs/sprints/.current-sprint` (create it containing `01` if missing). If the current sprint folder `docs/sprints/sprint-<NN>/` already contains a `sprint-summary.md`, the prior cycle closed — increment the counter. Call the result `<NN>`; every routing check below refers to `docs/sprints/sprint-<NN>/` only.
2. Create `docs/sprints/sprint-<NN>/pipeline-state.json` (or resume it if it exists and is unfinished):

```json
{
  "sprint": "NN",
  "started": "<timestamp>",
  "phase_runs": { "kickoff": 0, "ux": 0, "design": 0, "develop": 0, "review": 0, "security": 0, "devops": 0, "test": 0, "sprint": 0 },
  "verdicts": { "review": null, "security": null, "devops": null, "test": null },
  "unresolved": []
}
```

Update it after every phase (increment the run count, record verdicts, append unresolved failures). If a pipeline is interrupted and re-run in the same sprint, resume from this file instead of starting at zero.

3. Log the pipeline start:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Full pipeline started (sprint <NN>)" >> logs/agent-workflow.log
```

## Default Pipeline Order

```
maxPlanck-kickoff → maxPlanck-ux → maxPlanck-design → maxPlanck-develop → maxPlanck-review → maxPlanck-audit → maxPlanck-infra → maxPlanck-test → maxPlanck-sprint
```

## Phase Routing Rules

After each phase, read the relevant output to decide the next step. **Freshness rule: only artifacts produced or updated during THIS sprint satisfy a gate.** For sprint-scoped artifacts that means files under `docs/sprints/sprint-<NN>/`; for living docs (PRD, architecture) it means a Change Log entry for sprint `<NN>`. A verdict left over from a prior sprint proves nothing about the current code.

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-kickoff` | `docs/prd.md`, `docs/stories/` | If PRD has a sprint-`<NN>` Change Log entry and 3+ stories exist → `maxPlanck-ux`. Otherwise re-run `maxPlanck-kickoff`. |
| `maxPlanck-ux` | `docs/ux/` | If design files (or this-sprint revisions) exist for P0/P1 stories → `maxPlanck-design`. Otherwise re-run `maxPlanck-ux`. |
| `maxPlanck-design` | `docs/architecture.md` | If the doc has models + API endpoints and a sprint-`<NN>` Change Log entry → `maxPlanck-develop`. Otherwise re-run `maxPlanck-design`. |
| `maxPlanck-develop` | Source directories per `docs/architecture.md` | Actually run the build commands from the architecture doc's Build & Run Commands. If code exists and compiles → `maxPlanck-review`. Otherwise re-run `maxPlanck-develop`. |
| `maxPlanck-review` | `docs/sprints/sprint-<NN>/reviews/` | If **APPROVED** → `maxPlanck-audit`. If **NEEDS CHANGES** → `maxPlanck-develop`, telling it which review files to address. |
| `maxPlanck-audit` | `docs/sprints/sprint-<NN>/security-report.md` | If **CLEAR** or **WARNINGS** → `maxPlanck-infra`. If **CRITICAL FINDINGS** → `maxPlanck-develop`, telling it to fix the report's critical findings. |
| `maxPlanck-infra` | `docs/devops/deployment.md` | If **READY** → `maxPlanck-test`. If **BLOCKED** → record `"devops: BLOCKED (<deferred P0 ISRs>)"` in `pipeline-state.json` `unresolved`, then advance to `maxPlanck-test` (infra blockers should not stall app QA — but they are never dropped). |
| `maxPlanck-test` | `docs/sprints/sprint-<NN>/test-plans/` | If **all tests pass** → `maxPlanck-sprint`. If **tests fail** → `maxPlanck-develop`, telling it which test reports to fix from. |
| `maxPlanck-sprint` | `docs/sprints/sprint-<NN>/sprint-summary.md` | Pipeline complete. |

## Loop Protection

`phase_runs` in `pipeline-state.json` is the counter — persisted, not in-memory. If any phase reaches **3 runs**, force-advance to the next phase in the default order, log a warning, and append the unresolved failure (e.g. `"review: NEEDS CHANGES after 3 attempts"`) to `unresolved`. A force-advance is a recorded failure, not a success.

## Between Each Phase

Log the transition:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase <completed> finished → routing to <next> | Reason: <why>" >> logs/agent-workflow.log
```

## After All Phases Complete

Read `unresolved` from `pipeline-state.json` and finish honestly:

- If `unresolved` is empty, log and report: `Full pipeline complete (sprint <NN>): all phases clean`.
- If not, log and report: `Pipeline complete (sprint <NN>) with <N> unresolved issue(s)` and list each one with the file that documents it and the suggested next command (e.g. `/maxPlanck-develop`, `/maxPlanck-change`). **Never report unconditional success while `unresolved` is non-empty.**

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Pipeline complete (sprint <NN>) | Unresolved: <N>" >> logs/agent-workflow.log
```

Point the user at `docs/sprints/sprint-<NN>/sprint-summary.md` for the sprint review and `logs/agent-workflow.log` for the activity timeline.
