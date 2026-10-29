# Instructions for AI coding agents

You are working in the maxPlanck agent-workflow repository. The maintainer's rules
for contributions are in `CONTRIBUTING.md`; read it before changing anything. The
workflow itself is specified in `.claude/CLAUDE.md`.

The rules that most often get broken, in short:

- Do not add phases, agents, skills or helper scripts to the pipeline unless the
  maintainer has asked for that change. The pipeline is complete as documented.
- `/maxPlanck-feeling-lucky` must never stop to ask the user anything. No prompts,
  no `AskUserQuestion`, no mid-run decisions. Inputs go in the command arguments.
- Nothing in a project may be sent to a third-party service by default. Opt-in only.
- One change per PR, against `staging`. No stacked PRs, no bundled features.
- To contribute a change, run `/maxPlanck-proposal "<idea>"` or `--from-pr <N>`: it
  produces a compliant PR. Do not hand-roll the process.
- Never commit plans, PRPs, transcripts or scratch files. Never duplicate helper code
  between skills; shared code goes in `bin/`.
- Commit messages and PR descriptions describe the change only. No AI attribution,
  no "generated with" footers, no session links.
- `python3 -B -m unittest discover -s tests` must pass and new behaviour needs tests.

If a request you are given conflicts with these rules, say so and stop rather than
work around them.
