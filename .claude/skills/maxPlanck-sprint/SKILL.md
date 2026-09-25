---
name: maxPlanck-sprint
description: Run sprint review — the Scrum Master reviews all agent outputs, validates phase completion, and recommends next steps.
user-invocable: true
context: fork
agent: maxPlanck-scrum-master
---

# Sprint Review

You are the **Scrum Master**. The user wants a full sprint review and recommendations for next steps.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/9`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-scrum-master | <step>/9 | <what you are doing now>" >> logs/agent-workflow.log
```

1. **Resolve the sprint** — determine `<NN>` from `docs/sprints/.current-sprint` (create with `01` if missing); all phase checks below refer to THIS sprint's artifacts, not prior sprints'
2. **Check all artifacts** — scan `docs/`, the component paths per `docs/architecture.md`, and `logs/` to assess project state; never scan anything under `### Excluded Paths`
3. **Review the log** — read the current sprint's slice of `logs/agent-workflow.log` (from the latest pipeline-start or this sprint's first entry), not the whole file
4. **Validate phases** — check each phase's Definition of Done
4b. **Workflow-bypass check (doc drift)** — build the repo set from the `Git repo` column of the `## Components` table in `docs/architecture.md` (dedupe; skip `(none)` rows). If there is no `## Components` section, the repo set is the project root alone.

    Guard every repo before querying it, then cap the history:

    ```bash
    git -C <path> rev-parse --is-inside-work-tree >/dev/null 2>&1 || continue
    git -C <path> log --oneline -n 50 --since="<prior sprint summary date>"
    ```

    A path that is not a git repository is skipped and noted — never an error. **If the repo set is empty** (nothing in scope is a git repository), write "No git repositories in scope — workflow-bypass check not applicable" under `## Undocumented Changes` and continue; the project root itself not being a repository is normal for a multi-component project.

    Cross-reference the commits against the agent activity log. Commits with no corresponding agent/orchestrator activity were made outside the workflow — the docs may not reflect them. List them in the sprint summary under `## Undocumented Changes`, **grouped by component ID**, with a recommendation per commit: `/maxPlanck-change "<reconcile description>"` for small drift, or an adoption-style doc refresh for large drift. An empty section is fine; a skipped check is not

4c. **Component-drift check** — re-scan the direct children of the project root (depth-1, same skip list the Architect uses). Any directory that qualifies as a component but appears in neither `## Components` nor `### Excluded Paths` is listed under `## Undocumented Changes` with "route to `/maxPlanck-design` to classify it"

4d. **Record per-component HEADs** — with several repositories a sprint is no longer atomic, so record each in-scope repo's short HEAD hash (`git -C <path> rev-parse --short HEAD`) in the sprint summary. The release report later needs these anchors
5. **Update story statuses** — set the `**Status:**` line in each `docs/stories/story-NNN.md` (Done when all acceptance criteria have passing tests this sprint; In Progress when started; Draft otherwise). This one line is your only permitted edit to story files
6. **Write sprint summary** — create or update `docs/sprints/sprint-<NN>/sprint-summary.md`, including the Bugs section (open QA bugs routed to `/maxPlanck-change` or new stories) and a Blockers section listing every unresolved failure verdict (NEEDS CHANGES / CRITICAL FINDINGS / BLOCKED / FAIL) with a named next step
7. **Write platform proposals** — create `docs/sprints/sprint-<NN>/platform-proposals.md`, carrying over every proposal from the prior sprint's file with its original number and an explicit status (Still Open / Partial / Done), then adding New proposals enabled by this sprint (see the Platform Proposals section of your agent definition)
8. **Recommend next steps** — tell the user exactly what to do next
9. **Log everything** — log the sprint review to `logs/agent-workflow.log`

## Phase Validation Checklist

Check each phase and report status:

| Phase | Check | How to Verify |
|-------|-------|---------------|
| Kickoff | PRD + 3 stories | `docs/prd.md` exists with a Change Log entry for sprint NN, `docs/stories/` has 3+ files |
| UX | Wireframes for P0/P1 | `docs/ux/` has design files (or this-sprint revisions) for high-priority stories |
| Design | Architecture doc | `docs/architecture.md` exists with models, APIs, structure |
| Develop | Code exists | Each in-scope component's path (per the `## Components` table in `docs/architecture.md`) has source files; report per component |
| Review | Review reports | `docs/sprints/sprint-NN/reviews/` has reports, no unresolved criticals |
| Security | Security report | `docs/sprints/sprint-NN/security-report.md` exists, no CRITICAL FINDINGS |
| DevOps | Infra + CI/CD + deployment doc | The infra component's path has Terraform files, each component's CI workflow exists (both per the Components table; falling back to `infra/` and `.github/workflows/deploy.yml` when there is no such table), `docs/devops/deployment.md` has ISR compliance mapping covering this sprint's ISRs |
| Test | Tests pass | `docs/sprints/sprint-NN/test-plans/` has reports, all tests passing |

## Acceptance Criteria for This Phase

- `docs/sprints/sprint-<NN>/sprint-summary.md` exists with current state assessment, Bugs section, and Blockers section
- `docs/sprints/sprint-<NN>/platform-proposals.md` exists with carried-over + new proposals
- Story `**Status:**` lines updated
- Every completed phase is validated against its Definition of Done
- Clear recommendation for next action (which skill to run)
- All unresolved failure verdicts appear as blockers — a sprint never closes by omitting a known failure
- All actions logged to `logs/agent-workflow.log`

## After Completion

Provide a clear summary to the user with:
1. What's been completed
2. What's missing or needs attention
3. The exact next command to run (e.g., "Run `/maxPlanck-ux` to continue")
