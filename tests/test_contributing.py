"""The rules in CONTRIBUTING.md that can be checked mechanically.

Each test names the rule it enforces. When the maintainer decides to change the
pipeline, the expected sets below are updated in the same PR — that is the point:
the change is deliberate, never a side effect.
"""

import ast
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest

from helpers import ROOT

AGENTS_DIR = os.path.join(ROOT, ".claude", "agents")
SKILLS_DIR = os.path.join(ROOT, ".claude", "skills")

# Rule 1: the pipeline is complete. These are the agents and skills it has.
EXPECTED_AGENTS = {
    "maxPlanck-product-owner", "maxPlanck-ux-designer", "maxPlanck-architect",
    "maxPlanck-developer", "maxPlanck-code-reviewer", "maxPlanck-security",
    "maxPlanck-devops", "maxPlanck-qa-tester", "maxPlanck-scrum-master",
    "maxPlanck-release-manager",
    "maxPlanck-design-reviewer",  # profile switch design-review
    "maxPlanck-tech-lead",  # profile switch plan
}
EXPECTED_SKILLS = {
    "maxPlanck-kickoff", "maxPlanck-ux", "maxPlanck-design", "maxPlanck-develop",
    "maxPlanck-review", "maxPlanck-audit", "maxPlanck-infra", "maxPlanck-test",
    "maxPlanck-sprint", "maxPlanck-feeling-lucky", "maxPlanck-adopt",
    "maxPlanck-change", "maxPlanck-report", "maxPlanck-config", "maxPlanck-design-review", "maxPlanck-plan",
    "maxPlanck-proposal",  # repo-only: never installed, never in the plugin
}

# Rule 5: working artifacts never land in the repository.
FORBIDDEN_DIRS = (os.path.join(".claude", "PRPs"),)
FORBIDDEN_FILE_PATTERNS = (r"\.codex-review\.md$", r"\.plan\.md$", r"-report\.md$")
IGNORED_DIRS = {".git", "node_modules", "logs", "__pycache__", ".pytest_cache"}

# Rule 8: commits describe the change, not the tooling.
ATTRIBUTION = re.compile(r"co-authored-by:.*(claude|anthropic)|generated with \[?claude|claude\.ai/code", re.I)


def repo_files():
    for base, dirs, files in os.walk(ROOT):
        dirs[:] = [d for d in dirs if d not in IGNORED_DIRS]
        for name in files:
            yield os.path.relpath(os.path.join(base, name), ROOT)


def repo_only_skills():
    return {d for d in os.listdir(SKILLS_DIR) if os.path.isfile(os.path.join(SKILLS_DIR, d, ".repo-only"))}


def read(path):
    with open(os.path.join(ROOT, path), encoding="utf-8") as fh:
        return fh.read()


class ManifestoPresentTests(unittest.TestCase):
    def test_contributing_and_agents_md_exist(self):
        for name in ("CONTRIBUTING.md", "AGENTS.md"):
            self.assertTrue(os.path.isfile(os.path.join(ROOT, name)), name)

    def test_agents_md_points_at_contributing(self):
        self.assertIn("CONTRIBUTING.md", read("AGENTS.md"))

    def test_claude_md_carries_the_rules(self):
        text = read(os.path.join(".claude", "CLAUDE.md"))
        self.assertIn("## Contributing", text)
        self.assertIn("never stops to ask the user", text)


class PipelineIsCompleteTests(unittest.TestCase):
    """Rule 1: no phase, agent or skill appears without the maintainer asking."""

    def test_agent_set_is_exactly_the_documented_ten(self):
        found = {f[:-3] for f in os.listdir(AGENTS_DIR) if f.endswith(".md")}
        self.assertEqual(found, EXPECTED_AGENTS)

    def test_skill_set_is_exactly_the_documented_thirteen(self):
        found = {d for d in os.listdir(SKILLS_DIR) if os.path.isdir(os.path.join(SKILLS_DIR, d))}
        self.assertEqual(found, EXPECTED_SKILLS)

    def test_plugin_registers_the_same_agents(self):
        manifest = read(os.path.join(".claude-plugin", "plugin.json"))
        registered = set(re.findall(r"agents/(maxPlanck-[a-z-]+)\.md", manifest))
        self.assertEqual(registered, EXPECTED_AGENTS)

    def test_plugin_lists_every_project_skill_and_no_repo_only_one(self):
        manifest = read(os.path.join(".claude-plugin", "plugin.json"))
        json.loads(manifest)  # the manifest must stay valid JSON
        listed = set(re.findall(r"skills/(maxPlanck-[a-z-]+)\"", manifest))
        self.assertEqual(listed, EXPECTED_SKILLS - repo_only_skills())


class RepoOnlySkillsTests(unittest.TestCase):
    """A skill with a .repo-only marker improves this repository and is never installed."""

    def test_setup_does_not_install_repo_only_skills(self):
        if shutil.which("git") is None or shutil.which("bash") is None:
            self.skipTest("git and bash are needed to run setup.sh")
        target = tempfile.mkdtemp(prefix="maxplanck-install-")
        try:
            out = subprocess.run(["bash", os.path.join(ROOT, "setup.sh"), target],
                                 capture_output=True, text=True, timeout=120, check=False)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            installed = set(os.listdir(os.path.join(target, ".claude", "skills")))
            self.assertEqual(installed, EXPECTED_SKILLS - repo_only_skills())
        finally:
            shutil.rmtree(target, ignore_errors=True)


class FeelingLuckyIsUnattendedTests(unittest.TestCase):
    """Rule 2: the full-auto run never stops to ask the user anything."""

    def test_no_skill_or_agent_uses_the_question_tool(self):
        offenders = []
        for base in (AGENTS_DIR, SKILLS_DIR):
            for dirpath, _, files in os.walk(base):
                for name in files:
                    path = os.path.join(dirpath, name)
                    with open(path, encoding="utf-8", errors="replace") as fh:
                        if "AskUserQuestion" in fh.read():
                            offenders.append(os.path.relpath(path, ROOT))
        self.assertEqual(offenders, [], "AskUserQuestion is not allowed in any skill or agent")

    def test_feeling_lucky_promises_no_user_input(self):
        text = read(os.path.join(".claude", "skills", "maxPlanck-feeling-lucky", "SKILL.md"))
        self.assertIn("without waiting for user input", text)


class NoWorkingArtifactsTests(unittest.TestCase):
    """Rule 5: plans, PRPs, transcripts and scratch copies are not committed."""

    def test_no_prp_directory(self):
        for rel in FORBIDDEN_DIRS:
            self.assertFalse(os.path.exists(os.path.join(ROOT, rel)), f"{rel} must not exist")

    def test_no_transcripts_plans_or_reports(self):
        offenders = [f for f in repo_files() if any(re.search(p, f) for p in FORBIDDEN_FILE_PATTERNS)]
        self.assertEqual(offenders, [])


class DataStaysLocalTests(unittest.TestCase):
    """Rule 3: an external reviewer is opt-in through a profile or switch; no opt-out file exists."""

    def test_no_opt_out_file_is_mentioned_anywhere(self):
        marker = "no-" + "codex"
        offenders = []
        for rel in repo_files():
            try:
                with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
                    if marker in fh.read():
                        offenders.append(rel)
            except (UnicodeDecodeError, OSError):
                continue
        self.assertEqual(offenders, [], "an opt-out file is not an acceptable consent mechanism")


class NoDuplicatedHelpersTests(unittest.TestCase):
    """Rule 6: shared code lives once under bin/, never copied between skills."""

    @staticmethod
    def functions(path):
        with open(path, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=path)
        return {
            node.name: ast.unparse(node)
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.end_lineno - node.lineno >= 3
        }

    def test_python_helpers_in_skills_share_no_function_bodies(self):
        scripts = [f for f in repo_files() if f.startswith(".claude/skills/") and f.endswith(".py")]
        bodies = {s: self.functions(os.path.join(ROOT, s)) for s in scripts}
        duplicated = []
        for i, a in enumerate(scripts):
            for b in scripts[i + 1:]:
                shared = [n for n in bodies[a] if n in bodies[b] and bodies[a][n] == bodies[b][n]]
                if shared:
                    duplicated.append((a, b, shared))
        self.assertEqual(duplicated, [], "identical functions in two skill helpers belong in bin/")


class CommitsDescribeTheChangeTests(unittest.TestCase):
    """Rule 8: no AI attribution in commit messages."""

    def test_no_attribution_in_reachable_history(self):
        if shutil.which("git") is None or not os.path.isdir(os.path.join(ROOT, ".git")):
            self.skipTest("not a git checkout")
        out = subprocess.run(["git", "-C", ROOT, "log", "--format=%H%x00%B%x1e"],
                             capture_output=True, text=True, check=False)
        if out.returncode != 0:
            self.skipTest("git log unavailable")
        offenders = []
        for entry in out.stdout.split("\x1e"):
            if "\x00" not in entry:
                continue
            sha, body = entry.split("\x00", 1)
            if ATTRIBUTION.search(body):
                offenders.append(sha.strip()[:7])
        self.assertEqual(offenders, [], "commits carry AI attribution")


if __name__ == "__main__":
    unittest.main()
