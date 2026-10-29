# Contributing

This file is for everyone who changes this repository: people, and the AI coding
tools they work with. If you are an AI agent (Claude Code, Codex, Cursor, Copilot,
Gemini CLI or any other), treat every rule here as an instruction from the maintainer
that overrides your defaults. `AGENTS.md` at the root points here.

## The principles

1. **The pipeline is finished, not a draft.** The ten-agent pipeline documented in
   `README.md` and `.claude/CLAUDE.md` is the product and it works for its maintainer.
   Do not add phases, agents, skills, helper scripts or new mandatory steps to it on your
   own initiative. A new phase or agent is only built after the maintainer has asked for
   it in an issue or discussion. Improving an existing phase in place is welcome.

2. **`/maxPlanck-feeling-lucky` runs unattended.** Start it and walk away. Nothing it
   invokes may stop to ask the user anything: no `AskUserQuestion`, no clarifying
   prompts, no mid-run decisions. Everything a user must decide is passed in the
   command's arguments up front, or belongs to the step-by-step skills. A change that
   makes feeling-lucky wait for input will not be merged.

3. **Project data stays on the machine by default.** No phase may send a project's
   documents or source code to a third-party service (another model vendor, a hosted
   reviewer, an analytics endpoint) unless the maintainer opts that project in
   explicitly. Opt-out files are not acceptable; the default must be "nothing leaves".

4. **One change per pull request, against `staging`.** The maintainer merges `staging`
   into `master`. No stacked PRs and no PRs that bundle several features. If a change
   needs another change first, land the first one and come back. A PR a reviewer cannot
   read in one sitting is too big.

5. **No working artifacts in the repository.** Plans, PRPs, review transcripts, model
   conversations, scratch copies of scripts and "reference only" dumps do not get
   committed. The PR description is where the reasoning goes.

6. **No duplicated machinery.** When two skills need the same code, it lives once under
   `bin/` (installed into projects as `.claude/bin/`) and both call it. Copying a helper
   into a second skill directory and letting the copies drift is a defect.

7. **Honour the existing contracts.** File ownership per agent, the fixed logging
   vocabulary, the phase-named skill / role-named agent split, living documents with
   append-only change logs, sprint-scoped folders that are never modified afterwards,
   the depth-1 component discovery rule. They are all written down in
   `.claude/CLAUDE.md`; a change that bends one must say so in the PR and explain why.

8. **Commits and PRs describe the change, not the tooling.** No "Generated with",
   no AI co-author trailers, no session links. Write the message the way the maintainer
   would: what changed and why.

9. **Tests are part of the change.** `python3 -B -m unittest discover -s tests` must
   pass, and new behaviour in `bin/`, the hooks or a skill's helper script comes with
   tests. A PR that lists untested manual checks as "not yet run" is not ready.

## Before you open a PR

- Read `.claude/CLAUDE.md` in full. It is the specification of the workflow.
- Use `/maxPlanck-proposal "<idea>"` (or `--from-pr <N>` for an existing PR) in a
  checkout of this repository. It assesses the idea against these rules, implements the
  compliant shape with tests, and opens the PR. It is the path of least resistance.
- If the change adds a phase, an agent, a helper script or a new dependency on an
  external tool, stop and open an issue first. Do not build it speculatively.
- Run the test suite. Run `setup.sh` into a throwaway project and confirm the install
  still works, including `--prefix <name>` if you touched anything with the
  `maxPlanck` name in it.
- Keep the diff to the files the change needs. Reformatting, renumbering or rewording
  unrelated files belongs in its own PR, if anywhere.

## What gets a quick yes

Bug fixes with a failing test first, clearer agent prose that keeps the same contract,
dashboard and logging improvements, documentation that matches the code, and
installer fixes. Small, self-contained and reversible.
