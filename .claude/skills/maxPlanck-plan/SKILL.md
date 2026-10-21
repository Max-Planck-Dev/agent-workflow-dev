---
name: maxPlanck-plan
description: Run implementation planning — the Tech Lead plans one story at a time from the approved architecture, writing the development plan the Developer follows for that story.
user-invocable: true
context: fork
agent: maxPlanck-tech-lead
---

<!-- Skill is phase-named (plan) while the agent keeps its role name
     (maxPlanck-tech-lead) — skill and agent names must not collide. -->

# Implementation Planning

You are the **Tech Lead**. The user wants a development plan written before the Developer starts building: tasks, files to touch, and how each piece is verified — for **one story**.

Stories are built one at a time: plan → plan review → develop → code review, then the next story. This phase runs after the design review and before each story's development. It is not used during adoption (`/maxPlanck-adopt`), where nothing is about to be built.

The request may name the story (`/maxPlanck-plan story-003`). Without one, you pick it as the Which Story section of your agent definition says: the current story if its plan review left proposals open, otherwise the next story in the sprint's story order without a plan.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/6`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-tech-lead | <step>/6 | <what you are doing now>" >> logs/agent-workflow.log
```

1. **Read the design** — read `docs/architecture.md` (Components table, data models, API contracts, folder structure, scaffolding and build commands) and, if it exists, `docs/sprints/sprint-<NN>/design-review.md` (determine `<NN>` from `docs/sprints/.current-sprint`, creating it with `01` if missing). If the review's verdict is CHANGES PROPOSED with proposals still open, say so in the plan's Risks section — the Architect has not ruled on them yet
2. **Read the stories and UX specs** — read `docs/stories/` for acceptance criteria and priorities, and `docs/ux/` for the specs that apply. If the story you will plan has a `**PRP plan:**` line, read that PRP plan too (PRP Plan in your agent definition)
3. **Write or read the plan index** — if `docs/sprints/sprint-<NN>/dev-plan.md` does not exist, decide which stories are in scope this sprint and in what order (P0/P1 first, then by dependency; the sprint focus from the conversation, if any, wins) and write it in the Plan Index Format from your agent definition. If it exists, read it: the order is already decided. Then pick the story (Which Story in your agent definition) and record it: `printf '<story>\n' > docs/sprints/sprint-<NN>/.current-story`
4. **Read the existing code and this story's feedback** — look at the in-scope component paths from the `## Components` table (never anything under `### Excluded Paths`): the earlier stories of this sprint are already built, so tasks say *modify* where they should. If `docs/architecture.md` has no `## Components` section, treat the whole project root as a single component with ID `app`, path `.`. Then read `docs/sprints/sprint-<NN>/plan-reviews/<story>-plan-review.md` if it exists: every proposal in it with no row in the plan's `## Plan Review Log` is open and is your work order (see Plan Review Proposals in your agent definition)
5. **Write the story's plan** — `docs/sprints/sprint-<NN>/plans/<story>-plan.md`, in the Story Plan Format from your agent definition: implementation order by component dependency, every acceptance criterion mapped to a task, contracts and UX to honour, per-component verification commands, risks and open questions. When the story names a PRP plan, `## Tasks` maps the acceptance criteria onto the PRP's tasks (`PRP Task N — <name>` plus its files) instead of transcribing them, and the header carries the `**PRP plan:**` line. If the plan already exists, revise it in place and keep its `## Plan Review Log`; for each open proposal decide ACCEPTED, PARTIAL, or REJECTED, apply what you accept, and append one row per proposal to that log
6. **Log everything** — log the story order when you wrote the index (as a `DECISION`), the story you planned, one `DECISION` line per plan review proposal, and the plan path to `logs/agent-workflow.log`

## Acceptance Criteria for This Phase

- `docs/sprints/sprint-<NN>/dev-plan.md` exists with a `## Story Order` listing every story in scope
- `docs/sprints/sprint-<NN>/.current-story` holds the story you planned, and nothing else
- `docs/sprints/sprint-<NN>/plans/<story>-plan.md` exists with an `## Implementation Order` and a `## Tasks` table
- Every acceptance criterion of the story appears in a task's `Covers AC` column
- Every task names the file(s) it creates or modifies
- When the story names a PRP plan: the plan header carries its `**PRP plan:**` line, `## Tasks` references its tasks by number instead of copying them, and only acceptance criteria the PRP does not cover get tasks of their own
- The plan has a `**Verification:**` line with each touched component's own `Check` and `Test (focused)` commands (`Build` when it has no `Check` line)
- The plan follows `docs/architecture.md` — no models, endpoints, or paths that are not in it
- If this story has a plan review report, every proposal in it has a row in the plan's `## Plan Review Log` — none left open
- No other story's plan was written or changed; no source code, tests, or other docs were written or modified
- All actions logged to `logs/agent-workflow.log`

## After Completion

Tell the user: "Development plan for `<story>` written to `docs/sprints/sprint-<NN>/plans/<story>-plan.md` (<m> tasks; story <k> of <n> in this sprint's order). Run `/maxPlanck-plan-review` to have it reviewed before development (by OpenAI Codex when installed, otherwise by Claude), or `/maxPlanck-develop` to start building it." If the plan lists open questions for the Architect, say so and suggest `/maxPlanck-design` first.

If you were responding to a plan review, say instead: "Plan review proposals for `<story>` evaluated — <A> accepted, <P> partial, <R> rejected. Re-run `/maxPlanck-plan-review` only if its last round printed `RECHECK=yes` (it had a CRITICAL or HIGH proposal); otherwise run `/maxPlanck-develop` to start building."

If every story in the index already has a plan, say so and name the stories: "All <n> stories of sprint <NN> are planned. Run `/maxPlanck-plan story-NNN` to revise one."
