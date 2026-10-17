---
name: maxPlanck-design-review
description: Run design review — a second reviewer (OpenAI Codex when its CLI is installed, otherwise Claude) checks the architecture design, and its proposals go back to the Architect.
user-invocable: true
context: fork
agent: maxPlanck-design-reviewer
---

<!-- Skill is phase-named (design-review) while the agent keeps its role name
     (maxPlanck-design-reviewer) — skill and agent names must not collide. -->

# Design Review

You are the **Design Reviewer**. The user wants the architecture design reviewed independently, before any code is written.

OpenAI Codex does the review when its CLI is installed and working; otherwise you do it yourself, as the fallback reviewer. This phase is not used during adoption (`/maxPlanck-adopt`), where the architecture doc describes what already exists.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/5`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-design-reviewer | <step>/5 | <what you are doing now>" >> logs/agent-workflow.log
```

Every step uses the review helper that ships with this skill. Locate it once and reuse the path:

```bash
HELPER="${CLAUDE_SKILL_DIR}/design_review.py"
[ -f "$HELPER" ] || HELPER=".claude/skills/maxPlanck-design-review/design_review.py"
```

1. **Check the helper can run** — `command -v python3`. If it prints nothing, tell the user the design review needs python3 and stop. Do not check for Codex yourself: the helper decides who reviews
2. **Ask Codex** — this is the slow step, so log its PROGRESS line *before* starting. From the project root, with the Bash tool timeout set to 600000 ms:

   ```bash
   python3 "$HELPER" run --skip-if-exists .claude/maxPlanck-no-codex
   ```

   (`.claude/maxPlanck-no-codex` is how a project says its docs must not be sent to OpenAI: when that file exists the helper does not call Codex.)

   - Exit status 0 — Codex reviewed and the round is filed. Skip step 3
   - Exit status 3 — Codex did not review: it is not installed, it is turned off for this project, or the run failed. The `FALLBACK=` line says which, and nothing was written: you are the reviewer, go to step 3 with that reason
   - Exit status 2 — relay the `ERROR=` line to the user and stop (for a missing architecture doc: run `/maxPlanck-design` first)
3. **Fallback: you review** — only when Codex did not. Run `python3 "$HELPER" brief`, follow it as your agent definition's When You Are the Reviewer section describes, and file your answer with the round `brief` printed and the `FALLBACK=` reason from step 2, copied exactly, in single quotes:

   ```bash
   python3 "$HELPER" file --round <N> --reason '<the FALLBACK reason>' <<'DESIGN_REVIEW_JSON'
   <your JSON answer>
   DESIGN_REVIEW_JSON
   ```

   If it is rejected (exit status 4), fix what the `ERROR=` line names and file again, at most twice more; after that file `python3 "$HELPER" file --unavailable --reason '<what went wrong, in a few plain words>'`
4. **Read what was filed** — read `docs/sprints/sprint-<NN>/design-review.md` (the `REPORT` line gives the path) and confirm the new `## Round` section is there and names the right reviewer. Do not edit it
5. **Log everything** — log who reviewed (and why, if it was the fallback) and the verdict to `logs/agent-workflow.log`

## What the Review Covers

`docs/architecture.md`, checked against `docs/prd.md`, `docs/stories/`, and `docs/ux/`:

- Requirements coverage — every acceptance criterion reachable through the data models and API endpoints
- Internal consistency — models, endpoints, folder structure, and commands agree
- Complexity the requirements do not justify
- Missing failure and edge-case handling
- Scalability and security risks visible at design level
- Commands or paths that cannot work as written

The reviewer reads those documents only — not the source code, and nothing under `### Excluded Paths`.

## Acceptance Criteria for This Phase

- `docs/sprints/sprint-<NN>/design-review.md` has a `## Round` section for this run, naming its reviewer
- When the fallback reviewed, the reviewer line says why Codex did not
- Every proposal has a stable `DR-<NN>-<n>` ID, a severity (CRITICAL/HIGH/MEDIUM/LOW), the architecture doc section it changes, the problem, and the proposed change
- The report was written by the helper and not edited afterwards
- Verdict is clearly stated: APPROVED, CHANGES PROPOSED, or UNAVAILABLE
- No project file other than this sprint's `design-review.md` and the shared log was changed (the helper also creates `docs/sprints/.current-sprint` with `01` when it is missing, as every phase does)
- All actions logged to `logs/agent-workflow.log`

## After Completion

Say who reviewed in every case (e.g. "reviewed by OpenAI Codex" / "reviewed by Claude — Codex CLI is not installed").

- If APPROVED: Tell the user "Design review passed. Run `/maxPlanck-plan` to have the Tech Lead write the development plan."
- If CHANGES PROPOSED: Tell the user "The review proposed design changes — see `docs/sprints/sprint-<NN>/design-review.md`. Run `/maxPlanck-design` so the Architect evaluates each proposal, then re-run `/maxPlanck-design-review`."
- If UNAVAILABLE: Tell the user "The design review could not be completed (<reason>) — see `docs/sprints/sprint-<NN>/design-review.md`. Re-run `/maxPlanck-design-review`, or run `/maxPlanck-plan` to continue without it."
