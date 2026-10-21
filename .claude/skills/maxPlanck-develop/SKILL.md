---
name: maxPlanck-develop
description: Run development — the Developer implements one story from its development plan and the architecture doc (or runs a fix pass across the sprint from the feedback reports).
user-invocable: true
context: fork
agent: maxPlanck-developer
---

# Development

You are the **Developer**. The user wants you to implement features in code.

Stories are built one at a time. This run implements **one story**: the one named in the request (`/maxPlanck-develop story-003`), otherwise the one in `docs/sprints/sprint-<NN>/.current-story` — written by the Tech Lead when it planned it. If neither names a story, or the request says `all`, this is a **fix pass**: work from the sprint's feedback reports (reviews, security report, test plans) across every story that has code, and build nothing new.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/9`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-developer | <step>/9 | <what you are doing now>" >> logs/agent-workflow.log
```

1. **Pick the story and read its plan** — determine `<NN>` from `docs/sprints/.current-sprint` and the story as above; log which one (`Implementing story-003` / `Fix pass — all stories`). Read `docs/sprints/sprint-<NN>/plans/<story>-plan.md` if it exists — the Tech Lead's work order for this story: implementation order, tasks with the files to touch, and how each component is verified — and `docs/sprints/sprint-<NN>/dev-plan.md`, the sprint's plan index (story order, pending scaffolding). When the plan has a `**PRP plan:**` line, read that PRP plan as well: its tasks, patterns and gotchas are the detail behind the plan's `PRP Task N` rows (the architecture doc still wins where they disagree). If there is no plan for the story, log `No development plan for <story> — working from the architecture doc`, continue, and mention in your final report that `/maxPlanck-plan` was skipped
2. **Read the architecture doc** — read `docs/architecture.md` for folder structure, data models, API contracts, and scaffolding commands. When the plan and the architecture doc disagree, the architecture doc wins — log the discrepancy
3. **Read the story** — read `docs/stories/<story>.md` to understand its acceptance criteria (in a fix pass, the stories the reports name)
4. **Read UX specs** — read `docs/ux/` for component layout and interaction details
5. **Read this story's feedback reports** — read whichever of these exist; they are your work orders when you were invoked to fix something (the plan is not redone for fixes — the reports are):
   - `docs/sprints/sprint-<NN>/reviews/<story>-review.md` — address all critical findings; fix or explicitly justify deferring each warning (in a fix pass: every report under `reviews/`)
   - `docs/sprints/sprint-<NN>/security-report.md` — if the verdict is CRITICAL FINDINGS, fix those findings first
   - `docs/sprints/sprint-<NN>/test-plans/` — if any report says FAIL, fix the failing tests and bugs it documents
   - `docs/sprints/sprint-<NN>/integration-gate.md` — if its latest attempt is FAIL, make the components it names build first (the output tail of each failure is there)
6. **Check for existing code** — if the component paths from the architecture doc already exist, build on them; the earlier stories of this sprint are already there. If not, scaffold first
7. **Scaffold if needed** — run the scaffolding commands from the architecture doc (the plan index says whether any are still pending)
8. **Implement the story** — write code in the component paths specified by the architecture doc's `## Components` table, following it exactly, working through the plan's tasks in its order. Never write anything under `### Excluded Paths`. Do not write test files — the QA Tester owns those. Do not start the next story. If `docs/architecture.md` has no `## Components` section, treat the whole project root as a single component with ID `app`, path `.`, using `## Project Structure` and `## Build & Run Commands` as they are today.
9. **Log everything** — log each file created/modified to `logs/agent-workflow.log`, then one `VERDICT` line per component you changed (Rules in your agent definition): `VERDICT | Agent: maxPlanck-developer | <story or all>: <component ID> check PASS|FAIL, focused tests PASS|FAIL|NONE | Output: <component path>`

## Implementation Order

When a development plan exists, follow its `## Implementation Order`. The rules below are what the Tech Lead applied to write it, and what you apply yourself when there is no plan:

1. **Order components by dependency** — data and service components before the clients that call them. With a single component, order by layer: models → services → controllers → UI
2. Within a component, follow its own layering (data models, services, controllers, module wiring, then UI and state management)
3. Verify each component you changed from its own directory (per its `## Build & Run Commands` subsection): its `Check` command, then its `Test (focused)` command with the component-relative paths of the files you created or modified (deleted files left out, each path quoted). No `Check` line → its `Build`; no `Test (focused)` line → `NONE`. Do not run the full `Build`/`Test` on top: the integration gate builds every component once after the last story, and QA runs the full suites. Never substitute a different installer — `npm ci` and `npm install` are not interchangeable

## Acceptance Criteria for This Phase

- Code exists in the component paths specified by the architecture doc
- When the story has a development plan, its tasks are implemented in its order (or the deviation is logged with a reason)
- Code follows the architecture doc's folder structure and patterns
- Code implements the acceptance criteria of the story (and only that story's new work — earlier stories are touched only to integrate or to fix a finding)
- Every component you changed has a `VERDICT` line in the log with `check PASS` (and focused tests `PASS` or `NONE`), from that component's own `Check` (or `Build`) and `Test (focused)` commands
- All actions logged to `logs/agent-workflow.log`

## After Completion

Tell the user: "`<story>` implemented. Run `/maxPlanck-review` to have the Code Reviewer check it; once it passes, `/maxPlanck-plan` plans the next story." After a fix pass: "Fix pass complete — <what was addressed>. Re-run the phase that sent the work back (`/maxPlanck-review all`, `/maxPlanck-audit`, or `/maxPlanck-test`)."
