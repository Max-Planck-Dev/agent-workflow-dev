"""bin/workflow_config.py: profiles, feature switches and agent models, through its CLI."""

import json
import os
import shutil
import subprocess
import tempfile
import unittest

from helpers import ROOT, clean_env, load_module

HELPER = os.path.join(ROOT, "bin", "workflow_config.py")
wc = load_module("workflow_config", HELPER)

AGENT = "---\nname: maxPlanck-{role}\ndescription: x\ntools: Read\nmodel: {model}\n---\n\n# {role}\n"
ROLES = ("product-owner", "ux-designer", "architect", "developer", "code-reviewer", "security",
         "devops", "qa-tester", "scrum-master", "release-manager")


class ConfigCase(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="wc-")
        os.makedirs(os.path.join(self.root, ".claude", "agents"))
        for role in ROLES:
            self.write_agent(role, "sonnet")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write_agent(self, role, model):
        with open(os.path.join(self.root, ".claude", "agents", f"maxPlanck-{role}.md"), "w", encoding="utf-8") as fh:
            fh.write(AGENT.format(role=role, model=model))

    def model_of(self, role):
        with open(os.path.join(self.root, ".claude", "agents", f"maxPlanck-{role}.md"), encoding="utf-8") as fh:
            return wc.MODEL_LINE_RE.search(fh.read()).group(1)

    def run(self, *args, **kw):  # noqa: A003 - unittest's run is not used here
        if args and isinstance(args[0], str):
            out = subprocess.run(["python3", "-I", HELPER, *args, "--root", self.root],
                                 capture_output=True, text=True, env=clean_env(), timeout=30, check=False)
            return out.returncode, out.stdout
        return super().run(*args, **kw)

    def config(self):
        with open(os.path.join(self.root, ".claude", "maxPlanck-config.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def kv(self, text):
        return dict(line.split("=", 1) for line in text.splitlines() if "=" in line)


class DefaultProfileTests(ConfigCase):
    def test_no_config_file_means_the_default_profile(self):
        code, out = self.run("features")
        self.assertEqual(code, 0)
        kv = self.kv(out)
        self.assertEqual(kv["PROFILE"], "default")
        self.assertEqual(kv["ORDER"], "kickoff ux design develop review audit infra test sprint")
        self.assertEqual(kv["CHANGE_ORDER"], "kickoff design develop review audit test sprint")
        self.assertEqual(kv["PER_STORY"], "")
        for name in wc.FEATURES:
            self.assertEqual(kv[name], "off", name)

    def test_init_creates_the_default_config_once(self):
        code, out = self.run("init")
        self.assertEqual(code, 0)
        self.assertEqual(self.config(), {"profile": "default"})
        code, out = self.run("init")
        self.assertIn("kept", out)

    def test_apply_on_default_rewrites_nothing(self):
        self.run("init")
        code, out = self.run("apply", "--quiet")
        self.assertEqual((code, out), (0, ""))
        self.assertEqual(self.model_of("architect"), "sonnet")

    def test_the_default_profile_is_every_switch_off_and_sonnet(self):
        preset = wc.PROFILES["default"]
        self.assertFalse(any(preset["features"].values()))
        self.assertEqual(preset["models"], {"default": "sonnet", "agents": {}})


class NachoProfileTests(ConfigCase):
    def test_profile_nacho_turns_on_every_switch_and_adds_the_phases(self):
        code, out = self.run("profile", "nacho")
        self.assertEqual(code, 0, out)
        self.assertIn("NOTICE=", out)
        kv = self.kv(self.run("features")[1])
        self.assertEqual(kv["ORDER"], "kickoff ux design design-review plan plan-review develop review gate audit infra test sprint")
        self.assertEqual(kv["CHANGE_ORDER"], "kickoff design design-review plan plan-review develop review gate audit test sprint")
        self.assertEqual(kv["PER_STORY"], "plan plan-review develop review")
        self.assertEqual(kv["codex"], "on")

    def test_profile_nacho_applies_its_models_and_ignores_roles_not_installed(self):
        code, out = self.run("profile", "nacho")
        self.assertEqual(self.model_of("architect"), "fable")
        self.assertEqual(self.model_of("developer"), "opus")
        self.assertEqual(self.model_of("qa-tester"), "sonnet")
        self.assertNotIn("WARNING", out)  # tech-lead etc. are preset entries, not user overrides
        self.assertIn("maxPlanck-architect: sonnet → fable", out)

    def test_switching_profile_drops_overrides_and_says_so(self):
        self.run("set", "developer=haiku")
        code, out = self.run("profile", "nacho")
        self.assertIn("dropped overrides: developer", out)
        self.assertEqual(self.config(), {"profile": "nacho"})

    def test_unknown_profile_is_refused(self):
        code, out = self.run("profile", "brian")
        self.assertEqual(code, 2)
        self.assertIn("ERROR=unknown profile", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".claude", "maxPlanck-config.json")))


class SetTests(ConfigCase):
    def test_a_feature_override_is_recorded_and_read_back(self):
        code, out = self.run("set", "design-review=on")
        self.assertEqual(code, 0, out)
        self.assertEqual(self.config(), {"profile": "default", "features": {"design-review": True}})
        kv = self.kv(self.run("features")[1])
        self.assertEqual(kv["ORDER"], "kickoff ux design design-review develop review audit infra test sprint")

    def test_an_override_equal_to_the_profile_value_is_dropped(self):
        self.run("set", "design-review=on")
        self.run("set", "design-review=off")
        self.assertEqual(self.config(), {"profile": "default"})
        self.run("set", "design-review=on")
        self.run("set", "design-review=")
        self.assertEqual(self.config(), {"profile": "default"})

    def test_requirements_are_enforced_and_nothing_is_written_on_error(self):
        code, out = self.run("set", "story-loop=on")
        self.assertEqual(code, 2)
        self.assertIn("ERROR=story-loop=on needs plan=on", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".claude", "maxPlanck-config.json")))
        code, out = self.run("set", "story-loop=on", "plan=on")
        self.assertEqual(code, 0, out)

    def test_models_override_resolution_order(self):
        self.run("set", "developer=opus", "default=haiku")
        self.assertEqual(self.model_of("developer"), "opus")
        self.assertEqual(self.model_of("qa-tester"), "haiku")
        self.run("set", "developer=")
        self.assertEqual(self.model_of("developer"), "haiku")
        self.assertEqual(self.config(), {"profile": "default", "models": {"default": "haiku"}})

    def test_bad_assignments_reject_the_whole_set(self):
        for bad in ("developer=op us", "tech-lead=opus", "design-review=maybe", "nonsense", "default="):
            code, out = self.run("set", "developer=opus", bad)
            self.assertEqual(code, 2, bad)
            self.assertIn("ERROR=", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, ".claude", "maxPlanck-config.json")))
        self.assertEqual(self.model_of("developer"), "sonnet")

    def test_turning_codex_on_prints_the_notice(self):
        code, out = self.run("set", "codex=on")
        self.assertIn("NOTICE=", out)
        code, out = self.run("set", "codex=off")
        self.assertNotIn("NOTICE=", out)


class ApplyAndShowTests(ConfigCase):
    def test_apply_is_idempotent_and_quiet_when_nothing_changed(self):
        self.run("set", "developer=opus")
        code, out = self.run("apply", "--quiet")
        self.assertEqual((code, out), (0, ""))
        self.write_agent("developer", "sonnet")
        code, out = self.run("apply", "--quiet")
        self.assertIn("maxPlanck-developer: sonnet → opus", out)
        self.assertEqual(self.model_of("developer"), "opus")

    def test_apply_keeps_everything_but_the_model_line(self):
        self.run("set", "developer=opus")
        with open(os.path.join(self.root, ".claude", "agents", "maxPlanck-developer.md"), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), AGENT.format(role="developer", model="opus"))

    def test_corrupt_config_is_an_error_that_writes_nothing(self):
        with open(os.path.join(self.root, ".claude", "maxPlanck-config.json"), "w", encoding="utf-8") as fh:
            fh.write("{not json")
        for cmd in (("apply",), ("features",), ("show",), ("set", "developer=opus")):
            code, out = self.run(*cmd)
            self.assertEqual(code, 2, cmd)
            self.assertIn("ERROR=", out)
        self.assertEqual(self.model_of("developer"), "sonnet")

    def test_show_names_the_source_of_every_value(self):
        self.run("set", "developer=opus", "design-review=on")
        code, out = self.run("show")
        self.assertEqual(code, 0)
        self.assertRegex(out, r"design-review\s+on\s+override")
        self.assertRegex(out, r"codex\s+off\s+profile default")
        self.assertRegex(out, r"maxPlanck-developer\s+opus\s+override")
        self.assertRegex(out, r"maxPlanck-qa-tester\s+sonnet\s+profile default \(default\)")

    def test_reset_drops_overrides_but_keeps_the_profile(self):
        self.run("profile", "nacho")
        self.run("set", "developer=haiku")
        code, out = self.run("reset")
        self.assertEqual(self.config(), {"profile": "nacho"})
        self.assertEqual(self.model_of("developer"), "opus")


class InstallerTests(unittest.TestCase):
    """setup.sh installs the helper, writes the profile and applies the models."""

    def setUp(self):
        if shutil.which("git") is None or shutil.which("bash") is None:
            self.skipTest("git and bash are needed to run setup.sh")
        self.target = tempfile.mkdtemp(prefix="wc-install-")

    def tearDown(self):
        shutil.rmtree(self.target, ignore_errors=True)

    def install(self, *flags):
        out = subprocess.run(["bash", os.path.join(ROOT, "setup.sh"), *flags, self.target],
                             capture_output=True, text=True, timeout=120, check=False)
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        return out.stdout

    def read(self, rel):
        with open(os.path.join(self.target, rel), encoding="utf-8") as fh:
            return fh.read()

    def test_default_install_writes_the_default_profile_and_the_hook(self):
        out = self.install()
        self.assertEqual(json.loads(self.read(".claude/maxPlanck-config.json")), {"profile": "default"})
        self.assertTrue(os.path.isfile(os.path.join(self.target, ".claude", "bin", "maxPlanck-config.py")))
        self.assertIn("apply-workflow-config.sh", self.read(".claude/settings.json"))
        self.assertIn("model: sonnet", self.read(".claude/agents/maxPlanck-architect.md"))
        self.assertNotIn("NOTICE", out)

    def test_profile_nacho_install_applies_models_and_warns_about_codex(self):
        out = self.install("--profile", "nacho")
        self.assertEqual(json.loads(self.read(".claude/maxPlanck-config.json")), {"profile": "nacho"})
        self.assertIn("model: fable", self.read(".claude/agents/maxPlanck-architect.md"))
        self.assertIn("model: opus", self.read(".claude/agents/maxPlanck-developer.md"))
        self.assertIn("sent to that service", out)

    def test_reinstall_keeps_the_chosen_profile(self):
        self.install("--profile", "nacho")
        self.install()
        self.assertEqual(json.loads(self.read(".claude/maxPlanck-config.json")), {"profile": "nacho"})
        self.assertIn("model: fable", self.read(".claude/agents/maxPlanck-architect.md"))

    def test_rebranded_install_leaves_no_source_prefix(self):
        self.install("--prefix", "acme", "--profile", "nacho")
        self.assertTrue(os.path.isfile(os.path.join(self.target, ".claude", "acme-config.json")))
        hits = subprocess.run(["grep", "-rl", "maxPlanck", os.path.join(self.target, ".claude")],
                              capture_output=True, text=True, check=False).stdout
        self.assertEqual(hits, "")
        self.assertIn("model: fable", self.read(".claude/agents/acme-architect.md"))

    def test_unknown_profile_fails_before_installing(self):
        out = subprocess.run(["bash", os.path.join(ROOT, "setup.sh"), "--profile", "brian", self.target],
                             capture_output=True, text=True, timeout=120, check=False)
        self.assertNotEqual(out.returncode, 0)
        self.assertFalse(os.path.exists(os.path.join(self.target, ".claude")))


if __name__ == "__main__":
    unittest.main()
