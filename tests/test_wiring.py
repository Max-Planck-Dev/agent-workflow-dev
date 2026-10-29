"""How the pieces are wired: the config hook, and the repo's own agent files."""

import os
import shutil
import subprocess
import tempfile
import unittest

from helpers import ROOT, clean_env, load_module

load_module("review_rounds", os.path.join(ROOT, "bin", "review_rounds.py"))

HOOK = os.path.join(ROOT, ".claude", "hooks", "apply-workflow-config.sh")
HELPER = os.path.join(ROOT, "bin", "workflow_config.py")
wc = load_module("workflow_config", HELPER)

AGENT = "---\nname: maxPlanck-developer\nmodel: {model}\n---\n"


class ApplyConfigHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="hook-")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        path = os.path.join(self.tmp, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)

    def run_hook(self):
        out = subprocess.run(["bash", HOOK], capture_output=True, text=True,
                             env=clean_env(CLAUDE_PROJECT_DIR=self.tmp), timeout=20)
        self.assertEqual(out.returncode, 0, out.stderr)
        return out.stdout

    def install_helper(self):
        shutil.copy(HELPER, os.path.join(self.tmp, ".claude", "bin", "maxPlanck-config.py")) if os.path.isdir(
            os.path.join(self.tmp, ".claude", "bin")) else (os.makedirs(os.path.join(self.tmp, ".claude", "bin")),
                                                           shutil.copy(HELPER, os.path.join(self.tmp, ".claude", "bin", "maxPlanck-config.py")))

    def test_silent_without_config_or_helper(self):
        self.assertEqual(self.run_hook(), "")
        self.write(".claude/maxPlanck-config.json", '{"profile": "nacho"}')
        self.assertEqual(self.run_hook(), "")  # config but no helper: a plugin install

    def test_applies_the_profile_to_a_stale_agent_file(self):
        self.write(".claude/maxPlanck-config.json", '{"profile": "nacho"}')
        self.write(".claude/agents/maxPlanck-developer.md", AGENT.format(model="sonnet"))
        self.install_helper()
        self.assertIn("maxPlanck-developer: sonnet → opus", self.run_hook())
        with open(os.path.join(self.tmp, ".claude", "agents", "maxPlanck-developer.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), AGENT.format(model="opus"))
        self.assertEqual(self.run_hook(), "")  # second run: nothing to do

    def test_corrupt_config_is_reported_but_never_fails_the_hook(self):
        self.write(".claude/maxPlanck-config.json", "{broken")
        self.write(".claude/agents/maxPlanck-developer.md", AGENT.format(model="sonnet"))
        self.install_helper()
        self.assertIn("ERROR=", self.run_hook())


class SourceRepoTests(unittest.TestCase):
    """The repository itself is the default profile by construction."""

    def test_every_agent_file_carries_the_default_profile_model(self):
        config = {"profile": "default"}
        for role in wc.installed_roles(ROOT):
            with open(wc.agent_file(ROOT, role), encoding="utf-8") as fh:
                line = wc.MODEL_LINE_RE.search(fh.read())
            self.assertIsNotNone(line, role)
            self.assertEqual(line.group(1), wc.model(config, role)[0], role)

    def test_no_installed_config_or_bin_in_the_repository(self):
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".claude", "maxPlanck-config.json")))
        self.assertFalse(os.path.exists(os.path.join(ROOT, ".claude", "bin")))

    def test_settings_json_lists_the_hook(self):
        with open(os.path.join(ROOT, ".claude", "settings.json"), encoding="utf-8") as fh:
            self.assertIn("apply-workflow-config.sh", fh.read())

    def test_profiles_are_well_formed(self):
        for name, preset in wc.PROFILES.items():
            self.assertEqual(set(preset["features"]), set(wc.FEATURES), name)
            self.assertFalse(wc.unmet(preset["features"]), name)
            self.assertTrue(wc.MODEL_RE.match(preset["models"]["default"]), name)


if __name__ == "__main__":
    unittest.main()


class DesignSystemWiringTests(unittest.TestCase):
    """The design-system switch: resolved without asking, and read by everyone downstream."""

    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_kickoff_resolves_the_design_system_without_asking(self):
        skill = self.read(".claude/skills/maxPlanck-kickoff/SKILL.md")
        step = skill[skill.index("**Settle the design system**"):skill.index("**Write or update the PRD**")]
        self.assertIn("Designer's call", step)
        self.assertIn("design-system=", step)
        self.assertNotIn("ask the user", step.lower())
        choices = self.read(".claude/skills/maxPlanck-kickoff/design-system-choices.md")
        self.assertIn("Nobody is asked anything", choices)
        self.assertIn("**Source:** new", choices)

    def test_downstream_readers_know_the_design_system_file(self):
        for rel in (".claude/agents/maxPlanck-ux-designer.md", ".claude/agents/maxPlanck-architect.md",
                    ".claude/agents/maxPlanck-developer.md", ".claude/skills/maxPlanck-ux/SKILL.md",
                    ".claude/skills/maxPlanck-design/SKILL.md", ".claude/skills/maxPlanck-feeling-lucky/SKILL.md"):
            self.assertIn("docs/ux/design-system.md", self.read(rel), rel)

    def test_the_switch_exists_and_is_off_by_default(self):
        self.assertIn("design-system", wc.FEATURES)
        self.assertFalse(wc.PROFILES["default"]["features"]["design-system"])
        self.assertTrue(wc.PROFILES["nacho"]["features"]["design-system"])


class DesignReviewWiringTests(unittest.TestCase):
    """The design-review switch: an agent, a skill, the helper, and the Architect's log."""

    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_skill_is_bound_to_the_reviewer_and_uses_the_helper(self):
        skill = self.read(".claude/skills/maxPlanck-design-review/SKILL.md")
        self.assertIn("agent: maxPlanck-design-reviewer", skill)
        self.assertIn("context: fork", skill)
        self.assertIn("maxPlanck-reviews.py", skill)
        self.assertIn("--kind design", skill)

    def test_architect_rules_in_the_log_the_helper_reads(self):
        agent = self.read(".claude/agents/maxPlanck-architect.md")
        from review_rounds import KINDS  # loaded by test_review_rounds through helpers
        self.assertIn(KINDS["design"]["log_heading"], agent)
        for word in ("ACCEPTED", "PARTIAL", "REJECTED"):
            self.assertIn(word, agent)

    def test_orchestrators_gate_the_phase_on_the_switch(self):
        for rel in (".claude/skills/maxPlanck-feeling-lucky/SKILL.md", ".claude/skills/maxPlanck-change/SKILL.md"):
            text = self.read(rel)
            self.assertIn("design-review", text, rel)
            self.assertIn("open --kind design", text, rel)

    def test_installer_ships_the_helper(self):
        self.assertIn("review_rounds:reviews", self.read("setup.sh"))


class PlanWiringTests(unittest.TestCase):
    """The plan switch: a Tech Lead, a skill, and a Developer that follows the plan."""

    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_skill_is_bound_to_the_tech_lead(self):
        skill = self.read(".claude/skills/maxPlanck-plan/SKILL.md")
        self.assertIn("agent: maxPlanck-tech-lead", skill)
        self.assertIn("context: fork", skill)
        self.assertIn("dev-plan.md", skill)

    def test_developer_and_orchestrators_know_the_plans(self):
        for rel in (".claude/agents/maxPlanck-developer.md", ".claude/skills/maxPlanck-develop/SKILL.md",
                    ".claude/skills/maxPlanck-feeling-lucky/SKILL.md", ".claude/skills/maxPlanck-change/SKILL.md",
                    ".claude/skills/maxPlanck-sprint/SKILL.md"):
            self.assertIn("plan", self.read(rel), rel)
        self.assertIn("maxPlanck-plan all", self.read(".claude/skills/maxPlanck-feeling-lucky/SKILL.md"))

    def test_tech_lead_writes_only_plans(self):
        agent = self.read(".claude/agents/maxPlanck-tech-lead.md")
        self.assertIn("MUST NOT write source code", agent)
        self.assertIn("plans/story-NNN-plan.md", agent)


class PlanReviewWiringTests(unittest.TestCase):
    """The plan-review switch: a Plan Reviewer, a skill, and the Tech Lead's log."""

    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_skill_is_bound_and_uses_the_plan_kind(self):
        skill = self.read(".claude/skills/maxPlanck-plan-review/SKILL.md")
        self.assertIn("agent: maxPlanck-plan-reviewer", skill)
        self.assertIn("--kind plan --story", skill)

    def test_tech_lead_rules_in_the_log_the_helper_reads(self):
        from review_rounds import KINDS
        agent = self.read(".claude/agents/maxPlanck-tech-lead.md")
        self.assertIn(KINDS["plan"]["log_heading"], agent)
        self.assertIn("open --kind plan", agent)

    def test_switch_requires_plan_and_orchestrators_gate_on_it(self):
        self.assertEqual(wc.REQUIRES["plan-review"], ("plan",))
        for rel in (".claude/skills/maxPlanck-feeling-lucky/SKILL.md", ".claude/skills/maxPlanck-change/SKILL.md"):
            self.assertIn("plan-review", self.read(rel), rel)
            self.assertIn("recheck", self.read(rel).lower(), rel)


class StoryLoopWiringTests(unittest.TestCase):
    """The story-loop switch: one story per run, named explicitly by the orchestrators."""

    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_phase_skills_take_a_story_or_all(self):
        for rel in (".claude/skills/maxPlanck-develop/SKILL.md", ".claude/skills/maxPlanck-review/SKILL.md"):
            text = self.read(rel)
            self.assertIn(".current-story", text, rel)
            self.assertIn("`all`", text, rel)
        self.assertIn("`next`", self.read(".claude/skills/maxPlanck-plan/SKILL.md"))
        self.assertIn(".current-story", self.read(".claude/agents/maxPlanck-tech-lead.md"))

    def test_orchestrator_announces_stories_and_names_them(self):
        text = self.read(".claude/skills/maxPlanck-feeling-lucky/SKILL.md")
        self.assertIn("Stories in scope (sprint <NN>)", text)
        self.assertIn("maxPlanck-plan next", text)
        self.assertIn("routing to plan (<S+1>)", text)
        self.assertIn("maxPlanck-develop all", text)
        self.assertIn("story-loop", self.read(".claude/skills/maxPlanck-change/SKILL.md"))

    def test_switch_requires_plan_and_the_helper_lists_the_loop_phases(self):
        self.assertEqual(wc.REQUIRES["story-loop"], ("plan",))
        on = dict(wc.PROFILES["nacho"]["features"])
        self.assertEqual(wc.order(on)[2], ["plan", "plan-review", "develop", "review"])
        on["plan-review"] = False
        self.assertEqual(wc.order(on)[2], ["plan", "develop", "review"])
        self.assertEqual(wc.order(wc.PROFILES["default"]["features"])[2], [])


class IntegrationGateWiringTests(unittest.TestCase):
    """The integration-gate switch: quick checks per story, one build before the audit."""

    def read(self, rel):
        with open(os.path.join(ROOT, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_architect_records_check_lines_and_developer_logs_verdicts(self):
        self.assertIn("- Check:", self.read(".claude/agents/maxPlanck-architect.md"))
        self.assertIn("- Test (focused):", self.read(".claude/agents/maxPlanck-architect.md"))
        self.assertIn("VERDICT | Agent: maxPlanck-developer", self.read(".claude/agents/maxPlanck-developer.md"))
        self.assertIn("Check", self.read(".claude/maxPlanck-default-stack.md"))

    def test_orchestrators_run_the_gate_helper(self):
        for rel in (".claude/skills/maxPlanck-feeling-lucky/SKILL.md", ".claude/skills/maxPlanck-change/SKILL.md"):
            text = self.read(rel)
            self.assertIn("maxPlanck-gate.py run", text, rel)
            self.assertIn("GATE=", text, rel)
        self.assertIn("gate", wc.order(wc.PROFILES["nacho"]["features"])[0])
        self.assertNotIn("gate", wc.order(wc.PROFILES["default"]["features"])[0])
