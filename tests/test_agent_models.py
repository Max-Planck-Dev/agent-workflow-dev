"""bin/agent_models.py: the per-project agent → model config and its applier."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from helpers import AGENT_MODELS, ROOT, load_module

am = load_module("agent_models", AGENT_MODELS)

AGENT = """---
name: maxPlanck-{role}
description: x
tools: Read
model: {model}
---

# {role}
body
"""

AGENT_WITHOUT_MODEL = """---
name: maxPlanck-{role}
description: x
tools: Read
---

body
"""


def frontmatter_model(path):
    with open(path, encoding="utf-8") as fh:
        for line in fh.read().split("---")[1].splitlines():
            if line.startswith("model:"):
                return line.split(":", 1)[1].strip()
    return None


class Project:
    """A throwaway project with a few installed agents."""

    def __init__(self):
        self.root = tempfile.mkdtemp()
        self.agents = os.path.join(self.root, ".claude", "agents")
        os.makedirs(self.agents)

    def agent(self, role, model="sonnet", template=AGENT):
        path = os.path.join(self.agents, f"maxPlanck-{role}.md")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(template.format(role=role, model=model))
        return path

    def config(self, data):
        path = am.config_path(self.root)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(data if isinstance(data, str) else json.dumps(data))
        return path

    def run(self, *args):
        proc = subprocess.run(
            [sys.executable, AGENT_MODELS, *args, "--root", self.root],
            capture_output=True, text=True,
        )
        return proc.returncode, proc.stdout

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class ResolveTests(unittest.TestCase):
    def test_built_in_defaults_when_there_is_no_config(self):
        self.assertEqual(am.resolve("tech-lead", None).model, "fable")
        self.assertEqual(am.resolve("developer", None).model, "opus")
        self.assertEqual(am.resolve("architect", None).model, "fable")
        self.assertEqual(am.resolve("qa-tester", None), am.Resolved("qa-tester", "sonnet", "built-in default"))

    def test_the_config_file_is_the_whole_answer_once_it_exists(self):
        config = {"default": "haiku", "agents": {"developer": "opus"}}
        self.assertEqual(am.resolve("developer", config).source, "config")
        # tech-lead is not listed: the file's default applies, not the built-in fable.
        self.assertEqual(am.resolve("tech-lead", config), am.Resolved("tech-lead", "haiku", "config default"))

    def test_config_without_default_still_hides_the_built_in_role_defaults(self):
        config = {"agents": {"architect": "opus"}}
        self.assertEqual(am.resolve("architect", config).model, "opus")
        # The file is the whole answer: no fable/opus sneaks in from the built-ins.
        self.assertEqual(am.resolve("tech-lead", config), am.Resolved("tech-lead", "sonnet", "built-in default"))
        self.assertEqual(am.resolve("qa-tester", config).model, "sonnet")

    def test_model_values_only_need_to_be_one_token(self):
        for ok in ("opus", "opus[1m]", "claude-opus-5-5", "inherit",
                   "arn:aws:bedrock:us-east-1:123:inference-profile/us.anthropic.claude-x",
                   "claude-sonnet-5@20260101"):
            self.assertTrue(am.MODEL_RE.match(ok), ok)
        for bad in ("op us", "", '"opus"', "#opus", "opus\n"):
            self.assertFalse(am.MODEL_RE.match(bad), repr(bad))


class SetModelTests(unittest.TestCase):
    def test_rewrites_only_the_model_line(self):
        text = AGENT.format(role="developer", model="sonnet")
        new, previous = am.set_model(text, "opus")
        self.assertEqual(previous, "sonnet")
        self.assertEqual(new, AGENT.format(role="developer", model="opus"))

    def test_is_a_no_op_when_already_set(self):
        text = AGENT.format(role="developer", model="opus")
        self.assertEqual(am.set_model(text, "opus"), (text, "opus"))

    def test_adds_the_line_after_name_when_missing(self):
        new, previous = am.set_model(AGENT_WITHOUT_MODEL.format(role="x"), "fable")
        self.assertIsNone(previous)
        self.assertIn("name: maxPlanck-x\nmodel: fable\ndescription: x\n", new)

    def test_refuses_a_file_without_frontmatter(self):
        with self.assertRaises(ValueError):
            am.set_model("# no frontmatter\n", "opus")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.cleanup)
        self.dev = self.p.agent("developer")
        self.lead = self.p.agent("tech-lead")
        self.arch = self.p.agent("architect")

    def test_init_writes_the_defaults_once(self):
        code, out = self.p.run("init")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("wrote "))
        with open(am.config_path(self.p.root), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), am.DEFAULTS)
        self.p.config({"default": "haiku"})
        code, out = self.p.run("init")
        self.assertEqual(code, 0)
        self.assertTrue(out.startswith("kept "))
        with open(am.config_path(self.p.root), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh), {"default": "haiku"})

    def test_apply_without_config_writes_the_built_in_defaults(self):
        code, out = self.p.run("apply")
        self.assertEqual(code, 0)
        self.assertEqual(frontmatter_model(self.dev), "opus")
        self.assertEqual(frontmatter_model(self.lead), "fable")
        self.assertEqual(frontmatter_model(self.arch), "fable")
        self.assertIn("maxPlanck-developer: sonnet → opus", out)
        self.assertIn("3 agent model(s) updated", out)

    def test_apply_is_idempotent_and_quiet_when_nothing_changes(self):
        self.p.run("apply")
        code, out = self.p.run("apply", "--quiet")
        self.assertEqual((code, out), (0, ""))
        code, out = self.p.run("apply")
        self.assertEqual(code, 0)
        self.assertIn("nothing changed", out)

    def test_apply_follows_the_config(self):
        self.p.config({"default": "haiku", "agents": {"developer": "claude-opus-5-5"}})
        code, _ = self.p.run("apply")
        self.assertEqual(code, 0)
        self.assertEqual(frontmatter_model(self.dev), "claude-opus-5-5")
        self.assertEqual(frontmatter_model(self.lead), "haiku")
        self.assertEqual(frontmatter_model(self.arch), "haiku")

    def test_apply_leaves_the_rest_of_the_file_alone(self):
        with open(self.dev, encoding="utf-8") as fh:
            before = fh.read()
        self.p.run("apply")
        with open(self.dev, encoding="utf-8") as fh:
            after = fh.read()
        self.assertEqual(after.replace("model: opus", "model: sonnet"), before)

    def test_apply_warns_about_a_role_that_matches_no_agent(self):
        self.p.config({"agents": {"developr": "opus"}})
        code, out = self.p.run("apply", "--quiet")
        self.assertEqual(code, 0)
        self.assertIn('"agents.developr" matches no installed agent', out)
        self.assertIn("known: architect, developer, tech-lead", out)

    def test_broken_config_is_reported_and_nothing_is_written(self):
        self.p.config("{not json")
        code, out = self.p.run("apply", "--quiet")
        self.assertEqual(code, 2)
        self.assertTrue(out.startswith("ERROR="), out)
        self.assertEqual(frontmatter_model(self.dev), "sonnet")
        self.p.config({"agents": {"developer": "op us"}})
        code, out = self.p.run("apply")
        self.assertEqual(code, 2)
        self.assertIn('"agents.developer" must be a model alias or id', out)

    def test_show_names_the_source_of_every_value(self):
        self.p.config({"agents": {"architect": "opus"}})
        code, out = self.p.run("show")
        self.assertEqual(code, 0)
        self.assertIn("(present)", out)
        self.assertRegex(out, r"maxPlanck-architect\s+opus\s+config\n")
        self.assertRegex(out, r"maxPlanck-tech-lead\s+sonnet\s+built-in default\n")
        self.assertRegex(out, r"maxPlanck-developer\s+sonnet\s+built-in default\n")
        os.unlink(am.config_path(self.p.root))
        code, out = self.p.run("show")
        self.assertIn("(absent", out)
        self.assertRegex(out, r"maxPlanck-tech-lead\s+fable\s+built-in\n")

    def test_one_unwritable_agent_does_not_stop_the_others(self):
        os.chmod(self.p.agents, 0o555)  # directory read-only: os.replace fails
        self.addCleanup(os.chmod, self.p.agents, 0o755)
        code, out = self.p.run("apply", "--quiet")
        self.assertEqual(code, 0)
        self.assertEqual(out.count("WARNING="), 3, out)  # developer, tech-lead and architect all change
        self.assertIn("maxPlanck-developer.md: not updated", out)
        self.assertEqual(frontmatter_model(self.dev), "sonnet")
        self.assertEqual(os.listdir(self.p.agents).count("maxPlanck-developer.md"), 1)
        self.assertFalse([f for f in os.listdir(self.p.agents) if f.endswith(".tmp")])


class SetTests(unittest.TestCase):
    """`set role=model …` is what /maxPlanck-config runs: it edits the config
    and applies it in one step, so the agent files never lag the file."""

    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.cleanup)
        self.dev = self.p.agent("developer")
        self.lead = self.p.agent("tech-lead")
        self.arch = self.p.agent("architect")

    def read_config(self):
        with open(am.config_path(self.p.root), encoding="utf-8") as fh:
            return json.load(fh)

    def test_set_creates_the_config_from_the_defaults_and_applies(self):
        code, out = self.p.run("set", "developer=haiku")
        self.assertEqual(code, 0)
        config = self.read_config()
        self.assertEqual(config["default"], am.DEFAULTS["default"])
        self.assertEqual(config["agents"]["developer"], "haiku")
        self.assertEqual(config["agents"]["tech-lead"], "fable")  # the rest of the defaults came along
        self.assertEqual(frontmatter_model(self.dev), "haiku")
        self.assertEqual(frontmatter_model(self.lead), "fable")
        self.assertIn("maxPlanck-developer: sonnet → haiku", out)

    def test_set_edits_an_existing_config_in_place_and_keeps_other_keys(self):
        self.p.config({"default": "haiku", "agents": {"developer": "opus"}, "note": "mine"})
        code, out = self.p.run("set", "tech-lead=fable", "default=sonnet")
        self.assertEqual(code, 0)
        self.assertEqual(self.read_config(), {
            "default": "sonnet", "agents": {"developer": "opus", "tech-lead": "fable"}, "note": "mine",
        })
        self.assertEqual(frontmatter_model(self.arch), "sonnet")
        self.assertEqual(frontmatter_model(self.lead), "fable")
        self.assertEqual(frontmatter_model(self.dev), "opus")

    def test_set_with_an_empty_value_drops_the_override(self):
        self.p.config({"default": "haiku", "agents": {"developer": "opus"}})
        code, _ = self.p.run("set", "developer=")
        self.assertEqual(code, 0)
        self.assertEqual(self.read_config()["agents"], {})
        self.assertEqual(frontmatter_model(self.dev), "haiku")

    def test_set_rejects_bad_input_and_writes_nothing(self):
        self.p.config({"agents": {"developer": "opus"}})
        for args, message in (
            (("developr=haiku",), "matches no installed agent"),
            (("developer=op us",), "must be a model alias or id"),
            (("developer",), "expected role=model"),
            (("default=",), '"default" cannot be empty'),
        ):
            code, out = self.p.run("set", *args)
            self.assertEqual(code, 2, args)
            self.assertTrue(out.startswith("ERROR="), out)
            self.assertIn(message, out)
        self.assertEqual(self.read_config(), {"agents": {"developer": "opus"}})
        self.assertEqual(frontmatter_model(self.dev), "sonnet")

    def test_set_refuses_to_touch_a_broken_config(self):
        self.p.config("{not json")
        code, out = self.p.run("set", "developer=opus")
        self.assertEqual(code, 2)
        self.assertTrue(out.startswith("ERROR="), out)
        with open(am.config_path(self.p.root), encoding="utf-8") as fh:
            self.assertEqual(fh.read(), "{not json")

    def test_set_same_value_twice_reports_nothing_changed(self):
        self.p.run("set", "developer=opus")
        code, out = self.p.run("set", "developer=opus")
        self.assertEqual(code, 0)
        self.assertIn("nothing changed", out)

    def test_reset_restores_the_built_in_defaults(self):
        self.p.config({"default": "haiku", "agents": {"developer": "haiku"}})
        self.p.run("apply")
        code, out = self.p.run("reset")
        self.assertEqual(code, 0)
        self.assertEqual(self.read_config(), am.DEFAULTS)
        self.assertEqual(frontmatter_model(self.dev), "opus")
        self.assertEqual(frontmatter_model(self.lead), "fable")
        self.assertIn("maxPlanck-developer: haiku → opus", out)


class HookTests(unittest.TestCase):
    """The SessionStart hook applies the config of an installed project."""

    HOOK = os.path.join(ROOT, ".claude", "hooks", "apply-agent-models.sh")

    def setUp(self):
        self.p = Project()
        self.addCleanup(self.p.cleanup)
        self.dev = self.p.agent("developer")

    def install_applier(self):
        os.makedirs(os.path.join(self.p.root, ".claude", "bin"))
        shutil.copy(AGENT_MODELS, os.path.join(self.p.root, ".claude", "bin", "maxPlanck-models.py"))

    def run_hook(self):
        proc = subprocess.run(
            ["bash", self.HOOK], capture_output=True, text=True,
            env={**os.environ, "CLAUDE_PROJECT_DIR": self.p.root},
        )
        return proc.returncode, proc.stdout

    def test_no_op_without_a_config_or_an_installed_applier(self):
        self.assertEqual(self.run_hook(), (0, ""))
        self.p.config({"agents": {"developer": "opus"}})
        self.assertEqual(self.run_hook(), (0, ""))  # applier not installed: source repo / plugin
        self.assertEqual(frontmatter_model(self.dev), "sonnet")

    def test_applies_and_reports_a_change_once(self):
        self.install_applier()
        self.p.config({"agents": {"developer": "opus"}})
        code, out = self.run_hook()
        self.assertEqual(code, 0)
        self.assertIn("maxPlanck-developer: sonnet → opus", out)
        self.assertEqual(frontmatter_model(self.dev), "opus")
        self.assertEqual(self.run_hook(), (0, ""))

    def test_never_fails_on_a_broken_config(self):
        self.install_applier()
        self.p.config("{broken")
        code, out = self.run_hook()
        self.assertEqual(code, 0)
        self.assertIn("ERROR=", out)


if __name__ == "__main__":
    unittest.main()
