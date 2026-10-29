---
name: maxPlanck-change
description: Run a change request through the team — the docs update first, then the change is implemented, reviewed, and tested. Use after a cycle when you (or QA bug reports) want something changed, so manual asks never drift out of the documented state.
user-invocable: true
---

# Change Request — Mini Pipeline

The user wants something changed after (or during) a development cycle: a tweak they noticed while testing, a bug from a QA report, a small scope adjustment. Run the change through the team so **the docs are updated first and stay in sync with the code** — the whole point of this skill is that manual changes never bypass the documented state.

Like `maxPlanck-feeling-lucky`, this skill deliberately has no `context: fork` / `agent:` binding: it is an **orchestrator** and must run in the main context so it can invoke the phase skills. It logs as `Agent: orchestrator`.

## Input

The change description comes from the command arguments or conversation. If there is none, ask the user what they want changed before proceeding. Do NOT ask for input after that — run the pipeline automatically.

## Sprint Context

Read `docs/sprints/.current-sprint` (create it containing `01` if missing). A change request works **within the current sprint** — it never increments the counter. All artifacts land in `docs/sprints/sprint-<NN>/`.

Read the profile: `python3 .claude/bin/maxPlanck-config.py features` prints the project's profile, the order a change request follows (`CHANGE_ORDER=`) and one `<switch>=on|off` line per feature; without the helper (a plugin install) the profile is `default` and every switch is off. Keep the switches for the whole run. Log the start, then the profile and the order (the dashboard builds its phase list from that line):

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Change request started (sprint <NN>): <short description>" >> logs/agent-workflow.log
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Profile <name> | Order: <CHANGE_ORDER, space separated>" >> logs/agent-workflow.log
```

## Pipeline

Run these phases in order, logging a `PIPELINE` transition line between each (`Phase <completed> finished → routing to <next> | Reason: <why>`, with `(re-run)` after the phase name on a repeat). With the `default` profile the steps are exactly the numbered ones below; a profile that turns on optional phases inserts them where `CHANGE_ORDER` puts them, each with its own rule marked by its switch. A switch with no rule in this file yet is read and recorded, and nothing else:

1. **Product Owner** (`maxPlanck-kickoff` context — invoke the skill with the change description): update the affected artifacts, not just the code intent:
   - If the change modifies an existing story → edit that story AND append a `## History` entry (what changed, when, why)
   - If it is new scope → create a new story (numbering continues)
   - If it affects product scope/vision → update `docs/prd.md` in place + Change Log entry
   - If it changes the look and feel or a UX pattern (layout, colors, tables, form saving, messages) and the PRD has a `## Design System` section → update the matching rows + Change Log entry, then run `maxPlanck-ux` before step 2 so the UX Designer appends a revision to `docs/ux/design-system.md` (and to the affected story designs) before any code changes. Otherwise skip that silently — most changes leave the look and feel alone
2. **Architect** (`maxPlanck-design`) — **only if the change is structural** (new data model, new endpoint, changed folder structure, new dependency — including a different component library in the PRD's `## Design System`), or if it adds, removes, moves, or re-scopes a component. Skip for pure behavior/copy/style fixes, and say so in the log: `PIPELINE | Agent: orchestrator | Phase design skipped | Reason: <why>`. When run, it updates `docs/architecture.md` in place + Change Log entry.
   **2b. Design Reviewer** (`maxPlanck-design-review`) *(switch `design-review`)* — **only if step 2 ran.** Report to `docs/sprints/sprint-<NN>/design-review.md`. If CHANGES PROPOSED → back to step 2 so the Architect rules on each open proposal (`python3 .claude/bin/maxPlanck-reviews.py open --kind design` lists them), then review again only while `status --kind design` shows fewer than 2 rounds; after the second round's ruling go to step 3, recording anything still open as unresolved. Log the repeat as `Phase design (re-run) finished → routing to design-review`. If APPROVED → step 3. If UNAVAILABLE, or `rounds` did not grow by one → log `PIPELINE | Agent: orchestrator | Phase design-review skipped | Reason: UNAVAILABLE — <reason>`, record it as unresolved (the design went to development unreviewed), and go to step 3. With the switch off, or when step 2 was skipped, skip this silently.
   **2c. Tech Lead** (`maxPlanck-plan <story>`) *(switch `plan`)* — write or revise the development plan of the story the Product Owner touched (`docs/sprints/sprint-<NN>/plans/<story>-plan.md`; the Tech Lead writes the sprint's plan index first if there is none). **Skip only for a trivial fix** — a copy, style, or one-file behaviour change with no new contract — and say so in the log: `PIPELINE | Agent: orchestrator | Phase plan skipped | Reason: <why>`. Retries of step 3 never re-run this step. With the switch off, skip it silently.
   **2d. Plan Reviewer** (`maxPlanck-plan-review <story>`) *(switch `plan-review`)* — **only if step 2c ran.** Report to `docs/sprints/sprint-<NN>/plan-reviews/<story>-plan-review.md`. If CHANGES PROPOSED → back to step 2c so the Tech Lead rules on each open proposal (`open --kind plan --story <story>` lists them), then review again only when that round printed `RECHECK=yes` (max 1 retry; record anything still open as unresolved), logging the repeat as `Phase plan (re-run) finished → routing to plan-review`. If APPROVED → step 3. If UNAVAILABLE, or `rounds` did not grow by one → log `PIPELINE | Agent: orchestrator | Phase plan-review skipped | Reason: UNAVAILABLE — <reason>`, record it as unresolved, and go to step 3. With the switch off, or when step 2c was skipped, skip this silently.
   **The story.** From step 1 on, the change has a story — the one the Product Owner edited or created (`<S>`). With the `story-loop` switch on, steps 2c to 4 name it in every invocation (`maxPlanck-plan <S>`, `maxPlanck-plan-review <S>`, `maxPlanck-develop <S>`, `maxPlanck-review <S>`) and routing lines carry it in parentheses as in `maxPlanck-feeling-lucky`; a change that touches several stories is run as one pass per story, in story-number order. With the switch off, steps 3 and 4 run as today.
3. **Developer** (`maxPlanck-develop`) — implement the change per the updated docs (and the plan, when one exists).
4. **Code Reviewer** (`maxPlanck-review`) — review the changed code; report to `docs/sprints/sprint-<NN>/reviews/`. If NEEDS CHANGES → back to step 3 (max 2 retries, then record unresolved). Log the repeat as `Phase develop (re-run) finished → routing to review`.
   **4b. Integration gate** *(switch `integration-gate`)* — after an APPROVED review, run `python3 .claude/bin/maxPlanck-gate.py run` from the project root (Bash timeout 600000 ms) and read only its `GATE=` and `COMPONENT=` lines; log `Phase gate finished → routing to test | Reason: GATE=PASS (…)`. `GATE=FAIL` → back to step 3 with `docs/sprints/sprint-<NN>/integration-gate.md` as the work order (max 1 retry, then record unresolved). Exit status 2 → record `"integration-gate: not run (<error>)"` as unresolved and go on. With the switch off, skip this silently.
5. **QA Tester** (`maxPlanck-test`) — test the affected stories; report to `docs/sprints/sprint-<NN>/test-plans/`. If FAIL → back to step 3 (max 2 retries, then record unresolved).
6. **Scrum Master** (`maxPlanck-sprint`) — update the sprint summary and story statuses so the sprint record reflects the change.

Security note: if the change touches auth, input handling, secrets, dependencies, or infrastructure, insert `maxPlanck-audit` between steps 4 and 5. Otherwise skip it and log `PIPELINE | Agent: orchestrator | Phase audit skipped | Reason: <why>`.

## After Completion

Report honestly:

- What changed (stories touched, docs updated, files modified)
- Verdicts from review and test
- Anything unresolved after retries — with the file documenting it and the suggested next command

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Change request complete (sprint <NN>) | Unresolved: <N>" >> logs/agent-workflow.log
```
