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

Log the start:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Change request started (sprint <NN>): <short description>" >> logs/agent-workflow.log
```

## Pipeline

Run these phases in order, logging a `PIPELINE` transition line between each (`Phase <completed> finished → routing to <next> | Reason: <why>`, with `(re-run)` after the phase name on a repeat):

1. **Product Owner** (`maxPlanck-kickoff` context — invoke the skill with the change description): update the affected artifacts, not just the code intent:
   - If the change modifies an existing story → edit that story AND append a `## History` entry (what changed, when, why)
   - If it is new scope → create a new story (numbering continues)
   - If it affects product scope/vision → update `docs/prd.md` in place + Change Log entry
   - If it changes the look and feel or a UX pattern (layout, colors, tables, form saving, messages) and the PRD has a `## Design System` section → update the matching rows + Change Log entry; then run `maxPlanck-ux` before step 2, so the UX Designer appends a revision to `docs/ux/design-system.md` (and to the affected story designs) before any code changes. Otherwise skip it silently — most changes leave the look and feel alone
2. **Architect** (`maxPlanck-design`) — **only if the change is structural** (new data model, new endpoint, changed folder structure, new dependency — including a different component library in the PRD's `## Design System`), or if it adds, removes, moves, or re-scopes a component. Skip for pure behavior/copy/style fixes, and say so in the log: `PIPELINE | Agent: orchestrator | Phase design skipped | Reason: <why>`. When run, it updates `docs/architecture.md` in place + Change Log entry.
   **2b. Design Reviewer** (`maxPlanck-design-review`) — **only if step 2 ran.** The updated design is reviewed by OpenAI Codex when its CLI is installed, by a Claude agent otherwise (the skill decides); report to `docs/sprints/sprint-<NN>/design-review.md`. If CHANGES PROPOSED → back to step 2 so the Architect evaluates each open proposal, then review again only while the report has fewer than 2 rounds (`grep -c '^## Round '`) — after the second round's ruling go on to step 2c (max 1 retry; record anything still open as unresolved), logging the repeat as `Phase design (re-run) finished → routing to design-review`. If APPROVED → step 3. Check that the run filed a round: `grep -c '^## Round ' docs/sprints/sprint-<NN>/design-review.md` (no file = 0) must be exactly one higher after the skill than before — if not, treat the result as UNAVAILABLE with the reason `no round filed`. If UNAVAILABLE → log `PIPELINE | Agent: orchestrator | Phase design-review skipped | Reason: UNAVAILABLE — <reason from the report>`, record it as unresolved (the design went to development unreviewed), and go to step 3. If step 2 was skipped, skip this silently — there is no new design to review.
   **The story.** From step 1 on, the change has a story — the one the Product Owner edited or created (`<S>`). Steps 2c to 4 work on that one story, and every invocation names it (`maxPlanck-plan <S>`, `maxPlanck-plan-review <S>`, `maxPlanck-develop <S>`, `maxPlanck-review <S>`); routing lines carry it in parentheses as in `maxPlanck-feeling-lucky` (`Phase plan (story-007) finished → routing to plan-review (story-007)`). A change that touches several stories is run as one pass per story, in story-number order.
   **2c. Tech Lead** (`maxPlanck-plan <S>`) — write the story's development plan (`docs/sprints/sprint-<NN>/plans/<S>-plan.md`, revising it in place if the sprint already planned this story and keeping its `## Plan Review Log`; the Tech Lead writes the sprint's plan index `dev-plan.md` first if there is none, and adds the story to its `## Story Order` if it is new). **Skip only for a trivial fix** — a copy, style, or one-file behaviour change with no new contract — and say so in the log: `PIPELINE | Agent: orchestrator | Phase plan (<S>) skipped | Reason: <why>`. Retries of step 3 never re-run this step.
   **2d. Plan Reviewer** (`maxPlanck-plan-review <S>`) — **only if step 2c ran.** The plan is reviewed by OpenAI Codex when its CLI is installed, by a Claude agent otherwise (the skill decides); report to `docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md`. If CHANGES PROPOSED → back to step 2c so the Tech Lead evaluates each open proposal. After the ruling, review again only if `python3 .claude/skills/maxPlanck-plan-review/plan_review.py status --story <S>` says `"recheck": true` (the round had a CRITICAL or HIGH proposal; never a third round), logging the repeat as `Phase plan (<S>, re-run) finished → routing to plan-review (<S>)`; otherwise → step 3. If APPROVED → step 3. Check that the run filed a round (`grep -c '^## Round ' docs/sprints/sprint-<NN>/plan-reviews/<S>-plan-review.md`, no file = 0, must be exactly one higher) — if not, treat it as UNAVAILABLE. If UNAVAILABLE → log `PIPELINE | Agent: orchestrator | Phase plan-review (<S>) skipped | Reason: UNAVAILABLE — <reason>`, record it as unresolved, and go to step 3. If step 2c was skipped, skip this silently.
3. **Developer** (`maxPlanck-develop <S>`) — implement the change per the updated docs and the plan. The Developer verifies with each changed component's `Check` and `Test (focused)` commands and logs one `VERDICT` line per component; route on those lines exactly as `maxPlanck-feeling-lucky` does (Reading for Routing there) — any `FAIL` or missing line → re-run step 3 (max 1 retry, then record unresolved). Do not run builds yourself.
4. **Code Reviewer** (`maxPlanck-review <S>`) — review that story's code (by OpenAI Codex when its CLI is installed, by the Claude agent otherwise; the skill decides, say who in the log); report to `docs/sprints/sprint-<NN>/reviews/<S>-review.md`. If NEEDS CHANGES → back to step 3 (max 1 retry, then record unresolved). Log the repeat as `Phase develop (<S>, re-run) finished → routing to review (<S>)`.
   **4b. Integration gate** — once the last story of the change is APPROVED (or out of retries), run `python3 .claude/skills/maxPlanck-feeling-lucky/integration_gate.py run` from the project root (Bash timeout 600000 ms) and route on its `GATE=` / `COMPONENT=` lines exactly as `maxPlanck-feeling-lucky` does (Integration gate there): PASS → step 5 (or the audit, when it runs); FAIL → `maxPlanck-develop all` with `docs/sprints/sprint-<NN>/integration-gate.md` as the work order, then `maxPlanck-review all`, then the gate again; a second FAIL in a row → record `"integration-gate: FAIL after 2 attempts (<ids>)"` as unresolved and go on.
5. **QA Tester** (`maxPlanck-test`) — test the affected stories; report to `docs/sprints/sprint-<NN>/test-plans/`. If FAIL → back to step 3 (max 1 retry, then record unresolved).
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
