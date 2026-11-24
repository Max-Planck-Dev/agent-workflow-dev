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
2. **Read the profile** — run `python3 .claude/bin/maxPlanck-config.py features` from the project root. It prints the project's profile, the phase order this run follows (`ORDER=`), and one `<switch>=on|off` line per feature. If the helper does not exist (a plugin install), the profile is `default`, every switch is `off`, and `ORDER` is the default order below. Keep the switches for the whole run: a profile change mid-sprint never alters a pipeline already running.
3. Create `docs/sprints/sprint-<NN>/pipeline-state.json` (or resume it if it exists and is unfinished):

```json
{
  "sprint": "NN",
  "started": "<timestamp>",
  "profile": "default",
  "features": { "design-system": false, "design-review": false, "plan": false, "plan-review": false, "story-loop": false, "integration-gate": false, "codex": false },
  "phase_runs": { "kickoff": 0, "ux": 0, "design": 0, "develop": 0, "review": 0, "security": 0, "devops": 0, "test": 0, "sprint": 0 },
  "verdicts": { "review": null, "security": null, "devops": null, "test": null },
  "unresolved": []
}
```

`profile` and `features` are what the helper printed; `phase_runs` and `verdicts` get a key for every phase in `ORDER`. With the `story-loop` switch, `stories` gets one entry per story as the loop reaches it — `"story-003": { "phase_runs": { "plan": 0, "plan-review": 0, "develop": 0, "review": 0 }, "verdicts": { "plan-review": null, "review": null } }` — and `current_story` names the one in progress; the sprint-level `develop` / `review` counters then count only the fix passes after the loop. When resuming, use the recorded `profile` and `features`, never the current config. A state file written before profiles existed has neither key: treat it as `default` with every switch off. Update the file after every phase (increment the run count, record verdicts, append unresolved failures). If a pipeline is interrupted and re-run in the same sprint, resume from this file instead of starting at zero.

4. Log the pipeline start, **with the goal of this run in one line** (the project idea or feature from the command arguments or conversation; for a sprint continuing existing work, the sprint's focus). The dashboard shows this line as the run's title. Right after it, log the profile and the order, copied from the helper's `PROFILE=` and `ORDER=` lines (the dashboard builds its phase list from this line):

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Full pipeline started (sprint <NN>): <goal in one line>" >> logs/agent-workflow.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Profile <name> | Order: <ORDER, space separated>" >> logs/agent-workflow.log
```

## Pipeline Order for This Run

The run's order is the helper's `ORDER=` line. With the `default` profile it is:

```
maxPlanck-kickoff → maxPlanck-ux → maxPlanck-design → maxPlanck-develop → maxPlanck-review → maxPlanck-audit → maxPlanck-infra → maxPlanck-test → maxPlanck-sprint
```

Other profiles insert optional phases into it (each has its own routing rules, marked with the switch that enables them). **"Next phase" below always means the next entry of this run's order.** A phase whose switch is off is not in the order: it is never invoked and never logged as skipped. A switch with no routing rule in this file yet is read and recorded, and nothing else.

With the `story-loop` switch the helper's `PER_STORY=` line names the phases that run once per story (`plan plan-review develop review`, minus `plan-review` when that switch is off): see The Story Loop below, which replaces those phases' rows while the loop runs.

## Phase Routing Rules

After each phase, read the relevant output to decide the next step. **Freshness rule: only artifacts produced or updated during THIS sprint satisfy a gate.** For sprint-scoped artifacts that means files under `docs/sprints/sprint-<NN>/`; for living docs (PRD, architecture) it means a Change Log entry for sprint `<NN>`. A verdict left over from a prior sprint proves nothing about the current code.

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-kickoff` | `docs/prd.md`, `docs/stories/` | If PRD has a sprint-`<NN>` Change Log entry and 3+ stories exist → `maxPlanck-ux`. Otherwise re-run `maxPlanck-kickoff`. |
| `maxPlanck-ux` | `docs/ux/`; the `**Source:**` line of the PRD's `## Design System`, if the section exists | If design files (or this-sprint revisions) exist for P0/P1 stories — and `docs/ux/design-system.md` exists whenever the PRD has that section with a source other than `none` — → `maxPlanck-design`. Otherwise re-run `maxPlanck-ux`. |
| `maxPlanck-design` | `docs/architecture.md`; *(design-review)* `python3 .claude/bin/maxPlanck-reviews.py open --kind design` and `status --kind design` | If the doc lacks models + API endpoints or a sprint-`<NN>` Change Log entry → re-run `maxPlanck-design`. **`design-review=off`:** → next phase. **`design-review=on`:** if `open` prints any ID → re-run `maxPlanck-design`, naming the open proposal IDs (a run that only rules on proposals does not count toward the design phase's run cap). Else if `status` says fewer than 2 rounds → `maxPlanck-design-review`. Else → next phase, `Reason: design-review cap (2 rounds) — round-2 proposals ruled by the Architect`. |
| `maxPlanck-design-review` *(design-review)* | the `**Verdict:**` and `**Reviewer:**` lines of `docs/sprints/sprint-<NN>/design-review.md`; `status --kind design` before and after | If **APPROVED** → next phase. If **CHANGES PROPOSED** → `maxPlanck-design`, telling the Architect to evaluate the open proposals in that report (say so in the reason if the latest round was unavailable). If **UNAVAILABLE**, or `rounds` did not grow by one → the review did not happen: log `Phase design-review skipped \| Reason: UNAVAILABLE — <reason from the report>` *instead of* a routing line, record the verdict in `pipeline-state.json`, append `"design-review: UNAVAILABLE (<reason>)"` to `unresolved` (the design went to development unreviewed; suggested next command `/maxPlanck-design-review`), and go to the next phase. Put the reviewer in every reason (the report's `**Reviewer:**` line). |
| `maxPlanck-plan` *(plan)* | `docs/sprints/sprint-<NN>/dev-plan.md` and `docs/sprints/sprint-<NN>/plans/`; *(plan-review)* `python3 .claude/bin/maxPlanck-reviews.py open --kind plan --story <S>` and `status --kind plan --story <S>` per story | Invoke it as `maxPlanck-plan all`. If the index lacks a `## Story Order`, or a story it lists has no `plans/<story>-plan.md` with an `## Implementation Order` and a `## Tasks` table → re-run `maxPlanck-plan all`, naming what is missing. **`plan-review=off`:** → next phase (`maxPlanck-develop`). **`plan-review=on`:** for each story in the order: if `open` prints any ID → re-run `maxPlanck-plan <S>`, naming them (a run that only rules on proposals does not count toward the plan phase's run cap); else if `status` shows `rounds` 0, or `recheck` true → `maxPlanck-plan-review <S>`. When every story is reviewed and nothing is open → next phase. |
| `maxPlanck-plan-review` *(plan-review)* | the `**Verdict:**` line of `docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md`; `status --kind plan --story <S>` before and after | If **APPROVED** → the `maxPlanck-plan` row above decides the next story or the next phase. If **CHANGES PROPOSED** → `maxPlanck-plan <S>`, telling the Tech Lead to rule on the open proposals. If **UNAVAILABLE**, or `rounds` did not grow by one → log `Phase plan-review skipped \| Reason: UNAVAILABLE — <reason>` instead of a routing line, append `"plan-review (<S>): UNAVAILABLE (<reason>)"` to `unresolved`, and continue as if approved. Put the reviewer in every reason. |
| `maxPlanck-develop` | Component paths per the `## Components` table in `docs/architecture.md`; *(integration-gate)* the Developer's `VERDICT` lines in this run's slice of the log | **`integration-gate=off`:** actually run each changed component's own build command from its own directory; advance to `maxPlanck-review` only when every changed component builds, otherwise re-run `maxPlanck-develop`. **`integration-gate=on`:** do not run builds yourself — read the lines after the last routing line into develop: `grep 'VERDICT | Agent: maxPlanck-developer |'`. Every changed component with `check PASS` and focused tests `PASS` or `NONE` → `maxPlanck-review`; a `FAIL`, or a changed component without a line → re-run `maxPlanck-develop` (`Reason: <component> check FAIL` / `no VERDICT for <component>`). |
| `maxPlanck-review` | the `**Verdict:**` lines of `docs/sprints/sprint-<NN>/reviews/*.md` (`python3 .claude/bin/maxPlanck-code-review.py status --all` prints them as JSON) | If **APPROVED** → next phase (`gate` when the switch is on, else `maxPlanck-audit`). If **NEEDS CHANGES** → `maxPlanck-develop`, telling it which review files to address. If no report was written this run (NOTHING REVIEWED) → `maxPlanck-develop`. Who reviewed — Codex or Claude — is decided inside the skill; put it in the routing reason. |
| `gate` *(integration-gate)* | only the `GATE=` and `COMPONENT=` lines of `python3 .claude/bin/maxPlanck-gate.py run` (Bash timeout 600000 ms) | Not a phase skill: run the helper yourself from the project root. It builds every in-scope component that is not `infra` once (its `Build` command, from its directory, `CI=1`) and appends an attempt to `docs/sprints/sprint-<NN>/integration-gate.md`; increment `phase_runs.gate` and record `verdicts.gate`. `GATE=PASS` → `maxPlanck-audit`, logged `Phase gate finished → routing to audit \| Reason: GATE=PASS (api, web)`. `GATE=FAIL` → `maxPlanck-develop` (`maxPlanck-develop all` with the story loop) with the report as the work order: `Phase gate finished → routing to develop \| Reason: GATE=FAIL (<failing component IDs>); work order docs/sprints/sprint-<NN>/integration-gate.md`; the fix goes on as usual (review, then the gate again). A second `GATE=FAIL` in the sprint → force-advance to `maxPlanck-audit` and append `"integration-gate: FAIL after 2 attempts (<ids>)"` to `unresolved` (next command `/maxPlanck-develop all`). Exit status 2 → log the `ERROR=`, append `"integration-gate: not run (<error>)"`, → `maxPlanck-audit`. |
| `maxPlanck-audit` | `docs/sprints/sprint-<NN>/security-report.md` | If **CLEAR** or **WARNINGS** → `maxPlanck-infra`. If **CRITICAL FINDINGS** → `maxPlanck-develop`, telling it to fix the report's critical findings. |
| `maxPlanck-infra` | `docs/devops/deployment.md` | If **READY** → `maxPlanck-test`. If **BLOCKED** → record `"devops: BLOCKED (<deferred P0 ISRs>)"` in `pipeline-state.json` `unresolved`, then advance to `maxPlanck-test` (infra blockers should not stall app QA — but they are never dropped). |
| `maxPlanck-test` | `docs/sprints/sprint-<NN>/test-plans/` | If **all tests pass** → `maxPlanck-sprint`. If **tests fail** → `maxPlanck-develop`, telling it which test reports to fix from. |
| `maxPlanck-sprint` | `docs/sprints/sprint-<NN>/sprint-summary.md` | Pipeline complete. |

## The Story Loop *(story-loop)*

Stories are built one at a time: each goes through the `PER_STORY` phases before the next one is planned, so every plan is written against the code the earlier stories actually left, and every review is one story's worth.

**Entering the loop.** Invoke `maxPlanck-plan next`: the Tech Lead writes the plan index if it does not exist and plans the first story. Then read `## Story Order` in `docs/sprints/sprint-<NN>/dev-plan.md` — that ordered list of `story-NNN` IDs is the loop. Record it in `pipeline-state.json` (`stories`, one entry each, in order) and announce it — the dashboard reads this line to show `story k/n`:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Stories in scope (sprint <NN>): story-001, story-002, story-003" >> logs/agent-workflow.log
```

If the index has no `## Story Order` or it is empty, re-run `maxPlanck-plan next` (counts as a plan run of the first story). On resume, skip the stories whose `verdicts.review` is already `APPROVED` (or whose review was force-advanced) and continue with the first that is not.

Then, for each story `<S>` in that order, set `current_story` and route by this table. **Every invocation names the story** (`maxPlanck-plan <S>`, `maxPlanck-plan-review <S>`, `maxPlanck-develop <S>`, `maxPlanck-review <S>`) — never rely on `.current-story` from the orchestrator, it is for manual runs. Routing lines carry the story on both sides: `Phase review (<S>) finished → routing to plan (<S+1>) | Reason: APPROVED — next story`; a retry is `Phase develop (<S>, re-run) finished → routing to review (<S>)`.

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-plan <S>` | `docs/sprints/sprint-<NN>/plans/<S>-plan.md`, `.current-story`; *(plan-review)* `open --kind plan --story <S>` and `status --kind plan --story <S>` | If the plan lacks an `## Implementation Order` or a `## Tasks` table, or `.current-story` does not hold `<S>` → re-run `maxPlanck-plan <S>`. **`plan-review=off`:** → `maxPlanck-develop <S>`. **`plan-review=on`:** if `open` prints any ID → re-run `maxPlanck-plan <S>`, naming them (a ruling-only run is not counted against the phase); else if `status` shows `rounds` 0 or `recheck` true → `maxPlanck-plan-review <S>`; else → `maxPlanck-develop <S>` (`Reason: proposals ruled, no CRITICAL/HIGH in the round — no re-review`, or `Reason: plan-review cap reached (2 rounds)`). |
| `maxPlanck-plan-review <S>` | the `**Verdict:**` line of `docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md`; `status` before and after | If **APPROVED** → `maxPlanck-develop <S>`. If **CHANGES PROPOSED** → `maxPlanck-plan <S>`, telling the Tech Lead to rule on the open proposals. If **UNAVAILABLE**, or `rounds` did not grow by one → log `Phase plan-review (<S>) skipped \| Reason: UNAVAILABLE — <reason>` instead of a routing line, append `"plan-review (<S>): UNAVAILABLE (<reason>)"` to `unresolved`, and go to `maxPlanck-develop <S>`. |
| `maxPlanck-develop <S>` | Component paths per the `## Components` table; the plan's `**Component(s):**` line | Actually run each changed component's own build command from its own directory. Every component the plan names builds → `maxPlanck-review <S>`. Otherwise re-run `maxPlanck-develop <S>` (never `maxPlanck-plan`). |
| `maxPlanck-review <S>` | `docs/sprints/sprint-<NN>/reviews/<S>-review.md` (its `**Verdict:**` line) | If **APPROVED** and `<S>` is not the last entry of `## Story Order` → `maxPlanck-plan <S+1>` (`Reason: APPROVED — next story`). If **APPROVED** and `<S>` is the last → the next phase after the loop (`gate` when that switch is on, else `maxPlanck-audit`; `Reason: APPROVED — last story`). If **NEEDS CHANGES** → `maxPlanck-develop <S>`, telling it which review file to address. If no report was written for `<S>` → `maxPlanck-develop <S>`. |

**Sprint-level fix passes.** When the audit, QA or the integration gate sends the work back, the whole sprint is in play, not one story: invoke `maxPlanck-develop all` (the Developer works from the reports, builds nothing new), then `maxPlanck-review all` (every story with code is re-reviewed; APPROVED → the `gate` when that switch is on, then the audit; NEEDS CHANGES → `maxPlanck-develop all`). These runs count in the sprint-level `phase_runs.develop` / `phase_runs.review`, carry no story in their routing lines, and never go through `maxPlanck-plan`. The `maxPlanck-audit` and `maxPlanck-test` rows above route to `maxPlanck-develop all` while this switch is on.

## Loop Protection

`phase_runs` in `pipeline-state.json` is the counter — persisted, not in-memory; inside the story loop it is the story's own `stories.<S>.phase_runs`. If any phase reaches **3 runs**, force-advance to the next phase in the default order, log a warning, and append the unresolved failure (e.g. `"review: NEEDS CHANGES after 3 attempts"`, or `"review (<S>): NEEDS CHANGES after 3 attempts"` in the loop) to `unresolved`. A force-advance is a recorded failure, not a success. A run in which the Architect or the Tech Lead only rules on review proposals is not counted against its phase. In the story loop a force-advanced review goes to the next story's plan (or the next phase after the last story): one story's failure does not stop the sprint, it is reported. Log it as:

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
