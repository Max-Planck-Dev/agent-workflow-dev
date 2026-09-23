"""Shared test helpers: import the dashboard module and load fixtures."""

import importlib.util
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
FIXTURES = os.path.join(HERE, "fixtures")
DASHBOARD = os.path.join(ROOT, "bin", "pipeline_dashboard.py")
HOOK_SH = os.path.join(ROOT, ".claude", "hooks", "log-agent-lifecycle.sh")
HOOK_PY = os.path.join(ROOT, ".claude", "hooks", "pipeline-events.py")


def load_module(name: str, path: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def dashboard():
    return load_module("pipeline_dashboard", DASHBOARD)


def fixture_lines(name: str):
    with open(os.path.join(FIXTURES, name), encoding="utf-8") as fh:
        return fh.readlines()


def upto(lines, needle: str):
    """Lines up to and including the first line containing `needle`."""
    for i, line in enumerate(lines):
        if needle in line:
            return lines[: i + 1]
    raise AssertionError(f"needle not found in fixture: {needle!r}")


def clean_env(**overrides):
    """A copy of the environment with every herdr variable removed."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("HERDR_") and not k.startswith("PIPELINE_DASHBOARD_")}
    env.update({k: v for k, v in overrides.items() if v is not None})
    return env
