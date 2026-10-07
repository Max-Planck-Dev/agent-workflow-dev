---
name: maxPlanck-feeling-lucky
description: Run the entire agent workflow pipeline automatically — from kickoff through sprint review — in one command.
user-invocable: true
---

# Feeling Lucky — Full Pipeline Run

Run the entire agent workflow pipeline automatically, **adapting the next phase based on the output of the previous one**, without waiting for user input between phases.

This skill deliberately has no `context: fork` / `agent:` binding: it is an **orchestrator** and must run in the main context so it can invoke the phase skills. It logs as `Agent: orchestrator`.

## Sprint Setup (before any phase)

0. **Brownfield check** — if the project contains source code at the project root **or in any direct child directory** (a project may be several independently-buildable folders rather than one) but no `docs/prd.md`, stop and recommend `/maxPlanck-adopt` first: the founding docs must describe what exists before the pipeline can judge code against them.
1. Read `docs/sprints/.current-sprint` (create it containing `01` if missing). If the current sprint folder `docs/sprints/sprint-<NN>/` already contains a `sprint-summary.md`, the prior cycle closed — increment the counter. Call the result `<NN>`; every routing check below refers to `docs/sprints/sprint-<NN>/` only.
2. Create `docs/sprints/sprint-<NN>/pipeline-state.json` (or resume it if it exists and is unfinished):

```json
{
  "sprint": "NN",
  "started": "<timestamp>",
  "phase_runs": { "kickoff": 0, "ux": 0, "design": 0, "design-review": 0, "develop": 0, "review": 0, "security": 0, "devops": 0, "test": 0, "sprint": 0 },
  "verdicts": { "design-review": null, "review": null, "security": null, "devops": null, "test": null },
  "unresolved": []
}
```

Update it after every phase (increment the run count, record verdicts, append unresolved failures). If a pipeline is interrupted and re-run in the same sprint, resume from this file instead of starting at zero. A state file written before the design-review phase existed has no `design-review` keys — treat a missing key as `0` / `null`.

3. Log the pipeline start, **with the goal of this run in one line** (the project idea or feature from the command arguments or conversation; for a sprint continuing existing work, the sprint's focus). The dashboard shows this line as the run's title:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Full pipeline started (sprint <NN>): <goal in one line>" >> logs/agent-workflow.log
```

## Default Pipeline Order

```
maxPlanck-kickoff → maxPlanck-ux → maxPlanck-design → maxPlanck-design-review → maxPlanck-develop → maxPlanck-review → maxPlanck-audit → maxPlanck-infra → maxPlanck-test → maxPlanck-sprint
```

`maxPlanck-design-review` always runs after design. Who reviews — OpenAI Codex when its CLI is installed and working, a Claude agent otherwise — is decided inside that skill; do not check for Codex yourself. Put the reviewer in the routing reason (it is in the report's `**Reviewer:**` line), e.g. `Reason: CHANGES PROPOSED — 3 open proposals (reviewed by Claude, Codex CLI not installed)`.

## Phase Routing Rules

After each phase, read the relevant output to decide the next step. **Freshness rule: only artifacts produced or updated during THIS sprint satisfy a gate.** For sprint-scoped artifacts that means files under `docs/sprints/sprint-<NN>/`; for living docs (PRD, architecture) it means a Change Log entry for sprint `<NN>`. A verdict left over from a prior sprint proves nothing about the current code.

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-kickoff` | `docs/prd.md`, `docs/stories/` | If PRD has a sprint-`<NN>` Change Log entry and 3+ stories exist → `maxPlanck-ux`. Otherwise re-run `maxPlanck-kickoff`. |
| `maxPlanck-ux` | `docs/ux/` | If design files (or this-sprint revisions) exist for P0/P1 stories → `maxPlanck-design`. Otherwise re-run `maxPlanck-ux`. |
| `maxPlanck-design` | `docs/architecture.md`, `docs/sprints/sprint-<NN>/design-review.md` (if it exists) | If the doc lacks models + API endpoints or a sprint-`<NN>` Change Log entry → re-run `maxPlanck-design`. If a design review report exists and any of its proposals is still open (see the check below) → re-run `maxPlanck-design`, naming the open proposal IDs. Otherwise → `maxPlanck-design-review`. |
| `maxPlanck-design-review` | `docs/sprints/sprint-<NN>/design-review.md` (the `**Verdict:**`, `**Latest round:**` and `**Reviewer:**` lines) | If **APPROVED** → `maxPlanck-develop`. If **CHANGES PROPOSED** → `maxPlanck-design`, telling the Architect to evaluate the open proposals in that report (say so in the reason if the latest round was unavailable). If **UNAVAILABLE**, or this run filed no round (see the check below) → the review did not happen: log `Phase design-review skipped \| Reason: UNAVAILABLE — <reason from the report>` *instead of* a routing line, record the verdict in `pipeline-state.json`, append `"design-review: UNAVAILABLE (<reason>)"` to `unresolved` (the design went to development unreviewed; suggested next command `/maxPlanck-design-review`), and go to `maxPlanck-develop`. |
| `maxPlanck-develop` | Component paths per the `## Components` table in `docs/architecture.md` | Actually run each changed component's own build command from its own directory. Advance to `maxPlanck-review` only when every changed component builds. Otherwise re-run `maxPlanck-develop`. |
| `maxPlanck-review` | `docs/sprints/sprint-<NN>/reviews/` | If **APPROVED** → `maxPlanck-audit`. If **NEEDS CHANGES** → `maxPlanck-develop`, telling it which review files to address. |
| `maxPlanck-audit` | `docs/sprints/sprint-<NN>/security-report.md` | If **CLEAR** or **WARNINGS** → `maxPlanck-infra`. If **CRITICAL FINDINGS** → `maxPlanck-develop`, telling it to fix the report's critical findings. |
| `maxPlanck-infra` | `docs/devops/deployment.md` | If **READY** → `maxPlanck-test`. If **BLOCKED** → record `"devops: BLOCKED (<deferred P0 ISRs>)"` in `pipeline-state.json` `unresolved`, then advance to `maxPlanck-test` (infra blockers should not stall app QA — but they are never dropped). |
| `maxPlanck-test` | `docs/sprints/sprint-<NN>/test-plans/` | If **all tests pass** → `maxPlanck-sprint`. If **tests fail** → `maxPlanck-develop`, telling it which test reports to fix from. |
| `maxPlanck-sprint` | `docs/sprints/sprint-<NN>/sprint-summary.md` | Pipeline complete. |

**Did this run file a round?** Before invoking `maxPlanck-design-review`, count the rounds already in the report — `grep -c '^## Round ' docs/sprints/sprint-<NN>/design-review.md` (no file yet = 0). Afterwards the count must be exactly one higher. If it is not, the phase produced no result, whatever an older verdict in the file says: treat it as UNAVAILABLE with the reason `no round filed`.

**Open design review proposals** — proposals in the report that the Architect has not ruled on in the `## Design Review Log` table of the architecture doc. Empty output means none are open:

```bash
comm -23 <(grep -oE '^\| *DR-<NN>-[0-9]+ *\|' docs/sprints/sprint-<NN>/design-review.md | grep -oE 'DR-<NN>-[0-9]+' | sort -u) \
         <(awk '/^## Design Review Log/{f=1;next} /^## /{f=0} f' docs/architecture.md | grep -iE '^\| *DR-<NN>-[0-9]+ *\|[^|]*\| *(ACCEPTED|PARTIAL|REJECTED) *\|' | grep -oE 'DR-<NN>-[0-9]+' | sort -u)
```

## Loop Protection

`phase_runs` in `pipeline-state.json` is the counter — persisted, not in-memory. If any phase reaches **3 runs**, force-advance to the next phase in the default order, log a warning, and append the unresolved failure (e.g. `"review: NEEDS CHANGES after 3 attempts"`) to `unresolved`. A force-advance is a recorded failure, not a success. The `design ↔ design-review` loop is counted the same way. When `design-review` is force-advanced, route to `maxPlanck-develop` and record `"design-review: CHANGES PROPOSED after 3 attempts (<n> open proposals)"` — those proposals were never evaluated, and the suggested next command is `/maxPlanck-design`. Log it as:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase <x> force-advanced → routing to <y> | Reason: 3 runs, <what is still failing>" >> logs/agent-workflow.log
```

## Between Each Phase

Log the transition:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase <completed> finished → routing to <next> | Reason: <why>" >> logs/agent-workflow.log
```

When a phase is being re-run, mark it: `Phase develop (re-run) finished → routing to review`. The pipeline dashboard counts phase runs and loops from these lines.

## After All Phases Complete

Read `unresolved` from `pipeline-state.json` and finish honestly:

- If `unresolved` is empty, log and report: `Full pipeline complete (sprint <NN>): all phases clean`.
- If not, log and report: `Pipeline complete (sprint <NN>) with <N> unresolved issue(s)` and list each one with the file that documents it and the suggested next command (e.g. `/maxPlanck-develop`, `/maxPlanck-change`). **Never report unconditional success while `unresolved` is non-empty.**

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Pipeline complete (sprint <NN>) | Unresolved: <N>" >> logs/agent-workflow.log
```

Point the user at `docs/sprints/sprint-<NN>/sprint-summary.md` for the sprint review and `logs/agent-workflow.log` for the activity timeline.
