---
name: maxPlanck-plan
description: Run implementation planning — the Tech Lead turns the approved architecture and the sprint's stories into a development plan the Developer follows.
user-invocable: true
context: fork
agent: maxPlanck-tech-lead
---

<!-- Skill is phase-named (plan) while the agent keeps its role name
     (maxPlanck-tech-lead) — skill and agent names must not collide. -->

# Implementation Planning

You are the **Tech Lead**. The user wants a development plan written before the Developer starts building: implementation order, tasks per story, files to touch, and how each piece is verified.

This phase runs after the design review and before development. It is not used during adoption (`/maxPlanck-adopt`), where nothing is about to be built.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/6`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-tech-lead | <step>/6 | <what you are doing now>" >> logs/agent-workflow.log
```

1. **Read the design** — read `docs/architecture.md` (Components table, data models, API contracts, folder structure, scaffolding and build commands) and, if it exists, `docs/sprints/sprint-<NN>/design-review.md` (determine `<NN>` from `docs/sprints/.current-sprint`, creating it with `01` if missing). If the review's verdict is CHANGES PROPOSED with proposals still open, say so in the plan's Risks section — the Architect has not ruled on them yet
2. **Read the stories and UX specs** — read `docs/stories/` for acceptance criteria and priorities, and `docs/ux/` for the specs that apply. Decide which stories are in scope this sprint (P0/P1 first; the sprint focus from the conversation, if any, wins)
3. **Read the existing code** — look at the in-scope component paths from the `## Components` table; never read anything under `### Excluded Paths`. Note what already exists so tasks say *modify* where they should. If `docs/architecture.md` has no `## Components` section, treat the whole project root as a single component with ID `app`, path `.`
4. **Read this sprint's plan review and feedback reports**, if any exist — `docs/sprints/sprint-<NN>/plan-review.md`: every proposal in it with no row in the `## Plan Review Log` of the plan is open and is your work order when you were invoked to respond to a plan review (see Plan Review Proposals in your agent definition). Also `docs/sprints/sprint-<NN>/reviews/`, `security-report.md`, `test-plans/`: when you were invoked after a failed verdict, addressing those findings is part of the plan
5. **Write the plan** — `docs/sprints/sprint-<NN>/dev-plan.md`, in the Development Plan Format from your agent definition: implementation order by component dependency, one section per in-scope story with every acceptance criterion mapped to a task, contracts and UX to honour, per-component verification commands, scaffolding still needed, risks and open questions, out of scope. If the plan already exists this sprint, revise it in place and keep its `## Plan Review Log`; for each open proposal decide ACCEPTED, PARTIAL, or REJECTED, apply what you accept, and append one row per proposal to that log
6. **Log everything** — log the stories in scope, the implementation order (as a `DECISION`), one `DECISION` line per plan review proposal, and the plan path to `logs/agent-workflow.log`

## Acceptance Criteria for This Phase

- `docs/sprints/sprint-<NN>/dev-plan.md` exists with an `## Implementation Order` section and a `## story-NNN` section for every story in scope
- Every acceptance criterion of every in-scope story appears in a task's `Covers AC` column
- Every task names the file(s) it creates or modifies
- Every story section has a `**Verification:**` line with that component's own build/test commands
- The plan follows `docs/architecture.md` — no models, endpoints, or paths that are not in it
- If this sprint has a plan review report, every proposal in it has a row in the plan's `## Plan Review Log` — none left open
- No source code, tests, or other docs were written or modified
- All actions logged to `logs/agent-workflow.log`

## After Completion

Tell the user: "Development plan written to `docs/sprints/sprint-<NN>/dev-plan.md` (<n> stories, <m> tasks). Run `/maxPlanck-plan-review` to have it reviewed before development (by OpenAI Codex when installed, otherwise by Claude), or `/maxPlanck-develop` to start building." If the plan lists open questions for the Architect, say so and suggest `/maxPlanck-design` first.

If you were responding to a plan review, say instead: "Plan review proposals evaluated — <A> accepted, <P> partial, <R> rejected. Re-run `/maxPlanck-plan-review` to confirm, or `/maxPlanck-develop` to start building."
