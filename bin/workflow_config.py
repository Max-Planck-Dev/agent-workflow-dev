#!/usr/bin/env python3
"""Workflow profile and configuration for an installed project.

A project chooses a *profile* — a named preset of feature switches and agent
models — and records only what it overrides, in `.claude/maxPlanck-config.json`:

    { "profile": "nacho",
      "features": { "codex": false },
      "models": { "default": "sonnet", "agents": { "developer": "sonnet" } } }

A fresh default install is `{"profile": "default"}`. Everything not in the
file resolves from the preset, so a project on a profile gains that profile's
new features when the workflow is updated, while a project on `default` never
gains anything. `default` is the ten-agent pipeline exactly as documented.

Feature switches gate what the orchestrators run (design review, plan phase,
per-story loop, integration gate, design system at kickoff) and whether a
review may use the OpenAI Codex CLI. Agent models are written into the
`model:` line of the installed agent files — Claude Code reads a subagent's
model from nowhere else — at install time and at every session start.

Commands (all take --root, default $CLAUDE_PROJECT_DIR or the cwd):

    features            KEY=value lines: PROFILE, ORDER, CHANGE_ORDER, PER_STORY,
                        and one line per switch. What the orchestrators read.
    show                table of every switch and agent model with its source
    profiles            the known profile names, one per line
    init [--profile P]  create the config (default profile) if absent; with
                        --profile, write that profile and drop every override
    profile P           same as init --profile P, then apply
    set k=v ...         feature=on|off, default=<model>, <role>=<model>; an
                        empty value drops the override. Nothing is written
                        when any assignment is bad. Then apply.
    reset               drop every override of the current profile, then apply
    apply [--quiet]     rewrite the model: line of every installed agent file;
                        idempotent. --quiet prints only when a file changed or
                        the config is unusable (what the session-start hook wants)

Exit status: 0 on success, 2 when the config cannot be read or an assignment
is invalid — the offending line starts with `ERROR=`. Standard library only.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

# Rewritten to the chosen prefix by setup.sh, like every other workflow file.
PREFIX = "maxPlanck"

FEATURES = ("design-system", "design-review", "plan", "plan-review", "story-loop", "integration-gate", "codex")
REQUIRES = {"plan-review": ("plan",), "story-loop": ("plan",)}
# Switches that let project material reach a third-party service. Turning one
# on is the project's explicit consent (CONTRIBUTING.md rule 3).
EXTERNAL = ("codex",)

PROFILES: Dict[str, dict] = {
    # Brian's pipeline, byte for byte: ten agents, no extra phase, sonnet everywhere.
    "default": {
        "features": {f: False for f in FEATURES},
        "models": {"default": "sonnet", "agents": {}},
    },
    # Nacho's setup: every phase he added, Codex reviews, his model choices.
    "nacho": {
        "features": {f: True for f in FEATURES},
        "models": {"default": "sonnet", "agents": {
            "architect": "fable", "tech-lead": "fable",
            "developer": "opus", "design-reviewer": "opus", "plan-reviewer": "opus",
            "code-reviewer": "opus", "security": "opus", "devops": "opus",
        }},
    },
}

# An alias or a model id — including `opus[1m]`, Bedrock ARNs and Vertex ids:
# anything without whitespace that cannot break the YAML line.
MODEL_RE = re.compile(r"^[^\s\"'#]\S*\Z")
ROLE_RE = re.compile(r"^[a-z][a-z0-9-]*$")
FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
MODEL_LINE_RE = re.compile(r"^model:[ \t]*(.*?)[ \t]*$", re.M)
NAME_LINE_RE = re.compile(r"^name:.*$", re.M)
TRUE = ("on", "true", "yes", "1")
FALSE = ("off", "false", "no", "0")


class ConfigError(Exception):
    pass


# ── Files ────────────────────────────────────────────────


def config_path(root: str) -> str:
    return os.path.join(root, ".claude", f"{PREFIX}-config.json")


def agents_dir(root: str) -> str:
    return os.path.join(root, ".claude", "agents")


def installed_roles(root: str) -> List[str]:
    directory = agents_dir(root)
    if not os.path.isdir(directory):
        return []
    head = f"{PREFIX}-"
    return sorted(n[len(head):-3] for n in os.listdir(directory) if n.startswith(head) and n.endswith(".md"))


def agent_file(root: str, role: str) -> str:
    return os.path.join(agents_dir(root), f"{PREFIX}-{role}.md")


def write_atomically(path: str, text: str) -> None:
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def write_config(root: str, data: dict) -> str:
    path = config_path(root)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    write_atomically(path, json.dumps(data, indent=2) + "\n")
    return path


def load_config(root: str) -> dict:
    """The project's config, validated; `{"profile": "default"}` when absent."""
    path = config_path(root)
    if not os.path.isfile(path):
        return {"profile": "default"}
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError) as exc:
        raise ConfigError(f"{path}: {exc}") from exc
    validate(data, path)
    return data


def validate(data: object, path: str) -> None:
    if not isinstance(data, dict):
        raise ConfigError(f"{path}: top level must be an object")
    profile = data.get("profile", "default")
    if profile not in PROFILES:
        raise ConfigError(f"{path}: unknown profile {profile!r} (known: {', '.join(PROFILES)})")
    features = data.get("features", {})
    if not isinstance(features, dict):
        raise ConfigError(f'{path}: "features" must be an object of switch → true/false')
    for name, value in features.items():
        if name not in FEATURES:
            raise ConfigError(f'{path}: unknown feature {name!r} (known: {", ".join(FEATURES)})')
        if not isinstance(value, bool):
            raise ConfigError(f'{path}: "features.{name}" must be true or false')
    models = data.get("models", {})
    if not isinstance(models, dict):
        raise ConfigError(f'{path}: "models" must be an object')
    agents = models.get("agents", {})
    if not isinstance(agents, dict):
        raise ConfigError(f'{path}: "models.agents" must be an object of role → model')
    for role, model in agents.items():
        if not ROLE_RE.match(role) or not isinstance(model, str) or not MODEL_RE.match(model):
            raise ConfigError(f'{path}: "models.agents.{role}" must be a model alias or id, got {model!r}')
    default = models.get("default")
    if default is not None and (not isinstance(default, str) or not MODEL_RE.match(default)):
        raise ConfigError(f'{path}: "models.default" must be a model alias or id, got {default!r}')


# ── Resolution ───────────────────────────────────────────


def profile_of(config: dict) -> str:
    return config.get("profile", "default")


def feature(config: dict, name: str) -> Tuple[bool, str]:
    """(value, source) — source is 'override' or 'profile <name>'."""
    overrides = config.get("features", {})
    if name in overrides:
        return overrides[name], "override"
    return PROFILES[profile_of(config)]["features"][name], f"profile {profile_of(config)}"


def features(config: dict) -> Dict[str, bool]:
    return {name: feature(config, name)[0] for name in FEATURES}


def model(config: dict, role: str) -> Tuple[str, str]:
    """Role override > profile's agent entry > default override > profile default."""
    preset = PROFILES[profile_of(config)]["models"]
    models = config.get("models", {})
    agents = models.get("agents", {})
    if role in agents:
        return agents[role], "override"
    if role in preset["agents"]:
        return preset["agents"][role], f"profile {profile_of(config)}"
    if models.get("default"):
        return models["default"], "override (default)"
    return preset["default"], f"profile {profile_of(config)} (default)"


def unmet(flags: Dict[str, bool]) -> List[str]:
    return [f"{name}=on needs {need}=on" for name, needs in REQUIRES.items() if flags[name]
            for need in needs if not flags[need]]


def order(flags: Dict[str, bool]) -> Tuple[List[str], List[str], List[str]]:
    """(full pipeline order, change-request order, per-story loop) for these switches."""
    loop = ["plan"] + (["plan-review"] if flags["plan-review"] else []) + ["develop", "review"] if flags["plan"] else ["develop", "review"]
    gate = ["gate"] if flags["integration-gate"] else []
    review = ["design-review"] if flags["design-review"] else []
    full = ["kickoff", "ux", "design"] + review + loop + gate + ["audit", "infra", "test", "sprint"]
    change = ["kickoff", "design"] + review + loop + gate + ["audit", "test", "sprint"]
    per_story = loop if flags["story-loop"] else []
    return full, change, per_story


# ── Commands ─────────────────────────────────────────────


def cmd_features(root: str) -> int:
    config = load_config(root)
    flags = features(config)
    full, change, per_story = order(flags)
    print(f"PROFILE={profile_of(config)}")
    print(f"ORDER={' '.join(full)}")
    print(f"CHANGE_ORDER={' '.join(change)}")
    print(f"PER_STORY={' '.join(per_story)}")
    for name in FEATURES:
        print(f"{name}={'on' if flags[name] else 'off'}")
    return 0


def cmd_show(root: str) -> int:
    config = load_config(root)
    path = config_path(root)
    print(f"config: {path} ({'present' if os.path.isfile(path) else 'absent — profile default'})")
    print(f"profile: {profile_of(config)}")
    print()
    print("feature            value  source")
    for name in FEATURES:
        value, source = feature(config, name)
        print(f"{name:<18} {'on' if value else 'off':<6} {source}")
    for problem in unmet(features(config)):
        print(f"WARNING={problem}")
    roles = installed_roles(root)
    print()
    if not roles:
        print(f"agents: none installed under {agents_dir(root)}")
        return 0
    width = max(len(f"{PREFIX}-{r}") for r in roles)
    print(f"{'agent':<{width}}  model         source")
    for role in roles:
        value, source = model(config, role)
        print(f"{PREFIX + '-' + role:<{width}}  {value:<12}  {source}")
    return 0


def cmd_profiles() -> int:
    for name in PROFILES:
        print(name)
    return 0


def notice(config: dict) -> None:
    on = [name for name in EXTERNAL if feature(config, name)[0]]
    if on:
        print(f"NOTICE=profile {profile_of(config)} turns on {', '.join(on)}: design documents and in-scope code "
              "are sent to that service through this project's own login when a review runs.")


def set_profile(root: str, name: str, replace: bool) -> int:
    if name not in PROFILES:
        print(f"ERROR=unknown profile {name!r} (known: {', '.join(PROFILES)})")
        return 2
    path = config_path(root)
    if os.path.isfile(path) and not replace:
        print(f"kept {path}")
        return 0
    dropped: List[str] = []
    if os.path.isfile(path):
        try:
            current = load_config(root)
        except ConfigError:
            current = {}
        dropped = sorted(current.get("features", {})) + sorted(current.get("models", {}).get("agents", {}))
        if current.get("models", {}).get("default"):
            dropped.append("default")
    write_config(root, {"profile": name})
    print(f"wrote {os.path.relpath(path, root)} (profile {name})")
    if dropped:
        print(f"dropped overrides: {', '.join(dropped)}")
    notice({"profile": name})
    return 0


def cmd_init(root: str, profile: Optional[str]) -> int:
    return set_profile(root, profile or "default", replace=profile is not None)


def cmd_profile(root: str, name: str) -> int:
    status = set_profile(root, name, replace=True)
    return status or apply(root, quiet=False)


def cmd_reset(root: str) -> int:
    try:
        config = load_config(root)
    except ConfigError as exc:
        print(f"ERROR={exc}")
        return 2
    return cmd_profile(root, profile_of(config))


def parse_assignments(items: List[str], roles: List[str]) -> Tuple[Dict[str, Optional[bool]], Dict[str, Optional[str]]]:
    """`key=value` pairs → (feature changes, model changes). None drops an override."""
    flags: Dict[str, Optional[bool]] = {}
    models: Dict[str, Optional[str]] = {}
    for item in items:
        if "=" not in item:
            raise ConfigError(f"{item!r}: expected key=value (a feature=on|off, default=<model> or <role>=<model>)")
        key, value = (s.strip() for s in item.split("=", 1))
        if key in FEATURES:
            if not value:
                flags[key] = None
            elif value.lower() in TRUE:
                flags[key] = True
            elif value.lower() in FALSE:
                flags[key] = False
            else:
                raise ConfigError(f"{key}: expected on or off, got {value!r}")
        elif key == "default":
            if not value:
                raise ConfigError("default cannot be empty — give it a model")
            if not MODEL_RE.match(value):
                raise ConfigError(f"default must be a model alias or id, got {value!r}")
            models[key] = value
        elif key in roles:
            if value and not MODEL_RE.match(value):
                raise ConfigError(f"{key} must be a model alias or id, got {value!r}")
            models[key] = value or None
        else:
            raise ConfigError(f"unknown key {key!r} (features: {', '.join(FEATURES)}; roles: {', '.join(roles) or 'none installed'}; default)")
    return flags, models


def updated(config: dict, flags: Dict[str, Optional[bool]], models: Dict[str, Optional[str]]) -> dict:
    """A new config with the changes applied; an override equal to the profile's value is dropped."""
    new = {"profile": profile_of(config)}
    preset = PROFILES[new["profile"]]
    feats = dict(config.get("features", {}))
    for name, value in flags.items():
        if value is None or value == preset["features"][name]:
            feats.pop(name, None)
        else:
            feats[name] = value
    if feats:
        new["features"] = feats
    agents = dict(config.get("models", {}).get("agents", {}))
    default = config.get("models", {}).get("default")
    for role, value in models.items():
        if role == "default":
            default = None if value == preset["models"]["default"] else value
        elif value is None or value == preset["models"]["agents"].get(role):
            agents.pop(role, None)
        else:
            agents[role] = value
    section: dict = {}
    if default:
        section["default"] = default
    if agents:
        section["agents"] = agents
    if section:
        new["models"] = section
    return new


def cmd_set(root: str, items: List[str]) -> int:
    if not items:
        print("ERROR=nothing to set — give at least one key=value")
        return 2
    try:
        config = load_config(root)
        flags, models = parse_assignments(items, installed_roles(root))
        new = updated(config, flags, models)
        problems = unmet(features(new))
        if problems:
            raise ConfigError("; ".join(problems))
    except ConfigError as exc:
        print(f"ERROR={exc}")
        return 2
    path = write_config(root, new)
    print(f"wrote {os.path.relpath(path, root)}")
    for name in sorted(flags):
        value, source = feature(new, name)
        print(f"{name}={'on' if value else 'off'} ({source})")
    notice(new)
    return apply(root, quiet=False)


def set_model_line(text: str, value: str) -> Tuple[str, Optional[str]]:
    """The agent file with `model:` set, and the previous value. Everything else is kept byte for byte."""
    fm = FRONTMATTER_RE.match(text)
    if not fm:
        raise ValueError("no frontmatter")
    body = fm.group(1)
    found = MODEL_LINE_RE.search(body)
    if found:
        previous = found.group(1)
        if previous == value:
            return text, previous
        new_body = body[:found.start()] + f"model: {value}" + body[found.end():]
    else:
        previous = None
        name = NAME_LINE_RE.search(body)
        at = name.end() if name else len(body)
        new_body = body[:at] + f"\nmodel: {value}" + body[at:]
    return text[:fm.start(1)] + new_body + text[fm.end(1):], previous


def apply(root: str, quiet: bool) -> int:
    try:
        config = load_config(root)
    except ConfigError as exc:
        print(f"ERROR={exc}")
        print(f"[{PREFIX} workflow] configuration not applied — fix the file above.")
        return 2
    roles = installed_roles(root)
    changed = []
    for role in roles:
        path = agent_file(root, role)
        wanted = model(config, role)[0]
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            new_text, previous = set_model_line(text, wanted)
            if new_text != text:
                write_atomically(path, new_text)
                changed.append((role, previous, wanted))
        except ValueError:
            print(f"WARNING={path}: no frontmatter, left alone")
        except (OSError, UnicodeDecodeError) as exc:
            print(f"WARNING={path}: not updated ({exc})")
    for role in sorted(set(config.get("models", {}).get("agents", {})) - set(roles)):
        print(f"WARNING={os.path.relpath(config_path(root), root)}: \"models.agents.{role}\" matches no installed agent")
    for problem in unmet(features(config)):
        print(f"WARNING={problem}")
    for role, previous, wanted in changed:
        print(f"{PREFIX}-{role}: {previous or '(none)'} → {wanted}")
    if changed:
        print(f"[{PREFIX} workflow] {len(changed)} agent model(s) updated (profile {profile_of(config)}).")
    elif not quiet:
        print(f"[{PREFIX} workflow] agent models already match profile {profile_of(config)}; nothing changed.")
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Workflow profile and configuration for an installed project.")
    parser.add_argument("command", choices=["features", "show", "profiles", "init", "profile", "set", "reset", "apply"])
    parser.add_argument("args", nargs="*", metavar="arg", help="profile: the name; set: key=value pairs")
    parser.add_argument("--root", default=os.environ.get("CLAUDE_PROJECT_DIR") or ".", help="project root")
    parser.add_argument("--profile", default=None, help="init: write this profile, replacing the config")
    parser.add_argument("--quiet", action="store_true", help="apply: print only when something changed")
    args = parser.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        if args.command == "features":
            return cmd_features(root)
        if args.command == "show":
            return cmd_show(root)
        if args.command == "profiles":
            return cmd_profiles()
        if args.command == "init":
            return cmd_init(root, args.profile)
        if args.command == "profile":
            if len(args.args) != 1:
                print("ERROR=profile takes exactly one name")
                return 2
            return cmd_profile(root, args.args[0])
        if args.command == "set":
            return cmd_set(root, args.args)
        if args.command == "reset":
            return cmd_reset(root)
        return apply(root, args.quiet)
    except ConfigError as exc:
        print(f"ERROR={exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
