"""Static wiring checks for the workflow's own files.

Skills, agents, the plugin manifest, the dashboard's role map and the
installer's command list all name each other by hand. A new phase that
misses one of them still "works" until that one path is exercised.
"""

import json
import os
import re
import unittest

from helpers import ROOT, dashboard

pd = dashboard()

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
