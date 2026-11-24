"""The work-column skill: an opt-in orchestrator over the existing pipeline."""

import os
import re
import unittest

from helpers import ROOT

SKILL = os.path.join(ROOT, ".claude", "skills", "maxPlanck-work-column", "SKILL.md")


class WorkColumnSkillTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with open(SKILL, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.frontmatter = cls.text.split("---", 2)[1]

    def test_runs_in_the_main_context_like_the_other_orchestrators(self):
        self.assertNotIn("context:", self.frontmatter)
        self.assertNotIn("agent:", self.frontmatter)
        self.assertIn("Agent: orchestrator", self.text)

    def test_delegates_the_work_to_the_existing_orchestrators(self):
        for skill in ("/maxPlanck-change", "/maxPlanck-feeling-lucky"):
            self.assertIn(skill, self.text)

    def test_does_nothing_without_the_project_opting_in(self):
        # CONTRIBUTING.md rule 3: nothing reaches Trello until --setup wrote the file.
        self.assertIn(".claude/maxPlanck-trello.json", self.text)
        self.assertIn("Without the file the skill does nothing", self.text)

    def test_carries_no_board_of_its_own(self):
        self.assertIsNone(re.search(r"ari:cloud:trello::\w+/workspace/[0-9a-f]{24}", self.text))
        self.assertIsNone(re.search(r"trello\.com/[bc]/[A-Za-z0-9]{8}\b", self.text))

    def test_verifies_with_the_components_own_commands(self):
        self.assertIn("## Build & Run Commands", self.text)
        self.assertIn("## Components", self.text)

    def test_never_commits_without_the_flag(self):
        self.assertIn("Without `--pr`", self.text)
        self.assertIn("Nothing committed or pushed without `--pr`", self.text)

    def test_fix_rounds_are_bounded(self):
        self.assertIn("three rounds at most", self.text)

    def test_logs_only_with_the_fixed_vocabulary(self):
        actions = set(re.findall(r"\] ([A-Z]+) \| Agent: orchestrator", self.text))
        self.assertTrue(actions)
        self.assertLessEqual(actions, {"ACTION", "DECISION", "VERDICT", "PROGRESS", "PIPELINE"})


if __name__ == "__main__":
    unittest.main()
