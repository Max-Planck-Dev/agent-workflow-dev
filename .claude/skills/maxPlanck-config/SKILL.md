---
name: maxPlanck-config
description: Show or change the project's workflow profile (default, nacho, …), its feature switches and which Claude model each agent runs on (.claude/maxPlanck-config.json). Use to switch profile, turn a phase on or off, put the Developer on opus, or just see the current table.
user-invocable: true
---

<!-- Deliberately unbound: no `context: fork`, no `agent:`. This is
     configuration, not a pipeline phase — the result must land in the main
     session. It is not an orchestrator either, so it does not log to
     logs/agent-workflow.log. -->

# Workflow Configuration

The user wants to see or change how the workflow runs in this project: which **profile** it follows, which **feature switches** are on, and which **Claude model** each agent runs on. All of it lives in `.claude/maxPlanck-config.json`, which names a profile and records only the overrides. The helper script owns that file and the `model:` lines of the agent files — you never edit either by hand.

Profiles are presets. `default` is the documented ten-agent pipeline with nothing extra; `nacho` turns on every optional phase (design review, plan, plan review, per-story loop, integration gate, design system at kickoff) and Codex reviews, with its own model choices. `profiles` lists what is installed.

## The helper

Use the first that exists:

1. `.claude/bin/maxPlanck-config.py` — an installed project. Run it from the project root.
2. Nothing under `.claude/bin/` but `bin/workflow_config.py` present — this is the workflow's own source repository. Profiles apply to installed projects; the tracked agent files stay at the default profile. Say so and stop.
3. Neither — a plugin install. A plugin's agent files cannot be rewritten and its orchestrators read every switch as off: it runs the default profile. Say so and stop.

| Command | Does |
|---------|------|
| `show` | Every switch and every installed agent's model, each with its source (`profile <name>` or `override`) |
| `features` | The machine-readable form the orchestrators read (`PROFILE=`, `ORDER=`, one line per switch) |
| `profile <name>` | Switches profile, drops every override (it says which), applies the models |
| `set k=v …` | `design-review=on`, `codex=off`, `default=sonnet`, `developer=opus`; an empty value (`developer=`) drops that override. Validates everything first and writes nothing when any pair is bad |
| `reset` | Drops every override of the current profile |

Every command prints `ERROR=…` and exits 2 when something is wrong, and writes nothing in that case. Feature values are `on`/`off`; roles are agent names without the prefix (`developer`, `qa-tester`, …) and `show` lists the ones installed, so never guess them; models are whatever Claude Code accepts in `model:` (`sonnet`, `opus`, `haiku`, `fable`, `inherit`, or a full model id).

Turning on `codex` (directly, or by choosing a profile that has it on) is this project's consent to send its design documents and in-scope code to OpenAI through the project's own Codex login when a review runs. The helper prints a `NOTICE=` line whenever that happens; relay it.

## Your Task

Read the command arguments.

1. **No arguments, or `show`** — run `show` and print its table verbatim. Then tell the user how to change it (`/maxPlanck-config profile nacho`, `/maxPlanck-config set design-review=on developer=opus`, `/maxPlanck-config reset`) and end your turn. Do not prompt; the next command is theirs.
2. **`profile <name>`**, **`set k=v …`**, **`reset`** — run exactly that.
3. **Natural language** ("put the developer on opus", "turn the design review off", "Nacho's setup") — translate it to the helper's form against the roles and features `show` lists, print the command you are about to run, and run it. If a word is genuinely ambiguous ("the reviewer" can be several agents), print the candidates and end your turn instead of guessing.

```bash
python3 .claude/bin/maxPlanck-config.py set design-review=on developer=opus
```

Print the helper's output as is: it says which switch moved, which agent moved from which model to which, or that nothing changed. On `ERROR=`, show the message and fix the input, not the file.

## After Completion

Tell the user what changed. Claude Code loads agent definitions when a session starts, so a changed model takes effect in the next session; the SessionStart hook re-applies the config at every start. A changed switch takes effect on the next `/maxPlanck-feeling-lucky` or `/maxPlanck-change` run — a pipeline already running keeps the switches it started with.
