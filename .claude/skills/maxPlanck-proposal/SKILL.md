---
name: maxPlanck-proposal
description: Turn an idea, or an existing pull request, into a pull request that complies with this repository's CONTRIBUTING.md — assessed against the manifesto, implemented with tests, opened with gh. Repo-only; never installed into projects.
user-invocable: true
---

# Proposal — Improve This Workflow, the Compliant Way

The user wants to change the maxPlanck agent workflow itself: a new idea, or an existing pull request whose intent is good but whose shape does not fit `CONTRIBUTING.md`. Take the intent, give it a shape that complies with every rule, and open one pull request for it.

This skill exists only in the source repository (`.repo-only` marker in its directory; `setup.sh` never installs it and the plugin manifest does not list it). Like the orchestrators it has no `context: fork` / `agent:` binding, because it must run git and `gh`, run the test suite, and let the user watch — but it is not a pipeline phase and it never writes to `logs/agent-workflow.log`.

Invoking this skill is the user's say-so for one commit and one push on a `proposal/*` branch, and for opening the pull request. It never pushes to `master` or `staging`.

## Input

```
/maxPlanck-proposal "<idea in one or more sentences>"
/maxPlanck-proposal --from-pr <N>          # adapt an existing PR of this repo
/maxPlanck-proposal --assess "<idea>"      # assessment only, change nothing
/maxPlanck-proposal --base <branch> "<idea>"
```

- `--from-pr N`: read the PR with `gh pr view N --json title,body,author,number,headRefName,url` and its diff with `gh pr diff N`. The author's login and the PR URL go into the Origin section of the new PR; the PR is the source of intent, never the source of the implementation — read it for what it wanted, not for what it wrote.
- `--base`: the branch the PR targets. Without it, `staging` when `git ls-remote --heads origin staging` lists it, else `master`.
- `--assess`: stop after step 3.

If neither an idea nor `--from-pr` was given, say that one of them is required and stop. Do not ask follow-up questions afterwards: every decision below is made from the manifesto and the code.

## Steps

1. **Read the rules.** `CONTRIBUTING.md`, `AGENTS.md` and `.claude/CLAUDE.md` in full. Then `tests/test_contributing.py`: its `EXPECTED_AGENTS` and `EXPECTED_SKILLS` sets are the registry of what the pipeline has, and its other tests are the rules a machine checks. If `bin/workflow_config.py` exists, read its `FEATURES` and `PROFILES`: a change to the pipeline's shape lands behind a feature switch there, off in the `default` profile.

2. **Understand the intent.** From the idea or the PR, write one sentence saying what the contributor wants to be true afterwards. If the PR bundles several intents, pick the first one in pipeline order and carry the rest to Follow-ups.

3. **Assess — in the conversation, never in a committed file.** Print:
   - **Intent:** the one sentence.
   - **Manifesto check:** one line per numbered rule of `CONTRIBUTING.md`: `fits`, or `conflicts — <how the compliant shape resolves it>`. A conflict with rule 2 (feeling-lucky never asks) is resolved by taking inputs from command arguments, a file, or a default — never by a prompt. A conflict with rule 3 (data stays local) is resolved by a feature switch that is off in the `default` profile. A conflict with rule 6 (no duplicated helpers) is resolved by one script under `bin/`.
   - **Scope of this PR:** the one slice that fits in one sitting. Anything else goes to Follow-ups.
   - **Profile switch:** the `bin/workflow_config.py` feature it lands behind, if the pipeline's behaviour changes; `none` for a bug fix, a doc fix or a tooling change.
   - **Files:** what is added or modified, and which test file proves it.
   If the intent cannot be made to comply at all (it needs a prompt in an unattended run and nothing else will do, or it needs project data to leave the machine unconditionally), say so, say what the nearest compliant form would be, and stop.
   With `--assess`, stop here.

4. **Branch.** `git fetch origin <base>` then `git checkout -b proposal/<slug> origin/<base>`, where `<slug>` is three to six lowercase words joined by hyphens. Refuse to continue if the working tree is dirty.

5. **Implement**, in this repository's idiom:
   - Prose for skills and agents, small stdlib-only Python under `bin/` for anything a machine must decide, hooks under `.claude/hooks/`.
   - Adding an agent or a skill: add it to `EXPECTED_AGENTS` / `EXPECTED_SKILLS` in `tests/test_contributing.py`, to `.claude-plugin/plugin.json`, and to the ownership table and Definition of Done in `.claude/CLAUDE.md`, in the same commit. That is the deliberate-change mechanism; it is not a test to work around.
   - Changing the pipeline's shape: gate it behind the feature switch from step 3, `False` in the `default` profile, and keep the `default` behaviour byte-identical.
   - Never create `.claude/PRPs/`, plan files, transcripts or a copy of a script. Never add a question tool call or any other prompt to a skill or agent (the contributing tests grep for the tool name).
   - Document only what changed: the relevant lines of `README.md`, `QUICKSTART.md` and `.claude/CLAUDE.md`, nothing regenerated.

6. **Prove it.** Write the tests first where a behaviour is testable, then run `python3 -B -m unittest discover -s tests`. Every test must pass; fix the change, not the test. If `setup.sh` or anything it copies changed, also run `./setup.sh --prefix acme <temp dir>` and check that no `maxPlanck` string survives in the install.

7. **Commit.** One commit. The message describes the change and why, as the maintainer would write it: no attribution, no tooling, no session links (the history test rejects them). Then `git push -u origin proposal/<slug>`.

8. **Open the PR.** `gh pr create --base <base> --title "<the commit subject>" --body-file <temp file>` with exactly this body, nothing appended:

   ```markdown
   ## Intent
   <the one sentence>

   ## Origin
   <"Adapted from #N by @login — <PR URL>" | "Idea from <who, as given in the conversation>">

   ## How it complies
   - Rule 1 (pipeline complete): <one line>
   - Rule 2 (feeling-lucky unattended): <one line>
   - Rule 3 (data stays local): <one line>
   - Rule 4 (one change per PR): <one line>
   - Rule 5 (no working artifacts): <one line>
   - Rule 6 (no duplicated helpers): <one line>
   - Rule 7 (existing contracts): <one line>
   - Rule 8 (commits describe the change): <one line>
   - Rule 9 (tests): <one line>

   ## Profile
   <switch name, off in `default`> | none

   ## Tests
   <test file(s) and what they prove; the suite's count>

   ## Follow-ups
   <the slices not in this PR, one line each, or "None">
   ```

   Print the PR URL and stop. Do not merge it.

## Acceptance Criteria

- The assessment was printed before any file changed
- Exactly one branch `proposal/<slug>`, one commit, one PR against the right base
- `python3 -B -m unittest discover -s tests` passes on the branch, including `tests/test_contributing.py`
- No `.claude/PRPs/`, no transcript, no plan file, no copied script in the diff
- The PR body follows the template and credits the origin
