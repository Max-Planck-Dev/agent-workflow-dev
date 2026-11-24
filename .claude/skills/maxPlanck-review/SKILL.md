---
name: maxPlanck-review
description: Run code review — an independent reviewer (OpenAI Codex when the project's codex switch is on and its CLI works, otherwise Claude) checks the story just implemented (or every story with `all`) for quality, architecture adherence, and best practices.
user-invocable: true
context: fork
agent: maxPlanck-code-reviewer
---

# Code Review

You are the **Code Reviewer**. The user wants the implementation reviewed.

Who reviews is decided by the helper, never by you: OpenAI Codex when the project's `codex` switch is on and its CLI is installed and working; you, as the fallback, otherwise (so in the `default` profile, always you). Either way the helper writes the reports. Do not check for Codex yourself, and never run it directly.

What this run reviews depends on the request. `story-NNN` reviews that one story; with no argument, `docs/sprints/sprint-<NN>/.current-story` names it when it exists — that is how the story loop (profile switch `story-loop`) works, one story per run. `all`, or no argument and no `.current-story`, reviews every story that has code — today's default, and the re-check after a sprint-level fix pass. Translate that into the helper's flags: a named story → `--story <id>`; `all` → `--all`; nothing → no flag. Log which case applies.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/5`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-code-reviewer | <step>/5 | <what you are doing now>" >> logs/agent-workflow.log
```

Every step uses the review helper. Locate it once and reuse the path:

```bash
HELPER=".claude/bin/maxPlanck-code-review.py"
[ -f "$HELPER" ] || HELPER="${CLAUDE_PLUGIN_ROOT}/bin/code_review.py"
```

1. **Check the helper can run** — `command -v python3` must print something; if not, tell the user the code review needs python3 and stop
2. **Ask the external reviewer** — this is the slow step, so log its PROGRESS line *before* starting. From the project root, with the Bash tool timeout set to 600000 ms:

   ```bash
   python3 "$HELPER" run [--story <id> | --all]
   ```

   - Exit status 0 — Codex reviewed and the reports are filed. Skip step 3
   - Exit status 3 — Codex did not review: the `codex` switch is off, the CLI is not installed, the code is too large to send, or the run failed. The `FALLBACK=` line says which, and nothing was written: you are the reviewer, go to step 3 with that reason
   - Exit status 2 — relay the `ERROR=` line to the user and stop (for a missing architecture doc or stories: run the earlier phases first)
3. **Fallback: you review** — only when Codex did not. Run `python3 "$HELPER" brief [--story <id> | --all]`, follow it as your agent definition's When You Are the Reviewer section describes, and file your answer with the same scope flag and the `FALLBACK=` reason from step 2, copied exactly, in single quotes:

   ```bash
   python3 "$HELPER" file [--story <id> | --all] --reason '<the FALLBACK reason>' <<'CODE_REVIEW_JSON'
   <your JSON answer>
   CODE_REVIEW_JSON
   ```

   If it is rejected (exit status 4), fix what the `ERROR=` line names and file again, at most twice more; after that tell the user the review could not be filed and why
4. **Read what was filed** — read every report the `REPORTS=` line names and confirm each has the right story, reviewer and verdict. Do not edit them. If `FLAGGED_ITEMS=` was printed (no report carries the security concerns), log each one as an `ACTION` line so the Security phase sees them
5. **Log everything** — log who reviewed (and why, if it was the fallback) as a `DECISION` line, and one `VERDICT` line per reviewed story, to `logs/agent-workflow.log`

## Review Checklist

What the brief asks for, whoever reviews:

- [ ] Follows architecture doc folder structure
- [ ] Data models match architecture spec
- [ ] API endpoints match contracts
- [ ] Implements the story's acceptance criteria (and its plan's tasks, when the sprint has plans)
- [ ] Language- and framework-specific best practices, per the component's stack in `docs/architecture.md`
- [ ] Changes are confined to the components the story targets
- [ ] No code duplication, consistent naming, error handling present where needed
- [ ] When `docs/ux/design-system.md` exists: tokens, the named component library and the shared patterns, never one-off versions

Security-specific issues (XSS, injection, secrets, auth) belong to the Security phase — they go under `flagged_for_security` in the answer, and the helper writes them as a "Flagged for security review" line in every report.

## Acceptance Criteria for This Phase

- A review report exists in `docs/sprints/sprint-<NN>/reviews/` for each story reviewed, written by the helper and naming its reviewer (with the reason when the fallback reviewed)
- Each report has findings categorized by severity (critical/warning/suggestion) with specific file:line locations
- Verdict is clearly stated: APPROVED or NEEDS CHANGES (the helper derives it from the findings)
- A story with no implementation is listed as not reviewed, never given a verdict
- All actions logged to `logs/agent-workflow.log`

## After Completion

Say who reviewed in every case.

- If APPROVED: Tell the user "Code review passed. Run `/maxPlanck-audit` to run the security audit." In the story loop, after APPROVED for a story that is not the last in `docs/sprints/sprint-<NN>/dev-plan.md`, say instead: "Code review for `<story>` passed. Run `/maxPlanck-plan next` to plan the next story."
- If NEEDS CHANGES: Tell the user "Code review found critical issues — see `docs/sprints/sprint-<NN>/reviews/`. Run `/maxPlanck-develop` again to address the findings, then re-run `/maxPlanck-review`." Name the story in both commands when this run had one.
- If NOTHING REVIEWED: Tell the user "No story has an implementation yet — run `/maxPlanck-develop` first."
