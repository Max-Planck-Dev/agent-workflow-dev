---
name: maxPlanck-plan-review
description: Run plan review — a second reviewer (OpenAI Codex when its CLI is installed, otherwise Claude) checks the development plan, and its proposals go back to the Tech Lead.
user-invocable: true
context: fork
agent: maxPlanck-plan-reviewer
---

<!-- Skill is phase-named (plan-review) while the agent keeps its role name
     (maxPlanck-plan-reviewer) — skill and agent names must not collide. -->

# Plan Review

You are the **Plan Reviewer**. The user wants the development plan reviewed independently, before the Developer builds from it.

OpenAI Codex does the review when its CLI is installed and working; otherwise you do it yourself, as the fallback reviewer. This phase is not used during adoption (`/maxPlanck-adopt`), where nothing is about to be built.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/5`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-plan-reviewer | <step>/5 | <what you are doing now>" >> logs/agent-workflow.log
```

Every step uses the review helper that ships with this skill. Locate it once and reuse the path:

```bash
HELPER="${CLAUDE_SKILL_DIR}/plan_review.py"
[ -f "$HELPER" ] || HELPER=".claude/skills/maxPlanck-plan-review/plan_review.py"
```

1. **Check the helper can run** — `command -v python3`. If it prints nothing, tell the user the plan review needs python3 and stop. Do not check for Codex yourself: the helper decides who reviews
2. **Ask Codex** — this is the slow step, so log its PROGRESS line *before* starting. From the project root, with the Bash tool timeout set to 600000 ms:

   ```bash
   python3 "$HELPER" run --skip-if-exists .claude/maxPlanck-no-codex
   ```

   (`.claude/maxPlanck-no-codex` is how a project says its docs must not be sent to OpenAI: when that file exists the helper does not call Codex.)

   - Exit status 0 — Codex reviewed and the round is filed. Skip step 3
   - Exit status 3 — Codex did not review: it is not installed, it is turned off for this project, or the run failed. The `FALLBACK=` line says which, and nothing was written: you are the reviewer, go to step 3 with that reason
   - Exit status 2 — relay the `ERROR=` line to the user and stop (for a missing plan: run `/maxPlanck-plan` first)
3. **Fallback: you review** — only when Codex did not. Run `python3 "$HELPER" brief`, follow it as your agent definition's When You Are the Reviewer section describes, and file your answer with the round `brief` printed and the `FALLBACK=` reason from step 2, copied exactly, in single quotes:

   ```bash
   python3 "$HELPER" file --round <N> --reason '<the FALLBACK reason>' <<'PLAN_REVIEW_JSON'
   <your JSON answer>
   PLAN_REVIEW_JSON
   ```

   If it is rejected (exit status 4), fix what the `ERROR=` line names and file again, at most twice more; after that file `python3 "$HELPER" file --unavailable --reason '<what went wrong, in a few plain words>'`
4. **Read what was filed** — read `docs/sprints/sprint-<NN>/plan-review.md` (the `REPORT` line gives the path) and confirm the new `## Round` section is there and names the right reviewer. Do not edit it
5. **Log everything** — log who reviewed (and why, if it was the fallback) and the verdict to `logs/agent-workflow.log`

## What the Review Covers

`docs/sprints/sprint-<NN>/dev-plan.md`, checked against `docs/architecture.md`, `docs/prd.md`, `docs/stories/`, `docs/ux/`, and the inventory of source files that exist today:

- Coverage — every acceptance criterion of every in-scope story maps to a task
- Fidelity to the design — only the models, endpoints, paths, stacks and commands the architecture doc defines
- Order — components and layers in dependency order, each task verifiable when done
- Concreteness — files named with a verb; "modify" tasks name files that exist, "create" tasks follow the folder structure
- Verification — the right build/test commands per component, run from its directory
- Risk — missing edge cases, hidden work, open questions the Architect should hear

The reviewer reads the plan, the docs and the file inventory; of the source code, only the files a task names, and nothing under `### Excluded Paths`.

## Acceptance Criteria for This Phase

- `docs/sprints/sprint-<NN>/plan-review.md` has a `## Round` section for this run, naming its reviewer
- When the fallback reviewed, the reviewer line says why Codex did not
- Every proposal has a stable `PR-<NN>-<n>` ID, a severity (CRITICAL/HIGH/MEDIUM/LOW), the plan section it changes, the problem, and the proposed change
- The report was written by the helper and not edited afterwards
- Verdict is clearly stated: APPROVED, CHANGES PROPOSED, or UNAVAILABLE
- No project file other than this sprint's `plan-review.md` and the shared log was changed (the helper also creates `docs/sprints/.current-sprint` with `01` when it is missing, as every phase does)
- All actions logged to `logs/agent-workflow.log`

## After Completion

Say who reviewed in every case (e.g. "reviewed by OpenAI Codex" / "reviewed by Claude — Codex CLI not installed").

- If APPROVED: Tell the user "Plan review passed. Run `/maxPlanck-develop` to have the Developer start building."
- If CHANGES PROPOSED: Tell the user "The review proposed changes to the plan — see `docs/sprints/sprint-<NN>/plan-review.md`. Run `/maxPlanck-plan` so the Tech Lead evaluates each proposal, then re-run `/maxPlanck-plan-review`."
- If UNAVAILABLE: Tell the user "The plan review could not be completed (<reason>) — see `docs/sprints/sprint-<NN>/plan-review.md`. Re-run `/maxPlanck-plan-review`, or run `/maxPlanck-develop` to continue without it."
