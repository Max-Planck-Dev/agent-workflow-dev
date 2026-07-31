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

1. **Resolve the sprint** — determine `<NN>` from `docs/sprints/.current-sprint` (create with `01` if missing); all phase checks below refer to THIS sprint's artifacts, not prior sprints'
2. **Check all artifacts** — scan `docs/`, source directories per `docs/architecture.md`, and `logs/` to assess project state
3. **Review the log** — read the current sprint's slice of `logs/agent-workflow.log` (from the latest pipeline-start or this sprint's first entry), not the whole file
4. **Validate phases** — check each phase's Definition of Done
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
| Develop | Code exists | Source directories per `docs/architecture.md` have source files |
| Review | Review reports | `docs/sprints/sprint-NN/reviews/` has reports, no unresolved criticals |
| Security | Security report | `docs/sprints/sprint-NN/security-report.md` exists, no CRITICAL FINDINGS |
| DevOps | Infra + CI/CD + deployment doc | `infra/` has Terraform files, `.github/workflows/deploy.yml` exists, `docs/devops/deployment.md` has ISR compliance mapping covering this sprint's ISRs |
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
