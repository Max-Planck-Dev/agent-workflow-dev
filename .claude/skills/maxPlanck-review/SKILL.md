---
name: maxPlanck-review
description: Run code review — a second reviewer (OpenAI Codex when its CLI is installed, otherwise Claude) checks the implementation for quality, architecture adherence, and best practices.
user-invocable: true
context: fork
agent: maxPlanck-code-reviewer
---

# Code Review

You are the **Code Reviewer**. The user wants the implementation reviewed.

OpenAI Codex does the review when its CLI is installed and working; otherwise you do it yourself, as the fallback reviewer. Either way the review helper writes the reports.

## Your Task

**Report progress as you go.** The pipeline dashboard shows how far along you are only from these lines. Right after reading your inputs log `0/5`, then after finishing each numbered step below log the step number. Each line is its own Bash call made the moment that step completes; a batch of PROGRESS lines written together at the end shows nothing while you work. Never write START or STOP lines yourself, the hooks own those:

```bash
echo "[$(date '+%Y-%m-%d %H:%M:%S')] PROGRESS | Agent: maxPlanck-code-reviewer | <step>/5 | <what you are doing now>" >> logs/agent-workflow.log
```

Every step uses the review helper that ships with this skill. Locate it once and reuse the path:

```bash
HELPER="${CLAUDE_SKILL_DIR}/code_review.py"
[ -f "$HELPER" ] || HELPER=".claude/skills/maxPlanck-review/code_review.py"
```

1. **Check the helper can run** — `command -v python3`. If it prints nothing, tell the user the code review needs python3 and stop. Do not check for Codex yourself: the helper decides who reviews
2. **Ask Codex** — this is the slow step, so log its PROGRESS line *before* starting. From the project root, with the Bash tool timeout set to 600000 ms:

   ```bash
   python3 "$HELPER" run --skip-if-exists .claude/maxPlanck-no-codex
   ```

   (`.claude/maxPlanck-no-codex` is how a project says its code and docs must not be sent to OpenAI: when that file exists the helper does not call Codex.)

   - Exit status 0 — Codex reviewed and the reports are filed. Skip step 3
   - Exit status 3 — Codex did not review: it is not installed, it is turned off for this project, the code is too large to send, or the run failed. The `FALLBACK=` line says which, and nothing was written: you are the reviewer, go to step 3 with that reason
   - Exit status 2 — relay the `ERROR=` line to the user and stop (for a missing architecture doc or stories: run the earlier phases first)
3. **Fallback: you review** — only when Codex did not. Run `python3 "$HELPER" brief`, follow it as your agent definition's When You Are the Reviewer section describes, and file your answer with the `FALLBACK=` reason from step 2, copied exactly, in single quotes:

   ```bash
   python3 "$HELPER" file --reason '<the FALLBACK reason>' <<'CODE_REVIEW_JSON'
   <your JSON answer>
   CODE_REVIEW_JSON
   ```

   If it is rejected (exit status 4), fix what the `ERROR=` line names and file again, at most twice more; after that tell the user the review could not be filed and why
4. **Read what was filed** — the `REPORTS=` line lists the files under `docs/sprints/sprint-<NN>/reviews/`. Read them and confirm each names the right reviewer and story. Do not edit them
5. **Log everything** — log who reviewed (and why, if it was the fallback), the stories reviewed, and the verdict to `logs/agent-workflow.log`

## What the Review Covers

The code in the in-scope component paths from the `## Components` table of `docs/architecture.md` (never anything under `### Excluded Paths`; the whole project root as component `app` when there is no table), checked against `docs/architecture.md`, `docs/stories/`, and `docs/ux/`, for each story that has an implementation:

- [ ] Follows architecture doc folder structure
- [ ] Data models match architecture spec
- [ ] API endpoints match contracts
- [ ] Language-specific best practices followed (as defined by the tech stack in `docs/architecture.md`)
- [ ] Framework best practices followed for each reviewed component, per its row in the `## Components` table
- [ ] Changes are confined to the components the story targets
- [ ] No code duplication
- [ ] Consistent naming conventions
- [ ] Error handling present where needed

Security-specific issues (XSS, injection, secrets, auth) belong to the Security phase — they go under `flagged_for_security` in the answer, which the helper prints as one "Flagged for security review" line in the Summary, never as a finding.

## Acceptance Criteria for This Phase

- A report exists in `docs/sprints/sprint-<NN>/reviews/` for each story with an implementation, written by the helper and not edited afterwards, naming its reviewer
- Each report has findings categorized by severity (critical/warning/suggestion), each referencing a specific file:line location
- Each report's verdict is clearly stated: APPROVED or NEEDS CHANGES (NEEDS CHANGES whenever a critical finding exists — the helper derives it)
- When the fallback reviewed, the reviewer line says why Codex did not
- No project file other than this sprint's review reports and the shared log was changed
- All actions logged to `logs/agent-workflow.log`

## After Completion

Say who reviewed in every case (e.g. "reviewed by OpenAI Codex" / "reviewed by Claude — Codex CLI not installed").

- If `VERDICT=APPROVED`: Tell the user "Code review passed. Run `/maxPlanck-audit` to run the security audit."
- If `VERDICT=NEEDS CHANGES`: Tell the user "Code review found critical issues — see `docs/sprints/sprint-<NN>/reviews/`. Run `/maxPlanck-develop` again to address the findings, then re-run `/maxPlanck-review`."
- If `VERDICT=NOTHING REVIEWED`: Tell the user which stories have no implementation yet (the `NOT_REVIEWED=` line) and suggest `/maxPlanck-develop`.
