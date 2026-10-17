---
name: maxPlanck-feeling-lucky
description: Run the entire agent workflow pipeline automatically — from kickoff through sprint review, one story at a time through plan, plan review, development and code review — in one command.
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
  "stories": {},
  "current_story": null,
  "unresolved": []
}
```

`stories` gets one entry per story as the story loop reaches it — `"story-003": { "phase_runs": { "plan": 0, "plan-review": 0, "develop": 0, "review": 0 }, "verdicts": { "plan-review": null, "review": null } }` — and `current_story` names the one in progress. The sprint-level `develop` / `review` counters count only the **fix passes** after the story loop (see Sprint-Level Fix Passes). Update the file after every phase (increment the right run count, record verdicts, append unresolved failures). If a pipeline is interrupted and re-run in the same sprint, resume from this file instead of starting at zero: finished stories are not redone. A state file written before the design-review phase or the story loop existed lacks some keys — treat a missing key as `0` / `null` / `{}`.

3. Log the pipeline start, **with the goal of this run in one line** (the project idea or feature from the command arguments or conversation; for a sprint continuing existing work, the sprint's focus). The dashboard shows this line as the run's title:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Full pipeline started (sprint <NN>): <goal in one line>" >> logs/agent-workflow.log
```

## Default Pipeline Order

```
maxPlanck-kickoff → maxPlanck-ux → maxPlanck-design → maxPlanck-design-review
  → for each story, in the sprint's story order:
        maxPlanck-plan → maxPlanck-plan-review → maxPlanck-develop → maxPlanck-review
  → maxPlanck-audit → maxPlanck-infra → maxPlanck-test → maxPlanck-sprint
```

`maxPlanck-design-review` always runs after design. Who reviews — OpenAI Codex when its CLI is installed and working, a Claude agent otherwise — is decided inside that skill; do not check for Codex yourself. Put the reviewer in the routing reason (it is in the report's `**Reviewer:**` line), e.g. `Reason: CHANGES PROPOSED — 3 open proposals (reviewed by Claude, Codex CLI not installed)`.

**Stories are built one at a time.** After the design review, the Tech Lead's first run writes the sprint's plan index (`docs/sprints/sprint-<NN>/dev-plan.md`, with a `## Story Order`) and plans the first story; from then on each story goes through plan → plan review → develop → code review **before the next story is planned**. Every invocation in the loop names its story explicitly (`maxPlanck-plan story-003`, `maxPlanck-plan-review story-003`, `maxPlanck-develop story-003`, `maxPlanck-review story-003`) — never rely on `.current-story` from the orchestrator, it is for manual runs. The Developer follows the story's approved plan; loops back to `maxPlanck-develop` from the code review go **straight to develop for that story** — the plan is not redone for fixes, the failing report is the work order. Which model each agent runs on is set in `.claude/maxPlanck-models.json`, not here.

## Phase Routing Rules

After each phase, read the relevant output to decide the next step. **Freshness rule: only artifacts produced or updated during THIS sprint satisfy a gate.** For sprint-scoped artifacts that means files under `docs/sprints/sprint-<NN>/`; for living docs (PRD, architecture) it means a Change Log entry for sprint `<NN>`. A verdict left over from a prior sprint proves nothing about the current code.

### Before the story loop

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-kickoff` | `docs/prd.md`, `docs/stories/` | If PRD has a sprint-`<NN>` Change Log entry and 3+ stories exist → `maxPlanck-ux`. Otherwise re-run `maxPlanck-kickoff`. |
| `maxPlanck-ux` | `docs/ux/` | If design files (or this-sprint revisions) exist for P0/P1 stories → `maxPlanck-design`. Otherwise re-run `maxPlanck-ux`. |
| `maxPlanck-design` | `docs/architecture.md`, `docs/sprints/sprint-<NN>/design-review.md` (if it exists) | If the doc lacks models + API endpoints or a sprint-`<NN>` Change Log entry → re-run `maxPlanck-design`. If a design review report exists and any of its proposals is still open (see the check below) → re-run `maxPlanck-design`, naming the open proposal IDs. Otherwise → `maxPlanck-design-review`. |
| `maxPlanck-design-review` | `docs/sprints/sprint-<NN>/design-review.md` (the `**Verdict:**`, `**Latest round:**` and `**Reviewer:**` lines) | If **APPROVED** → the story loop (first `maxPlanck-plan`). If **CHANGES PROPOSED** → `maxPlanck-design`, telling the Architect to evaluate the open proposals in that report (say so in the reason if the latest round was unavailable). If **UNAVAILABLE**, or this run filed no round (see the check below) → the review did not happen: log `Phase design-review skipped \| Reason: UNAVAILABLE — <reason from the report>` *instead of* a routing line, record the verdict in `pipeline-state.json`, append `"design-review: UNAVAILABLE (<reason>)"` to `unresolved` (the design went to development unreviewed; suggested next command `/maxPlanck-design-review`), and go to the story loop. |

### The story loop

**Entering the loop.** Invoke `maxPlanck-plan` with no story: the Tech Lead writes the plan index if it does not exist and plans the first story. Then read `## Story Order` in `docs/sprints/sprint-<NN>/dev-plan.md` — that ordered list of `story-NNN` IDs is the loop. Record it in `pipeline-state.json` (`stories`, one entry each, in order) and announce it — the dashboard reads this line to show `story k/n`:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Stories in scope (sprint <NN>): story-001, story-002, story-003" >> logs/agent-workflow.log
```

If the index has no `## Story Order` or it is empty, re-run `maxPlanck-plan` (counts as a plan run of the first story). On resume, skip the stories whose `verdicts.review` is already `APPROVED` (or whose review was force-advanced) and continue with the first that is not.

Then, for each story `<S>` in that order, set `current_story` and route by this table. `<S>` is passed to every skill.

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-plan <S>` | `docs/sprints/sprint-<NN>/plans/<S>-plan.md`, `docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md` (if it exists), `docs/sprints/sprint-<NN>/.current-story` | If the plan lacks an `## Implementation Order` or a `## Tasks` table, or `.current-story` does not hold `<S>` → re-run `maxPlanck-plan <S>`. If a plan review report exists for `<S>` and any of its proposals is still open (same check as for the design, with `PR-<NN>-<SSS>-n` IDs against that plan's `## Plan Review Log`) → re-run `maxPlanck-plan <S>`, naming the open proposal IDs. Otherwise → `maxPlanck-plan-review <S>`. If the plan's Risks & Open Questions names a design gap the Architect must resolve, say so in the reason but still advance — the Developer will log the discrepancy. |
| `maxPlanck-plan-review <S>` | `docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md` (the `**Verdict:**`, `**Latest round:**` and `**Reviewer:**` lines) | If **APPROVED** → `maxPlanck-develop <S>`. If **CHANGES PROPOSED** → `maxPlanck-plan <S>`, telling the Tech Lead to evaluate the open proposals in that report. If **UNAVAILABLE**, or this run filed no round (round-count check on this story's file) → log `Phase plan-review (<S>) skipped \| Reason: UNAVAILABLE — <reason from the report>` *instead of* a routing line, record the verdict, append `"plan-review (<S>): UNAVAILABLE (<reason>)"` to `unresolved` (suggested next command `/maxPlanck-plan-review <S>`), and go to `maxPlanck-develop <S>`. |
| `maxPlanck-develop <S>` | Component paths per the `## Components` table in `docs/architecture.md` | Actually run each changed component's own build command from its own directory. Advance to `maxPlanck-review <S>` only when every changed component builds. Otherwise re-run `maxPlanck-develop <S>` (never `maxPlanck-plan`). |
| `maxPlanck-review <S>` | `docs/sprints/sprint-<NN>/reviews/<S>-review.md` (its `**Verdict:**` and `**Reviewer:**` lines) | If **APPROVED** → the next story's `maxPlanck-plan` (`Reason: APPROVED — next story`), or `maxPlanck-audit` when `<S>` was the last (`Reason: APPROVED — last story`). If **NEEDS CHANGES** → `maxPlanck-develop <S>`, telling it which review file to address. If no report was written this run (`NOTHING REVIEWED` — the reviewer found no implementation) → `maxPlanck-develop <S>`. Who reviewed — Codex or the Claude fallback — is decided inside the skill; put it in the routing reason. |

### After the story loop

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-audit` | `docs/sprints/sprint-<NN>/security-report.md` | If **CLEAR** or **WARNINGS** → `maxPlanck-infra`. If **CRITICAL FINDINGS** → `maxPlanck-develop all` (a fix pass, see below), telling it to fix the report's critical findings. |
| `maxPlanck-infra` | `docs/devops/deployment.md` | If **READY** → `maxPlanck-test`. If **BLOCKED** → record `"devops: BLOCKED (<deferred P0 ISRs>)"` in `pipeline-state.json` `unresolved`, then advance to `maxPlanck-test` (infra blockers should not stall app QA — but they are never dropped). |
| `maxPlanck-test` | `docs/sprints/sprint-<NN>/test-plans/` | If **all tests pass** → `maxPlanck-sprint`. If **tests fail** → `maxPlanck-develop all`, telling it which test reports to fix from. |
| `maxPlanck-sprint` | `docs/sprints/sprint-<NN>/sprint-summary.md` | Pipeline complete. |

**Sprint-Level Fix Passes.** When the audit or QA sends the work back, the whole sprint is in play, not one story: invoke `maxPlanck-develop all` (the Developer works from the reports, builds nothing new), then `maxPlanck-review all` (every story with code is re-reviewed; APPROVED → `maxPlanck-audit`, NEEDS CHANGES → `maxPlanck-develop all`), and the pipeline continues from the audit as in the table above. These runs count in the sprint-level `phase_runs.develop` / `phase_runs.review`, carry no story in their routing lines, and never go through `maxPlanck-plan`.

**Did this run file a round?** Before invoking `maxPlanck-design-review` (or `maxPlanck-plan-review <S>`), count the rounds already in the report — `grep -c '^## Round ' <report>` (no file yet = 0), where the report is `docs/sprints/sprint-<NN>/design-review.md` or `docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md`. Afterwards the count must be exactly one higher. If it is not, the phase produced no result, whatever an older verdict in the file says: treat it as UNAVAILABLE with the reason `no round filed`.

**Open design review proposals** — proposals in the report that the Architect has not ruled on in the `## Design Review Log` table of the architecture doc. Empty output means none are open:

```bash
comm -23 <(grep -oE '^\| *DR-<NN>-[0-9]+ *\|' docs/sprints/sprint-<NN>/design-review.md | grep -oE 'DR-<NN>-[0-9]+' | sort -u) \
         <(awk '/^## Design Review Log/{f=1;next} /^## /{f=0} f' docs/architecture.md | grep -iE '^\| *DR-<NN>-[0-9]+ *\|[^|]*\| *(ACCEPTED|PARTIAL|REJECTED) *\|' | grep -oE 'DR-<NN>-[0-9]+' | sort -u)
```

**Open plan review proposals** for story `<S>` (number `<SSS>`) — the same, on that story's two files:

```bash
comm -23 <(grep -oE '^\| *PR-<NN>-<SSS>-[0-9]+ *\|' docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md | grep -oE 'PR-<NN>-<SSS>-[0-9]+' | sort -u) \
         <(awk '/^## Plan Review Log/{f=1;next} /^## /{f=0} f' docs/sprints/sprint-<NN>/plans/<S>-plan.md | grep -iE '^\| *PR-<NN>-<SSS>-[0-9]+ *\|[^|]*\| *(ACCEPTED|PARTIAL|REJECTED) *\|' | grep -oE 'PR-<NN>-<SSS>-[0-9]+' | sort -u)
```

(`python3 .claude/skills/maxPlanck-plan-review/plan_review.py status --story <S>` prints the same answer as JSON, under `open`.)

## Loop Protection

`phase_runs` in `pipeline-state.json` is the counter — persisted, not in-memory; inside the story loop it is the story's own `stories.<S>.phase_runs`. If any phase reaches **3 runs**, force-advance to the next phase in the default order, log a warning, and append the unresolved failure to `unresolved`. A force-advance is a recorded failure, not a success.

- `design ↔ design-review`: when `design-review` is force-advanced, route to the story loop and record `"design-review: CHANGES PROPOSED after 3 attempts (<n> open proposals)"` — those proposals were never evaluated; suggested next command `/maxPlanck-design`.
- `plan <S> ↔ plan-review <S>`: when `plan-review` is force-advanced, route to `maxPlanck-develop <S>` and record `"plan-review (<S>): CHANGES PROPOSED after 3 attempts (<n> open proposals)"` (suggested next command `/maxPlanck-plan <S>`).
- `develop <S> ↔ review <S>`: when `review` is force-advanced, route to the next story's plan (or `maxPlanck-audit` after the last) and record `"review (<S>): NEEDS CHANGES after 3 attempts"` (suggested next command `/maxPlanck-develop <S>`). The next story is still planned and built: one story's failure does not stop the sprint, it is reported.
- Sprint-level fix passes: `develop all ↔ review all` counted in the sprint-level `phase_runs`, recorded as `"review: NEEDS CHANGES after 3 attempts"`.

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase <x> (<S>) force-advanced → routing to <y> (<S'>) | Reason: 3 runs, <what is still failing>" >> logs/agent-workflow.log
```

## Between Each Phase

Log the transition. **Inside the story loop, the story goes in parentheses after the phase name on both sides** — the dashboard reads it to show which story is in progress and to tell "next story" from "retry":

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase <completed> finished → routing to <next> | Reason: <why>" >> logs/agent-workflow.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase plan (story-003) finished → routing to plan-review (story-003) | Reason: plan written, 7 tasks" >> logs/agent-workflow.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase review (story-003) finished → routing to plan (story-004) | Reason: APPROVED — next story (reviewed by OpenAI Codex)" >> logs/agent-workflow.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase review (story-005) finished → routing to audit | Reason: APPROVED — last story" >> logs/agent-workflow.log
```

When a phase is being re-run, mark it inside the same parentheses: `Phase develop (story-003, re-run) finished → routing to review (story-003)`; outside the loop, `Phase develop (re-run) finished → routing to review`. The pipeline dashboard counts phase runs, stories and loops from these lines.

## After All Phases Complete

Read `unresolved` from `pipeline-state.json` and finish honestly:

- If `unresolved` is empty, log and report: `Full pipeline complete (sprint <NN>): all phases clean`.
- If not, log and report: `Pipeline complete (sprint <NN>) with <N> unresolved issue(s)` and list each one with the file that documents it and the suggested next command (e.g. `/maxPlanck-develop story-003`, `/maxPlanck-change`). **Never report unconditional success while `unresolved` is non-empty.**

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Pipeline complete (sprint <NN>) | Unresolved: <N>" >> logs/agent-workflow.log
```

Point the user at `docs/sprints/sprint-<NN>/sprint-summary.md` for the sprint review and `logs/agent-workflow.log` for the activity timeline.
