# Multi-Agent Agile Workflow

A demonstration of Claude Code's multi-agent capabilities using Agile role-based subagents that collaborate to build an app.

## Installation

### Script install (recommended today)

From your project root:

```
d=$(mktemp -d) && git clone https://github.com/Max-Planck-Dev/agent-workflow-dev.git "$d" && bash "$d/setup.sh" .; rm -rf "$d"
```

Or, if you use the [GitHub CLI](https://cli.github.com/) (`gh auth login` once first):

```
d=$(mktemp -d) && gh repo clone Max-Planck-Dev/agent-workflow-dev "$d" && bash "$d/setup.sh" .; rm -rf "$d"
```

The repo is public, so the plain `git clone` form needs no credentials. If it fails anyway, the usual causes are `git` missing from your `PATH`, a proxy or firewall blocking github.com, or running the command from a shell other than bash or zsh (`$(mktemp -d)` and `&&` are POSIX-shell syntax, so run it from bash or zsh, not from Windows cmd or PowerShell).

The installer copies the agents, skills, hooks, and shared config into your project's `.claude/`, merges the logging hooks into your `settings.json` without touching your own hooks, and records what it installed in `.claude/maxPlanck-workflow-version.json`.

### Plugin install

The repo is also a Claude Code **plugin** (`.claude-plugin/plugin.json`): skills, agents, and the logging hooks load directly from a versioned source instead of being copied into each project. Install goes through a plugin marketplace — ours is coming soon; once it exists, installation is `/plugin marketplace add <marketplace>` + `/plugin install maxplanck`, and updates flow through the plugin system automatically (every commit is a new plugin version).

Note: plugin-installed skills are invoked with the plugin namespace (`/maxplanck:maxPlanck-kickoff`), while script installs use the bare names (`/maxPlanck-kickoff`).

### Make it your own (rebranding)

This is an open project — you can install the whole team under **your** name:

```
d=$(mktemp -d) && git clone https://github.com/Max-Planck-Dev/agent-workflow-dev.git "$d" && bash "$d/setup.sh" . --prefix acme; rm -rf "$d"
```

(or `gh repo clone Max-Planck-Dev/agent-workflow-dev "$d"` in place of the `git clone`, as above)

Every file name, skill name, agent name, and cross-reference is rewritten from `maxPlanck` to your prefix: you get `/acme-kickoff`, `/acme-feeling-lucky`, `.claude/acme-default-stack.md`, and so on. Brand the reports too via `.claude/<prefix>-brand.json`.

**Updates still work for rebranded installs** — with one rule: update by re-running the installer with the *same* `--prefix`, and don't hand-edit the installed workflow files (the update overwrites them; customize by forking the source repo instead). The weekly update check knows your prefix and prints the right command. What a rebranded install can't use is the *plugin* route, which ships fixed names.

## Multi-component projects

Your product does not have to be one folder. The Architect scans the project root one level
down, proposes which folders are part of the product and which are not, and asks you to
confirm — then records the answer in `docs/architecture.md` as a `## Components` table plus
an `### Excluded Paths` list. From then on every agent routes through it: builds and tests
run from each component's own directory with that component's own commands, and anything
under Excluded Paths is never read, tested, or reported on.

The project root itself does not need to be a git repository — the components can carry the
repositories, and each one gets its own CI pipeline in its own repo. A single-folder project
gets a one-row table and behaves exactly as before.

## Staying up to date

Script installs record their source repo and commit in `.claude/maxPlanck-workflow-version.json`. A `SessionStart` hook checks the source repo at most **once a week** (silently, offline-safe) and, when the installed commit is behind, tells you at the start of your session — with the exact re-install command to run. Updating is just re-running the installer: it overwrites the workflow's own files, cleans up renamed/legacy leftovers, and leaves your project files, your hooks, and your `CLAUDE.md` alone.

## What Is This?

Ten specialized AI agents — Product Owner, UX Designer, Architect, Developer, Code Reviewer, Security Reviewer, DevOps Engineer, QA Tester, Scrum Master, and Release Manager — work together through a standard Agile pipeline. Each agent has a defined role, reads artifacts from previous phases, and produces its own outputs. Knowledge compounds across cycles: living docs (PRD, architecture) keep append-only change logs, while per-cycle artifacts (reviews, test results, security reports, sprint summaries) land in `docs/sprints/sprint-NN/` folders. Two orchestration skills (`feeling-lucky`, `change`) drive multi-phase runs, and `report` produces the release-handoff pack.

**No pre-scaffolding.** Agents handle everything from requirements through implementation.

## Commands

| Command | What it does |
|---------|--------------|
| `/maxPlanck-kickoff` | Product Owner writes PRD + stories from your idea |
| `/maxPlanck-ux` | UX Designer creates wireframes and component specs |
| `/maxPlanck-design` | Architect designs the technical system |
| `/maxPlanck-develop` | Developer scaffolds the project and implements features |
| `/maxPlanck-review` | Code Reviewer audits the implementation |
| `/maxPlanck-audit` | Security Reviewer audits and writes Infrastructure Security Requirements |
| `/maxPlanck-infra` | DevOps creates IaC and CI/CD pipelines |
| `/maxPlanck-test` | QA writes and runs tests |
| `/maxPlanck-sprint` | Scrum Master reviews everything and summarizes |
| `/maxPlanck-feeling-lucky` | Runs the entire pipeline end-to-end automatically |
| `/maxPlanck-adopt` | Adopts an existing codebase — reverse-engineers the founding docs as-built |
| `/maxPlanck-change` | Runs a change request through the team — docs update first, then implement → review → test |
| `/maxPlanck-report` | Release Manager generates the 4-report release pack: internal report, client report, blog-style release note, QA checklist |
| `/maxPlanck-design-review` | Profile switch `design-review`: an independent reviewer checks the design before any code, and the Architect accepts or rejects each proposal |
| `/maxPlanck-plan` | Profile switch `plan`: the Tech Lead writes development plans (story order + tasks per story) the Developer follows |
| `/maxPlanck-plan-review` | Profile switch `plan-review`: an independent reviewer checks one story's plan, and the Tech Lead rules on each proposal |
| `/maxPlanck-config` | Shows or changes the project's profile, feature switches and agent models |
| `/maxPlanck-proposal` | This repo only (never installed): turns an idea or an existing PR into a PR that complies with `CONTRIBUTING.md` |

## Profiles

A project follows a named **profile**, recorded in `.claude/maxPlanck-config.json` together with any overrides. `default` is the pipeline documented here: ten agents, nothing extra, every agent on `sonnet`. Other profiles turn on optional phases and other models; `nacho` is the first. Pick one at install time (`./setup.sh --profile nacho /path/to/project`) or later (`/maxPlanck-config profile nacho`), and change single switches with `/maxPlanck-config set design-review=on developer=opus`. The switches so far: `design-system` — the kickoff records a `## Design System` section in the PRD (from an existing reference, answers given with the idea, or the designer's call; nothing is asked) and the UX Designer writes `docs/ux/design-system.md`, which the Architect, Developer and reviewers then hold the UI to. `design-review` — before any code is written, a Design Reviewer with a fresh context reads the architecture doc against the PRD, stories and UX specs and files improvement proposals in `docs/sprints/sprint-NN/design-review.md`; the Architect accepts, partially accepts or rejects each one in a `## Design Review Log`, and the reviewer re-checks once more at most. `codex` — the reviews use the [OpenAI Codex CLI](https://github.com/openai/codex) (`codex` on your `PATH`, logged in with `codex login`), a different model from the one that wrote the design, with Claude as the fallback when a run fails; each round of a report says who reviewed it. `plan` — a Tech Lead writes the sprint's story order (`docs/sprints/sprint-NN/dev-plan.md`) and one plan per story (`plans/story-NNN-plan.md`: implementation order, tasks mapped to acceptance criteria, files, verification commands) before the Developer builds, so the implementation starts from decisions already made. `plan-review` — each story's plan gets the same independent review as the design (Codex or Claude, stable `PR-NN-SSS-n` IDs, the Tech Lead rules in the plan's `## Plan Review Log`), checked against the design and a paths-only inventory of the code that exists; a second round only after a CRITICAL or HIGH proposal. `story-loop` — plan, plan review, develop and code review run one story at a time in the Tech Lead's story order, so each plan is written against the code the earlier stories left and each review is one story's worth; the dashboard shows `story k/n`. `integration-gate` — stories are verified with quick per-component checks (typecheck, lint, the tests related to the changed files) instead of full builds, and one integration build of every component runs before the security audit, with the failing output in `docs/sprints/sprint-NN/integration-gate.md` as the work order.

**What leaves your machine with `codex` on:** the review documents (architecture, PRD, stories, UX specs) go to OpenAI through your own Codex login. Codex is given a temporary copy of those documents only and runs in its read-only sandbox — but that sandbox restricts writing, not reading, so treat it as reduced exposure rather than isolation. The switch is enforced in the helper script, not in prose: with it off, Codex is never invoked. It is off in the `default` profile and on in `nacho`; `/maxPlanck-config set codex=off` turns it off in any profile. The models are written into the agent files at install and at every session start; the switches are read by `/maxPlanck-feeling-lucky` and `/maxPlanck-change` when a run starts. A profile that turns on an external reviewer is the project's consent to send its documents to that service; `default` never does.

## Tech Stack (Built by Agents)

Determined at design time by the **Architect** agent:
1. Detects existing project stack (scans for `package.json`, `pyproject.toml`, `go.mod`, etc.)
2. Respects user preferences stated in the PRD
3. Falls back to defaults defined in `.claude/maxPlanck-default-stack.md`
4. Records every independently-buildable **component** (path, kind, git repo, CI workflow, stack) in a `## Components` table in `docs/architecture.md`, so a project root holding several separate folders — or several separate repositories — works the same way a single one does

## Agent Pipeline

```
Product Owner → UX Designer → Architect → Developer → Code Reviewer → Security → DevOps → QA Tester → Scrum Master
```

When you decide a feature set is ready to ship, the **Release Manager** (`/maxPlanck-report`) produces the client-facing handoff pack — a release-cadence step outside the sprint loop.

## Contributing

Read `CONTRIBUTING.md` before opening a pull request. It is short and it is binding: the pipeline is complete as documented, `/maxPlanck-feeling-lucky` never asks the user anything, project data never leaves the machine by default, and every change arrives as one small PR against `master` with tests. `AGENTS.md` at the root carries the same rules for AI coding tools.

## Observability

Every agent handoff is logged to `logs/agent-workflow.log` via two mechanisms:

1. **Lifecycle hooks** — Automatic `START`/`STOP` entries when any subagent runs (`.claude/hooks/log-agent-lifecycle.sh` extracts the agent name from the hook payload; the same hook records machine-readable events in `logs/pipeline-events.jsonl` for the dashboard)
2. **Semantic logging** — Agents log their decisions and outputs inline, including `PROGRESS | Agent: … | <n>/<total> | <what>` lines that say how far along they are

## Live dashboard

Orchestrated runs (`/maxPlanck-feeling-lucky`, `/maxPlanck-change`) can take hours. The dashboard turns the log into a live view: the phases top to bottom with re-run counts and, under each finished phase, what it did (the orchestrator's routing reason), the loops taken (review → develop ×2 …), the current agent with its `PROGRESS` as a percentage (or, when an agent has not reported, a ballpark estimated from how long earlier runs of the same phase took), elapsed time, a tool-call heartbeat read from the subagent's own transcript, unresolved items, and the log tail.

**Standalone** (any terminal, from the project root, `q` to quit):

```bash
python3 .claude/bin/maxPlanck-dashboard.py            # script installs
python3 /path/to/dev-agent-workflow/bin/pipeline_dashboard.py --cwd .   # plugin installs / this repo
```

`--once` prints a single frame, `--json` dumps the parsed model.

**Inside [herdr](https://github.com/brianh20/herdr)** this repo is also a herdr plugin. Link it once:

```bash
herdr plugin link /path/to/dev-agent-workflow
```

From then on the first workflow agent of a run opens the dashboard as a split pane next to the Claude pane (once per run; it stays open), the run's completion shows a herdr notification, and the Claude pane's sidebar row can show the current phase and agent. The plugin also provides `pipeline: toggle/open/close dashboard` actions (`herdr plugin action invoke toggle --plugin maxplanck.pipeline`).

Optional `~/.config/herdr/config.toml` snippets — a keybinding for the toggle and the sidebar tokens the dashboard publishes:

```toml
[[keys.command]]
key = "prefix+shift+p"
type = "shell"
command = "herdr plugin action invoke toggle --plugin maxplanck.pipeline"

[ui.sidebar.agents.rows_by_agent]
claude = [["state_icon", "workspace", "tab"], ["$phase", "$agent"]]
```

Nothing herdr-specific is copied into projects: the hook opens the pane for whichever project is running, and the pane reads that project's `logs/`.

## Quick Start

See [QUICKSTART.md](./QUICKSTART.md) for usage instructions.
