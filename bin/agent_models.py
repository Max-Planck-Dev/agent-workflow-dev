#!/usr/bin/env python3
"""Which Claude model each workflow agent runs on.

Claude Code takes a subagent's model from the `model:` line in the agent
file's frontmatter, and nothing else sets it per agent: settings.json has no
per-agent override and hooks cannot change it. So the choice lives in a file
the installer never overwrites, `.claude/maxPlanck-models.json`, and this
script writes it into the installed agent files — at install time (setup.sh)
and at session start (the apply-agent-models.sh hook), so editing the JSON
is all a user has to do.

    {
      "default": "sonnet",
      "agents": { "tech-lead": "fable", "developer": "opus" }
    }

Keys under "agents" are role names without the prefix (the part of the
agent name after `maxPlanck-`), so the file survives a rebranded install.
Values are whatever Claude Code accepts in an agent's `model:` line: an alias
(`sonnet`, `opus`, `haiku`, `fable`, `inherit`) or a full model id.

Once the file exists it is the whole answer: a role not listed under
"agents" gets the file's "default" (or `sonnet` when the file has no
"default" either). The built-in per-role defaults below are used only to
create the file (`init`) and when it does not exist.

Commands (all take --root, default $CLAUDE_PROJECT_DIR or the cwd):

    init    write the config with the built-in defaults, unless it exists
    show    table of agent → model and where each value came from
    apply   rewrite the `model:` line of every installed agent; idempotent.
            --quiet prints nothing unless a file changed or the config is
            unusable, which is what the session-start hook wants.
    set     `set developer=opus default=sonnet qa-tester=` edits the config
            (creating it from the defaults when absent; an empty value drops
            that role's override) and applies it. Nothing is written when any
            assignment is invalid. This is what /maxPlanck-config runs.
    reset   rewrite the config with the built-in defaults and apply it.

Exit status: 0 on success (including nothing to do), 2 when the config
cannot be read or an assignment is invalid — the offending line starts
with `ERROR=`.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

# Rewritten to the chosen prefix by setup.sh, like every other workflow file.
PREFIX = "maxPlanck"

DEFAULTS: Dict[str, object] = {
    "default": "sonnet",
    "agents": {
        "architect": "fable",
        "design-reviewer": "opus",  # the Claude fallback; Codex reviews when installed
        "tech-lead": "fable",
        "plan-reviewer": "opus",  # same: the fallback behind Codex
        "developer": "opus",
        "code-reviewer": "opus",  # same: the fallback behind Codex
        "security": "opus",
        "devops": "opus",
    },
}

# An alias or a model id — including `opus[1m]`, Bedrock ARNs and Vertex ids,
# so anything without whitespace that cannot break the YAML line. Claude Code
# validates the real thing; this only keeps `model: op us` out of a file.
MODEL_RE = re.compile(r"^[^\s\"'#]\S*\Z")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
MODEL_LINE_RE = re.compile(r"^model:[ \t]*(.*?)[ \t]*$", re.M)
NAME_LINE_RE = re.compile(r"^name:.*$", re.M)


class ConfigError(Exception):
    pass


@dataclass(frozen=True)
class Resolved:
    role: str
    model: str
    source: str  # "config" | "config default" | "built-in" | "built-in default"


def config_path(root: str) -> str:
    return os.path.join(root, ".claude", f"{PREFIX}-models.json")


def agents_dir(root: str) -> str:
    return os.path.join(root, ".claude", "agents")


def installed_roles(root: str) -> List[str]:
    """Roles of the workflow agents installed in this project, sorted."""
    directory = agents_dir(root)
    if not os.path.isdir(directory):
        return []
    head = f"{PREFIX}-"
    return sorted(
        name[len(head) : -len(".md")]
        for name in os.listdir(directory)
        if name.startswith(head) and name.endswith(".md")
    )


def agent_file(root: str, role: str) -> str:
    return os.path.join(agents_dir(root), f"{PREFIX}-{role}.md")


def load_config(root: str) -> Optional[dict]:
    """The user's config, or None when the file does not exist."""
    path = config_path(root)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be an object")
    agents = data.get("agents", {})
    if not isinstance(agents, dict):
        raise ConfigError(f'{path}: "agents" must be an object of role → model')
    for role, model in agents.items():
        if not isinstance(model, str) or not MODEL_RE.match(model):
            raise ConfigError(f'{path}: "agents.{role}" must be a model alias or id, got {model!r}')
    default = data.get("default")
    if default is not None and (not isinstance(default, str) or not MODEL_RE.match(default)):
        raise ConfigError(f'{path}: "default" must be a model alias or id, got {default!r}')
    return data


def resolve(role: str, config: Optional[dict]) -> Resolved:
    if config is not None:
        agents = config.get("agents", {})
        if role in agents:
            return Resolved(role, agents[role], "config")
        if config.get("default"):
            return Resolved(role, config["default"], "config default")
        return Resolved(role, DEFAULTS["default"], "built-in default")  # type: ignore[arg-type]
    builtin = DEFAULTS["agents"]  # type: ignore[index]
    if role in builtin:
        return Resolved(role, builtin[role], "built-in")  # type: ignore[index]
    return Resolved(role, DEFAULTS["default"], "built-in default")  # type: ignore[arg-type]


def unknown_roles(config: Optional[dict], roles: List[str]) -> List[str]:
    """Config keys that match no installed agent — almost always a typo."""
    if config is None:
        return []
    return sorted(set(config.get("agents", {})) - set(roles))


def set_model(text: str, model: str) -> Tuple[str, Optional[str]]:
    """Return the agent file text with `model:` set, and the previous value.

    Everything outside that one frontmatter line is kept byte for byte. A
    frontmatter without a `model:` line gets one right after `name:`.
    """
    fm = FRONTMATTER_RE.match(text)
    if not fm:
        raise ValueError("no frontmatter")
    body = fm.group(1)
    found = MODEL_LINE_RE.search(body)
    if found:
        previous = found.group(1)
        if previous == model:
            return text, previous
        new_body = body[: found.start()] + f"model: {model}" + body[found.end() :]
    else:
        previous = None
        name = NAME_LINE_RE.search(body)
        at = name.end() if name else len(body)
        new_body = body[:at] + f"\nmodel: {model}" + body[at:]
    return text[: fm.start(1)] + new_body + text[fm.end(1) :], previous


def write_atomically(path: str, text: str) -> None:
    """Replace the file in one step, so a session starting mid-write never
    loads a half-written agent definition."""
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def apply(root: str, quiet: bool) -> int:
    roles = installed_roles(root)
    try:
        config = load_config(root)
    except ConfigError as exc:
        print(f"ERROR={exc}")
        print(f"[{PREFIX} workflow] agent models not applied — fix the file above.")
        return 2

    changed = []
    for role in roles:
        path = agent_file(root, role)
        model = resolve(role, config).model
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            new_text, previous = set_model(text, model)
            if new_text != text:
                write_atomically(path, new_text)
                changed.append((role, previous, model))
        except ValueError:
            print(f"WARNING={path}: no frontmatter, left alone")
        except (OSError, UnicodeDecodeError) as exc:
            # One unreadable or read-only file must not stop the others, and
            # the hook sends stderr nowhere — so say it on stdout.
            print(f"WARNING={path}: not updated ({exc})")

    for role in unknown_roles(config, roles):
        print(f"WARNING={config_path(root)}: \"agents.{role}\" matches no installed agent (known: {', '.join(roles)})")
    for role, previous, model in changed:
        print(f"{PREFIX}-{role}: {previous or '(none)'} → {model}")
    if changed:
        print(f"[{PREFIX} workflow] {len(changed)} agent model(s) updated from {os.path.relpath(config_path(root), root)}.")
    elif not quiet:
        print(f"[{PREFIX} workflow] agent models already match the config; nothing changed.")
    return 0


def show(root: str) -> int:
    roles = installed_roles(root)
    try:
        config = load_config(root)
    except ConfigError as exc:
        print(f"ERROR={exc}")
        return 2
    path = config_path(root)
    print(f"config: {path} ({'present' if config is not None else 'absent — built-in defaults apply'})")
    if not roles:
        print(f"no {PREFIX}-* agents under {agents_dir(root)}")
        return 0
    width = max(len(f"{PREFIX}-{r}") for r in roles)
    for role in roles:
        res = resolve(role, config)
        print(f"{PREFIX}-{role:<{width - len(PREFIX) - 1}}  {res.model:<12}  {res.source}")
    for role in unknown_roles(config, roles):
        print(f"WARNING=\"agents.{role}\" matches no installed agent")
    return 0


def write_config(root: str, data: dict) -> str:
    path = config_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_atomically(path, json.dumps(data, indent=2) + "\n")
    return path


def init(root: str) -> int:
    path = config_path(root)
    if os.path.isfile(path):
        print(f"kept {path}")
        return 0
    write_config(root, DEFAULTS)
    print(f"wrote {path}")
    return 0


def parse_assignments(assignments: List[str], roles: List[str]) -> Dict[str, Optional[str]]:
    """`role=model` pairs → {role: model}; `default` is a role here and an
    empty model means "drop the override". Any bad pair rejects the lot."""
    parsed: Dict[str, Optional[str]] = {}
    for item in assignments:
        if "=" not in item:
            raise ConfigError(f"{item!r}: expected role=model (e.g. developer=opus)")
        role, model = item.split("=", 1)
        role, model = role.strip(), model.strip()
        if role == "default":
            if not model:
                raise ConfigError('"default" cannot be empty — give it a model or leave it alone')
        elif role not in roles:
            raise ConfigError(f"\"agents.{role}\" matches no installed agent (known: {', '.join(roles)})")
        if model and not MODEL_RE.match(model):
            raise ConfigError(f'"agents.{role}" must be a model alias or id, got {model!r}')
        parsed[role] = model or None
    return parsed


def updated_config(config: Optional[dict], changes: Dict[str, Optional[str]]) -> dict:
    """A new config with the changes applied; the current one is not mutated.
    Without a config file, the built-in defaults are the starting point, so
    `set developer=haiku` on a fresh project keeps the other defaults."""
    base = config if config is not None else DEFAULTS
    agents = dict(base.get("agents", {}))  # type: ignore[union-attr]
    new = {k: v for k, v in base.items() if k != "agents"}  # type: ignore[union-attr]
    for role, model in changes.items():
        if role == "default":
            new["default"] = model
        elif model is None:
            agents.pop(role, None)
        else:
            agents[role] = model
    new["agents"] = agents
    return new


def set_models(root: str, assignments: List[str]) -> int:
    roles = installed_roles(root)
    try:
        config = load_config(root)
        changes = parse_assignments(assignments, roles)
    except ConfigError as exc:
        print(f"ERROR={exc}")
        return 2
    if not changes:
        print("ERROR=nothing to set — give at least one role=model")
        return 2
    path = write_config(root, updated_config(config, changes))
    print(f"wrote {os.path.relpath(path, root)}")
    return apply(root, quiet=False)


def reset(root: str) -> int:
    path = write_config(root, DEFAULTS)
    print(f"wrote {os.path.relpath(path, root)} with the built-in defaults")
    return apply(root, quiet=False)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Which Claude model each workflow agent runs on.")
    parser.add_argument("command", choices=["init", "show", "apply", "set", "reset"])
    parser.add_argument("assignments", nargs="*", metavar="role=model", help="set: what to change")
    parser.add_argument("--root", default=os.environ.get("CLAUDE_PROJECT_DIR") or ".", help="project root")
    parser.add_argument("--quiet", action="store_true", help="apply: print only when something changed")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    if args.command == "init":
        return init(root)
    if args.command == "show":
        return show(root)
    if args.command == "set":
        return set_models(root, args.assignments)
    if args.command == "reset":
        return reset(root)
    return apply(root, args.quiet)


if __name__ == "__main__":
    sys.exit(main())
