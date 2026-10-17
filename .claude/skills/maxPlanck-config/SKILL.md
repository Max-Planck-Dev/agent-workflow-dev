---
name: maxPlanck-config
description: Show or change which Claude model each workflow agent runs on (.claude/maxPlanck-models.json). Use to put the Developer on opus, everyone on sonnet, restore the defaults, or just see the current table.
user-invocable: true
---

<!-- Deliberately unbound: no `context: fork`, no `agent:`. This is
     configuration, not a pipeline phase — it talks to the user and the
     result must land in the main session. It is not an orchestrator either,
     so it does not log to logs/agent-workflow.log. -->

# Agent Models — Configuration

The user wants to see or change which Claude model each workflow agent runs on. The choice lives in `.claude/maxPlanck-models.json` (role → model); Claude Code only reads a subagent's model from the `model:` line of its agent file, so the config has to be copied into the agent files — the applier script does that, never you.

## The applier

Resolve it in this order and use the first that exists:

1. `.claude/bin/maxPlanck-models.py` — an installed project
2. `bin/agent_models.py` — this workflow's own source repo (changing the config here rewrites tracked agent files; the wiring tests will say so)

If neither exists, this is a plugin install: a plugin's agent files live in the plugin cache and cannot be rewritten, so the agents run on the shipped defaults. Say so and stop — do not try to edit anything.

Commands (every one prints `ERROR=…` and exits 2 when something is wrong, and writes nothing in that case):

| Command | Does |
|---------|------|
| `show` | Table of agent → model and where each value came from (`config`, `config default`, `built-in`, `built-in default`) |
| `set role=model …` | Edits the config and applies it. Creates the file from the defaults when absent. `default=sonnet` sets the fallback; `qa-tester=` (empty) drops that role's override so it falls back to `default` |
| `reset` | Rewrites the config with the built-in defaults and applies it |

Roles are the agent names without the prefix (`developer`, `tech-lead`, `qa-tester`, …) — `show` lists the ones actually installed, so never guess them. Models are whatever Claude Code accepts in `model:`: `sonnet`, `opus`, `haiku`, `fable`, `inherit`, or a full model id (`claude-opus-5-5`, `opus[1m]`).

**Never edit `.claude/maxPlanck-models.json` or the agent files by hand.** The script validates roles and models, keeps the rest of the file intact, writes atomically, and applies in the same step — a hand edit skips all of that.

## Your Task

Read the command arguments.

1. **No arguments, or `show`** — run `show` and print its table verbatim. Then ask the user what they want to change, offering: keep it as is; a single model for everyone (`default=<model>` plus dropping every override listed under `config`); the built-in defaults (`reset`); or specific roles. Do not ask again after that — act on the answer.
2. **`role=model` pairs** (e.g. `/maxPlanck-config developer=opus tech-lead=fable`) — run `set` with exactly those pairs.
3. **`reset`** — run `reset`. If the config currently differs from the defaults (`show` says `config` on any row), name what will move before running it.
4. **Natural language** (e.g. "poné al developer en opus y al resto en sonnet") — translate it to `role=model` pairs against the roles `show` lists, print the pairs you are about to apply, and run `set`. Only ask when a role or model is genuinely ambiguous ("the reviewer" could be three agents).

Run the script from the project root, for example:

```bash
python3 .claude/bin/maxPlanck-models.py set developer=opus default=sonnet
```

Print the script's output: it says which agent moved from which model to which, or that nothing changed. On `ERROR=`, show the message as is and fix the input, not the file — an unknown role is almost always a typo, and the message lists the known ones.

## After Completion

Tell the user which agents moved (from the script's output) and that the change is already written into the agent files. Claude Code loads agent definitions when a session starts, so to be sure the next phase runs on the new model, start a new session before invoking it. The SessionStart hook re-applies the config at every start, so later edits to the JSON take effect the same way.
