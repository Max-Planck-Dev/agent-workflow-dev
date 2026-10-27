"""Static wiring checks for the workflow's own files.

Skills, agents, the plugin manifest, the dashboard's role map and the
installer's command list all name each other by hand. A new phase that
misses one of them still "works" until that one path is exercised.
"""

import json
import os
import re
import unittest

from helpers import AGENT_MODELS, ROOT, dashboard, load_module

pd = dashboard()
am = load_module("agent_models", AGENT_MODELS)

PREFIX = "maxPlanck"
AGENTS_DIR = os.path.join(ROOT, ".claude", "agents")
SKILLS_DIR = os.path.join(ROOT, ".claude", "skills")


def frontmatter(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    fields = {}
    for line in (m.group(1).splitlines() if m else []):
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    return fields


def agent_names() -> list:
    return sorted(f[: -len(".md")] for f in os.listdir(AGENTS_DIR) if f.endswith(".md"))


def skill_frontmatters() -> dict:
    return {
        name: frontmatter(os.path.join(SKILLS_DIR, name, "SKILL.md"))
        for name in sorted(os.listdir(SKILLS_DIR))
        if os.path.isfile(os.path.join(SKILLS_DIR, name, "SKILL.md"))
    }


class WiringTests(unittest.TestCase):
    def test_agent_file_name_matches_its_declared_name(self):
        for name in agent_names():
            self.assertEqual(frontmatter(os.path.join(AGENTS_DIR, name + ".md")).get("name"), name)

    def test_skill_directory_matches_its_declared_name(self):
        for name, fields in skill_frontmatters().items():
            self.assertEqual(fields.get("name"), name)

    def test_every_bound_skill_points_at_an_existing_agent(self):
        agents = set(agent_names())
        for name, fields in skill_frontmatters().items():
            if "agent" in fields:
                self.assertIn(fields["agent"], agents, name)

    def test_only_orchestrators_and_config_run_unbound(self):
        # Every phase skill forks into its agent; the orchestrators and the
        # config skill must run in the main context. Nothing else should.
        unbound = {name for name, fields in skill_frontmatters().items() if "agent" not in fields}
        expected = {f"{PREFIX}-{s}" for s in ("feeling-lucky", "adopt", "change", "config")}
        self.assertEqual(unbound, expected)
        for name in unbound:
            self.assertNotIn("context", skill_frontmatters()[name], name)

    def test_skill_and_agent_names_never_collide(self):
        self.assertEqual(set(agent_names()) & set(skill_frontmatters()), set())

    def test_every_agent_is_in_the_plugin_manifest(self):
        with open(os.path.join(ROOT, ".claude-plugin", "plugin.json"), encoding="utf-8") as fh:
            listed = {os.path.basename(p)[: -len(".md")] for p in json.load(fh)["agents"]}
        self.assertEqual(listed, set(agent_names()))

    def test_every_agent_role_maps_to_a_dashboard_phase(self):
        for name in agent_names():
            role = pd.role_of(name)
            self.assertIsNotNone(role, name)
            self.assertEqual(f"{PREFIX}-{role}", name)

    def test_installer_lists_every_user_invocable_skill(self):
        with open(os.path.join(ROOT, "setup.sh"), encoding="utf-8") as fh:
            installer = fh.read()
        for name, fields in skill_frontmatters().items():
            if fields.get("user-invocable") == "true":
                command = "/${PREFIX}-" + name[len(PREFIX) + 1:]
                self.assertRegex(installer, re.escape(command) + r"\s", name)


class AgentModelWiringTests(unittest.TestCase):
    """The agent files in this repo carry the applier's built-in defaults.

    Without this, a default changed in one place and not the other would
    ship two different answers to "which model does the Developer run on".
    """

    def test_every_agent_frontmatter_model_is_the_built_in_default(self):
        for name in agent_names():
            role = name[len(PREFIX) + 1:]
            expected = am.resolve(role, None).model
            self.assertEqual(frontmatter(os.path.join(AGENTS_DIR, name + ".md")).get("model"), expected, name)

    def test_every_built_in_override_names_an_existing_agent(self):
        roles = {name[len(PREFIX) + 1:] for name in agent_names()}
        self.assertLessEqual(set(am.DEFAULTS["agents"]), roles)

    def test_plan_and_develop_default_to_different_models(self):
        self.assertNotEqual(am.resolve("tech-lead", None).model, am.resolve("developer", None).model)

    def test_installer_ships_the_applier_and_its_session_hook(self):
        with open(os.path.join(ROOT, "setup.sh"), encoding="utf-8") as fh:
            installer = fh.read()
        self.assertIn("bin/agent_models.py", installer)
        self.assertIn("apply-agent-models.sh", installer)
        with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as fh:
            commands = [
                h["command"]
                for entry in json.load(fh)["hooks"]["SessionStart"]
                for h in entry["hooks"]
            ]
        self.assertTrue(any("apply-agent-models.sh" in c for c in commands), commands)
        self.assertTrue(os.access(os.path.join(ROOT, ".claude", "hooks", "apply-agent-models.sh"), os.X_OK))


class DesignSystemWiringTests(unittest.TestCase):
    """The kickoff asks the questions, the PRD records them, UX builds the doc."""

    QUESTIONS = os.path.join(SKILLS_DIR, f"{PREFIX}-kickoff", "design-system-questions.md")

    def read(self, *parts: str) -> str:
        with open(os.path.join(ROOT, ".claude", *parts), encoding="utf-8") as fh:
            return fh.read()

    def test_record_table_lists_every_topic_in_order(self):
        with open(self.QUESTIONS, encoding="utf-8") as fh:
            text = fh.read()
        table = text[text.index("## Design System\n"):]
        topics = [t for t in re.findall(r"^\| ([^|]+?) \|", table, re.M) if t != "Topic" and not t.startswith("-")]
        self.assertEqual(topics, [
            "Layout", "Density", "Look & feel", "Primary color", "Theme", "Typography",
            "Component library", "Buttons", "Tables", "Forms & saving", "Feedback", "Devices",
        ])
        self.assertEqual(len(re.findall(r"^## (\d+)\. ", text, re.M)), 12)

    def test_both_askers_point_at_the_questions_file(self):
        self.assertIn("design-system-questions.md", self.read("skills", f"{PREFIX}-kickoff", "SKILL.md"))
        self.assertIn(
            f".claude/skills/{PREFIX}-kickoff/design-system-questions.md",
            self.read("skills", f"{PREFIX}-feeling-lucky", "SKILL.md"),
        )

    def test_the_design_system_doc_is_written_by_ux_and_read_downstream(self):
        for parts in (
            ("agents", f"{PREFIX}-ux-designer.md"),
            ("skills", f"{PREFIX}-ux", "SKILL.md"),
            ("agents", f"{PREFIX}-architect.md"),
            ("agents", f"{PREFIX}-developer.md"),
            ("skills", f"{PREFIX}-review", "code_review.py"),
        ):
            self.assertIn("docs/ux/design-system.md", self.read(*parts), "/".join(parts))
