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

Run these phases in order, logging a `PIPELINE` transition line between each:

1. **Product Owner** (`maxPlanck-kickoff` context — invoke the skill with the change description): update the affected artifacts, not just the code intent:
   - If the change modifies an existing story → edit that story AND append a `## History` entry (what changed, when, why)
   - If it is new scope → create a new story (numbering continues)
   - If it affects product scope/vision → update `docs/prd.md` in place + Change Log entry
2. **Architect** (`maxPlanck-design`) — **only if the change is structural** (new data model, new endpoint, changed folder structure, new dependency). Skip for pure behavior/copy/style fixes. When run, it updates `docs/architecture.md` in place + Change Log entry.
3. **Developer** (`maxPlanck-develop`) — implement the change per the updated docs.
4. **Code Reviewer** (`maxPlanck-review`) — review the changed code; report to `docs/sprints/sprint-<NN>/reviews/`. If NEEDS CHANGES → back to step 3 (max 2 retries, then record unresolved).
5. **QA Tester** (`maxPlanck-test`) — test the affected stories; report to `docs/sprints/sprint-<NN>/test-plans/`. If FAIL → back to step 3 (max 2 retries, then record unresolved).
6. **Scrum Master** (`maxPlanck-sprint`) — update the sprint summary and story statuses so the sprint record reflects the change.

Security note: if the change touches auth, input handling, secrets, dependencies, or infrastructure, insert `maxPlanck-audit` between steps 4 and 5. Otherwise skip it.

## After Completion

Report honestly:

- What changed (stories touched, docs updated, files modified)
- Verdicts from review and test
- Anything unresolved after retries — with the file documenting it and the suggested next command

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PIPELINE | Agent: orchestrator | Change request complete (sprint <NN>) | Unresolved: <N>" >> logs/agent-workflow.log
```
