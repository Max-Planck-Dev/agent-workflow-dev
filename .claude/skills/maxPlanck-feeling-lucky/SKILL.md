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
  "phase_runs": { "kickoff": 0, "ux": 0, "design": 0, "design-review": 0, "develop": 0, "review": 0, "gate": 0, "security": 0, "devops": 0, "test": 0, "sprint": 0 },
  "verdicts": { "design-review": null, "review": null, "gate": null, "security": null, "devops": null, "test": null },
  "stories": {},
  "current_story": null,
  "unresolved": []
}
```

`stories` gets one entry per story as the story loop reaches it — `"story-003": { "phase_runs": { "plan": 0, "plan-review": 0, "develop": 0, "review": 0 }, "verdicts": { "plan-review": null, "review": null } }` — and `current_story` names the one in progress. The sprint-level `develop` / `review` counters count only the **fix passes** after the story loop (see Sprint-Level Fix Passes). Update the file after every phase (increment the right run count, record verdicts, append unresolved failures). If a pipeline is interrupted and re-run in the same sprint, resume from this file instead of starting at zero: finished stories are not redone. A state file written before the design-review phase, the story loop or the integration gate existed lacks some keys — treat a missing key as `0` / `null` / `{}`.

3. Log the pipeline start, **with the goal of this run in one line** (the project idea or feature from the command arguments or conversation; for a sprint continuing existing work, the sprint's focus). The dashboard shows this line as the run's title:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Full pipeline started (sprint <NN>): <goal in one line>" >> logs/agent-workflow.log
```

## Design System Questions (before the kickoff)

The kickoff of a new project settles its design system with the user, and the phase skills run in forked contexts that cannot stop to ask. So the questions are asked **here**, once, before invoking `maxPlanck-kickoff` — the only user input of the run besides the project idea.

Skip this when `docs/prd.md` already exists (with that section the answer is recorded; without it the project predates design systems and has none), or when the product clearly has no user interface (a pure API, CLI or library — pass `Design System: none — no user interface` to the kickoff). Otherwise read `.claude/skills/maxPlanck-kickoff/design-system-questions.md` and ask its questions with the AskUserQuestion tool, in the user's language:

- First question 1 alone (an existing design system or brand guide?). With one, ask where it is, then only the questions it leaves open.
- Then rounds of up to 4 questions, in the file's order, every option with its description; layout options carry their ASCII sketch as a `preview`. A question with more options than fit offers the best four — the free answer covers the rest — and always lets the user leave it to the designer.
- Pass the answers to `maxPlanck-kickoff` in its arguments, after the idea, as the `## Design System` section that file defines — the `**Source:**` line (`new — kickoff questions (<date>)`, or `existing — <reference>` when the user named one) and the table — so the Product Owner records them without asking again.

## Default Pipeline Order

```
maxPlanck-kickoff → maxPlanck-ux → maxPlanck-design → maxPlanck-design-review
  → for each story, in the sprint's story order:
        maxPlanck-plan → maxPlanck-plan-review → maxPlanck-develop → maxPlanck-review
  → integration gate (orchestrator: builds every component once)
  → maxPlanck-audit → maxPlanck-infra → maxPlanck-test → maxPlanck-sprint
```

`maxPlanck-design-review` runs after design, at most **2 rounds** per sprint: after the second, the Architect rules on its proposals and the pipeline moves on. Who reviews — OpenAI Codex when its CLI is installed and working, a Claude agent otherwise — is decided inside that skill; do not check for Codex yourself. Put the reviewer in the routing reason (it is in the report's `**Reviewer:**` line), e.g. `Reason: CHANGES PROPOSED — 3 open proposals (reviewed by Claude, Codex CLI not installed)`.

**Stories are built one at a time.** After the design review, the Tech Lead's first run writes the sprint's plan index (`docs/sprints/sprint-<NN>/dev-plan.md`, with a `## Story Order`) and plans the first story; from then on each story goes through plan → plan review → develop → code review **before the next story is planned**. The plan review runs **once** per story; a second round runs only when the first raised a CRITICAL or HIGH proposal (`plan_review.py` decides it: `RECHECK`), never a third. The Developer verifies each story with its components' quick `Check` and `Test (focused)` commands and logs a `VERDICT` line per component; the orchestrator routes on those lines and never re-runs builds itself. The full build runs once, in the **integration gate** after the last story; the full test suites run in QA. Every invocation in the loop names its story explicitly (`maxPlanck-plan story-003`, `maxPlanck-plan-review story-003`, `maxPlanck-develop story-003`, `maxPlanck-review story-003`) — never rely on `.current-story` from the orchestrator, it is for manual runs. The Developer follows the story's approved plan; loops back to `maxPlanck-develop` from the code review go **straight to develop for that story** — the plan is not redone for fixes, the failing report is the work order. Which model each agent runs on is set in `.claude/maxPlanck-models.json`, not here.

## Reading for Routing

Route from the lines that decide; **never read a whole report into this context**. Each check below prints a line or a count — that is all the orchestrator needs:

- Verdict, latest round, reviewer of a review report: `grep -m1 -E '^\*\*Verdict:\*\*' <report>` (the same for `Latest round` and `Reviewer`; one line per field)
- A plan's required headings: `grep -cE '^## (Implementation Order|Tasks)\s*$' docs/sprints/sprint-<NN>/plans/<S>-plan.md` must be `2`; the architecture's: `grep -cE '^## (Data Models|API Endpoints)' docs/architecture.md` must be `2`
- A living doc's Change Log entry for this sprint: `awk '/^## Change Log/{f=1;next} /^## /{f=0} f' <doc> | grep -cE '^\| *[^|]+ *\| *(Sprint )?<NN> *\|'` must be at least `1`
- Stories: `ls docs/stories/story-*.md | wc -l`
- Rounds filed: `grep -c '^## Round ' <report>` (no file = 0)
- Plan re-review: `python3 .claude/skills/maxPlanck-plan-review/plan_review.py status --story <S>` — JSON with `recheck` and `open`
- The Developer's verification for story `<S>` (or `all` in a fix pass), from this develop run's slice of the log — the lines after the last routing line into it:

  ```bash
  awk '/PIPELINE \| Agent: orchestrator \|.*routing to develop \(<S>[,)]/{buf=""} {buf=buf $0 "\n"} END{printf "%s", buf}' logs/agent-workflow.log | grep 'VERDICT | Agent: maxPlanck-developer | <S>:'
  ```

  (for a fix pass, match `routing to develop \|` — no story — and grep `| all:`; when the story has no plan — a change request that skipped it — expect at least one line instead of one per planned component)
- Integration gate: only the `GATE=` and `COMPONENT=` lines the helper prints (its build output stays in `docs/sprints/sprint-<NN>/integration-gate.md` for the Developer)

## Phase Routing Rules

After each phase, read the relevant output to decide the next step. **Freshness rule: only artifacts produced or updated during THIS sprint satisfy a gate.** For sprint-scoped artifacts that means files under `docs/sprints/sprint-<NN>/`; for living docs (PRD, architecture) it means a Change Log entry for sprint `<NN>`. A verdict left over from a prior sprint proves nothing about the current code.

### Before the story loop

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-kickoff` | `docs/prd.md`, `docs/stories/` | If PRD has a sprint-`<NN>` Change Log entry and 3+ stories exist → `maxPlanck-ux`. Otherwise re-run `maxPlanck-kickoff`. |
| `maxPlanck-ux` | `docs/ux/`, the `**Source:**` line of the PRD's `## Design System` | If design files (or this-sprint revisions) exist for P0/P1 stories, and `docs/ux/design-system.md` exists when the PRD has that section with any source other than `none` → `maxPlanck-design`. Otherwise re-run `maxPlanck-ux`. |
| `maxPlanck-design` | `docs/architecture.md`, `docs/sprints/sprint-<NN>/design-review.md` (if it exists) | If the doc lacks models + API endpoints or a sprint-`<NN>` Change Log entry → re-run `maxPlanck-design`. If a design review report exists and any of its proposals is still open (see the check below) → re-run `maxPlanck-design`, naming the open proposal IDs. Otherwise, if the design review report has fewer than 2 rounds (`grep -c '^## Round '`; no file = 0) → `maxPlanck-design-review`; with 2 rounds → the story loop (`Reason: design-review cap (2 rounds) — round-2 proposals ruled by the Architect`). |
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
| `maxPlanck-plan <S>` | `docs/sprints/sprint-<NN>/plans/<S>-plan.md`, `docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md` (if it exists), `docs/sprints/sprint-<NN>/.current-story` | If the plan lacks an `## Implementation Order` or a `## Tasks` table, or `.current-story` does not hold `<S>` → re-run `maxPlanck-plan <S>`. If a plan review report exists for `<S>` and any of its proposals is still open (same check as for the design, with `PR-<NN>-<SSS>-n` IDs against that plan's `## Plan Review Log`) → re-run `maxPlanck-plan <S>`, naming the open proposal IDs. Otherwise, with no plan review report for `<S>` yet → `maxPlanck-plan-review <S>`. With one, run `plan_review.py status --story <S>`: `recheck` true → `maxPlanck-plan-review <S>` (round 2 — the last round had a CRITICAL or HIGH proposal); false → `maxPlanck-develop <S>` (`Reason: proposals ruled, no CRITICAL/HIGH in the round — no re-review`, or `Reason: plan-review cap reached (2 rounds)`). If the plan's Risks & Open Questions names a design gap the Architect must resolve, say so in the reason but still advance — the Developer will log the discrepancy. |
| `maxPlanck-plan-review <S>` | `docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md` (the `**Verdict:**`, `**Latest round:**` and `**Reviewer:**` lines) | If **APPROVED** → `maxPlanck-develop <S>`. If **CHANGES PROPOSED** → `maxPlanck-plan <S>`, telling the Tech Lead to evaluate the open proposals in that report. If **UNAVAILABLE**, or this run filed no round (round-count check on this story's file) → log `Phase plan-review (<S>) skipped \| Reason: UNAVAILABLE — <reason from the report>` *instead of* a routing line, record the verdict, append `"plan-review (<S>): UNAVAILABLE (<reason>)"` to `unresolved` (suggested next command `/maxPlanck-plan-review <S>`), and go to `maxPlanck-develop <S>`. |
| `maxPlanck-develop <S>` | The developer's `VERDICT` lines for `<S>` in this run's slice of the log (see Reading for Routing), and the plan's `**Component(s):**` line | One `VERDICT` line per component named in the plan's `**Component(s):**` line, each with `check PASS` and focused tests `PASS` or `NONE` → `maxPlanck-review <S>`. A `FAIL`, or a component without a line → re-run `maxPlanck-develop <S>` (never `maxPlanck-plan`; `Reason: <component> check FAIL` / `no VERDICT for <component>`). Do not run builds or tests yourself: the integration gate builds everything once after the last story. |
| `maxPlanck-review <S>` | `docs/sprints/sprint-<NN>/reviews/<S>-review.md` (its `**Verdict:**` and `**Reviewer:**` lines) | If **APPROVED** → the next story's `maxPlanck-plan` (`Reason: APPROVED — next story`), or the **integration gate** when `<S>` was the last (see below). If **NEEDS CHANGES** → `maxPlanck-develop <S>`, telling it which review file to address. If no report was written this run (`NOTHING REVIEWED` — the reviewer found no implementation) → `maxPlanck-develop <S>`. Who reviewed — Codex or the Claude fallback — is decided inside the skill; put it in the routing reason. |

### Integration gate

Runs after the last story's review (APPROVED or force-advanced) and after every `maxPlanck-review all` that is APPROVED. It is not a phase skill: the orchestrator runs the helper itself, from the project root, with the Bash tool timeout set to 600000 ms:

```bash
python3 .claude/skills/maxPlanck-feeling-lucky/integration_gate.py run
```

It builds every in-scope component that is not `infra` once (its `Build` command, from its directory, `CI=1`, a timeout each) and appends an attempt to `docs/sprints/sprint-<NN>/integration-gate.md`. Read only its `GATE=` and `COMPONENT=` lines; increment `phase_runs.gate`, record `verdicts.gate`, and log the result — the line does not start with `Phase`, so the dashboard does not count it as one:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Integration gate (sprint <NN>, attempt <k>): api PASS, web FAIL | Output: docs/sprints/sprint-<NN>/integration-gate.md" >> logs/agent-workflow.log
```

- `GATE=PASS` → `maxPlanck-audit`. The routing line names it: `Phase review (<S>) finished → routing to audit | Reason: APPROVED — last story; integration gate PASS` (after a fix pass: `Phase review (re-run) finished → routing to audit | Reason: APPROVED; integration gate PASS`).
- `GATE=FAIL` → `maxPlanck-develop all`, a fix pass whose work order is the gate report: `→ routing to develop | Reason: integration gate FAIL (<failing component IDs>); work order docs/sprints/sprint-<NN>/integration-gate.md`. The fix pass goes on as usual (`maxPlanck-review all`, then the gate again).
- `GATE=FAIL` when the previous gate run of this sprint also failed (`verdicts.gate` was already `FAIL`) → force-advance to `maxPlanck-audit` and append `"integration-gate: FAIL after 2 attempts (<failing component IDs>)"` to `unresolved` (suggested next command `/maxPlanck-develop all`).
- Exit status 2 (`ERROR=`) → the gate could not run: log it, append `"integration-gate: not run (<error>)"` to `unresolved` and go on to `maxPlanck-audit`.

### After the story loop

| Completed Phase | Read | Route |
|----------------|------|-------|
| `maxPlanck-audit` | `docs/sprints/sprint-<NN>/security-report.md` | If **CLEAR** or **WARNINGS** → `maxPlanck-infra`. If **CRITICAL FINDINGS** → `maxPlanck-develop all` (a fix pass, see below), telling it to fix the report's critical findings. |
| `maxPlanck-infra` | `docs/devops/deployment.md` | If **READY** → `maxPlanck-test`. If **BLOCKED** → record `"devops: BLOCKED (<deferred P0 ISRs>)"` in `pipeline-state.json` `unresolved`, then advance to `maxPlanck-test` (infra blockers should not stall app QA — but they are never dropped). |
| `maxPlanck-test` | `docs/sprints/sprint-<NN>/test-plans/` | If **all tests pass** → `maxPlanck-sprint`. If **tests fail** → `maxPlanck-develop all`, telling it which test reports to fix from. |
| `maxPlanck-sprint` | `docs/sprints/sprint-<NN>/sprint-summary.md` | Pipeline complete. |

**Sprint-Level Fix Passes.** When the audit or QA sends the work back, the whole sprint is in play, not one story: invoke `maxPlanck-develop all` (the Developer works from the reports, builds nothing new), then `maxPlanck-review all` (every story with code is re-reviewed; APPROVED → the integration gate, then `maxPlanck-audit`; NEEDS CHANGES → `maxPlanck-develop all`), and the pipeline continues from the audit as in the table above. After `maxPlanck-develop all`, read its `VERDICT … | all:` lines the same way: any `FAIL` → re-run `maxPlanck-develop all`; otherwise → `maxPlanck-review all`. These runs count in the sprint-level `phase_runs.develop` / `phase_runs.review`, carry no story in their routing lines, and never go through `maxPlanck-plan`.

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

`phase_runs` in `pipeline-state.json` is the counter — persisted, not in-memory; inside the story loop it is the story's own `stories.<S>.phase_runs`. If a phase has run **2 times** and its result still fails the route's check, force-advance to the next phase in the default order, log a warning, and append the unresolved failure to `unresolved`. A force-advance is a recorded failure, not a success. A run in which the Architect (`design`) or the Tech Lead (`plan <S>`) only rules on review proposals is not counted against that phase — do not increment it: the review side's cap (2 rounds) already bounds those loops, and their normal path is initial run, ruling, ruling.

- `design ↔ design-review`: when `design-review` is force-advanced, route to the story loop and record `"design-review: CHANGES PROPOSED after 2 attempts (<n> open proposals)"` — those proposals were never evaluated; suggested next command `/maxPlanck-design`.
- `plan <S> ↔ plan-review <S>`: the real cap is `recheck` (a second round only after a CRITICAL or HIGH proposal, never a third); this is the safety net. When `plan-review` is force-advanced, route to `maxPlanck-develop <S>` and record `"plan-review (<S>): CHANGES PROPOSED after 2 attempts (<n> open proposals)"` (suggested next command `/maxPlanck-plan <S>`).
- `develop <S> ↔ review <S>`: when `review` is force-advanced, route to the next story's plan (or `maxPlanck-audit` after the last) and record `"review (<S>): NEEDS CHANGES after 2 attempts"` (suggested next command `/maxPlanck-develop <S>`). The next story is still planned and built: one story's failure does not stop the sprint, it is reported.
- Sprint-level fix passes: `develop all ↔ review all` counted in the sprint-level `phase_runs`, recorded as `"review: NEEDS CHANGES after 2 attempts"`.
- Integration gate: two failing gate runs in a row force-advance to `maxPlanck-audit` (see Integration gate).

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase <x> (<S>) force-advanced → routing to <y> (<S'>) | Reason: 2 runs, <what is still failing>" >> logs/agent-workflow.log
```

## Between Each Phase

Log the transition. **Inside the story loop, the story goes in parentheses after the phase name on both sides** — the dashboard reads it to show which story is in progress and to tell "next story" from "retry":

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase <completed> finished → routing to <next> | Reason: <why>" >> logs/agent-workflow.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase plan (story-003) finished → routing to plan-review (story-003) | Reason: plan written, 7 tasks" >> logs/agent-workflow.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase review (story-003) finished → routing to plan (story-004) | Reason: APPROVED — next story (reviewed by OpenAI Codex)" >> logs/agent-workflow.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Phase review (story-005) finished → routing to audit | Reason: APPROVED — last story; integration gate PASS" >> logs/agent-workflow.log
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
