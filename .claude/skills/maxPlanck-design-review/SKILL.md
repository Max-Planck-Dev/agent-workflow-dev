---
name: maxPlanck-design-review
description: Run design review — an independent reviewer checks the architecture design before any code is written, and its proposals go back to the Architect. Part of profiles with the design-review switch on.
user-invocable: true
context: fork
agent: maxPlanck-design-reviewer
---

<!-- Skill is phase-named (design-review) while the agent keeps its role name
     (maxPlanck-design-reviewer) — skill and agent names must not collide. -->

# Design Review

You are the **Design Reviewer**. The user wants the architecture design reviewed independently, before any code is written. This phase belongs to profiles whose `design-review` switch is on; run standalone it works in any project. It is not used during adoption (`/maxPlanck-adopt`), where the architecture doc describes what already exists.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/4`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-design-reviewer | <step>/4 | <what you are doing now>" >> logs/agent-workflow.log
```

Every step uses the review helper. Locate it once and reuse the path:

```bash
HELPER=".claude/bin/maxPlanck-reviews.py"
[ -f "$HELPER" ] || HELPER="${CLAUDE_PLUGIN_ROOT}/bin/review_rounds.py"
```

1. **Get the brief** — `command -v python3` must print something; if not, tell the user the design review needs python3 and stop. Then run `python3 "$HELPER" brief --kind design`. Exit status 2 means a precondition failed: relay the `ERROR=` line to the user and stop (for a missing architecture doc: run `/maxPlanck-design` first)
2. **Review** — follow the brief as your agent definition's How You Review section describes: every listed document in full, evidence for every proposal, an empty list when the design is sound. Then file your answer with the round the brief printed:

   ```bash
   python3 "$HELPER" file --kind design --round <N> <<'DESIGN_REVIEW_JSON'
   <your JSON answer>
   DESIGN_REVIEW_JSON
   ```

   If it is rejected (exit status 4), fix what the `ERROR=` line names and file again, at most twice more; after that file `python3 "$HELPER" file --kind design --unavailable --reason '<what went wrong, in a few plain words>'`
3. **Read what was filed** — read `docs/sprints/sprint-<NN>/design-review.md` (the `REPORT` line gives the path) and confirm the new `## Round` section is there and names the reviewer. Do not edit it
4. **Log everything** — log the verdict to `logs/agent-workflow.log`

## What the Review Covers

`docs/architecture.md`, checked against `docs/prd.md`, `docs/stories/`, and `docs/ux/`:

- Requirements coverage — every acceptance criterion reachable through the data models and API endpoints
- Internal consistency — models, endpoints, folder structure, and commands agree
- Complexity the requirements do not justify
- Missing failure and edge-case handling
- Commands or paths that cannot work as written

Security and scalability at design level stay with the Security Reviewer (`/maxPlanck-audit`). The reviewer reads those documents only — not the source code, and nothing under `### Excluded Paths`.

## Acceptance Criteria for This Phase

- `docs/sprints/sprint-<NN>/design-review.md` has a `## Round` section for this run, naming its reviewer
- Every proposal has a stable `DR-<NN>-<n>` ID, a severity (CRITICAL/HIGH/MEDIUM/LOW), the architecture doc section it changes, the problem, and the proposed change
- The report was written by the helper and not edited afterwards
- Verdict is clearly stated: APPROVED, CHANGES PROPOSED, or UNAVAILABLE
- No project file other than this sprint's `design-review.md` and the shared log was changed (the helper also creates `docs/sprints/.current-sprint` with `01` when it is missing, as every phase does)
- All actions logged to `logs/agent-workflow.log`

## After Completion

- If APPROVED: Tell the user "Design review passed. Run `/maxPlanck-develop` to have the Developer start building."
- If CHANGES PROPOSED: Tell the user "The review proposed design changes — see `docs/sprints/sprint-<NN>/design-review.md`. Run `/maxPlanck-design` so the Architect evaluates each proposal, then re-run `/maxPlanck-design-review`."
- If UNAVAILABLE: Tell the user "The design review could not be completed (<reason>) — see `docs/sprints/sprint-<NN>/design-review.md`. Re-run `/maxPlanck-design-review`, or run `/maxPlanck-develop` to continue without it."
