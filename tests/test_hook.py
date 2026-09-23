import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest

from helpers import HOOK_SH, clean_env

FAKE_HERDR = r'''#!/usr/bin/env bash
# Fake herdr: records argv, answers with canned JSON.
echo "$*" >> "$FAKE_HERDR_LOG"
case "$1 $2 $3" in
  "pane list "*)
    if [ -f "$FAKE_HERDR_LOG.opened" ]; then
      echo '{"result":{"panes":[{"pane_id":"w1:p1","agent":"claude","agent_session":{"value":"sess1"}},{"pane_id":"w1:p9","label":"pipeline dashboard"}]}}'
    else
      echo '{"result":{"panes":[{"pane_id":"w1:p1","agent":"claude","agent_session":{"value":"sess1"}}]}}'
    fi ;;
  "pane get "*)
    if [ -f "$FAKE_HERDR_LOG.opened" ] && [ "$3" = "w1:p9" ]; then
      echo '{"result":{"pane":{"pane_id":"w1:p9"}}}'
    else
      echo '{"error":{"code":"not_found"}}'; exit 1
    fi ;;
  "plugin pane open")
    touch "$FAKE_HERDR_LOG.opened"
    echo '{"result":{"plugin_pane":{"pane":{"pane_id":"w1:p9"}}}}' ;;
  *) echo '{"result":{}}' ;;
esac
'''


class HookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.transcripts = os.path.join(self.tmp, "tp")
        os.makedirs(os.path.join(self.transcripts, "sess1", "subagents"))
        self.main_transcript = os.path.join(self.transcripts, "sess1.jsonl")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def hook(self, event, payload, **env):
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        out = subprocess.run(
            ["bash", HOOK_SH, event], input=stdin, capture_output=True, text=True,
            env=clean_env(CLAUDE_PROJECT_DIR=self.tmp, **env), timeout=20,
        )
        self.assertEqual(out.returncode, 0, out.stderr)
        return out

    def log_lines(self):
        with open(os.path.join(self.tmp, "logs", "agent-workflow.log")) as fh:
            return [l.rstrip("\n") for l in fh]

    def events(self):
        path = os.path.join(self.tmp, "logs", "pipeline-events.jsonl")
        if not os.path.exists(path):
            return []
        with open(path) as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def payload(self, **kw):
        base = {"session_id": "sess1", "transcript_path": self.main_transcript, "agent_id": "abc"}
        base.update(kw)
        return base

    def test_start_and_stop_workflow_agent(self):
        self.hook("START", self.payload(agent_type="maxPlanck-developer"))
        self.hook("STOP", self.payload())  # no agent_type on stop
        lines = self.log_lines()
        self.assertTrue(lines[0].endswith("START | Agent: maxPlanck-developer"))
        self.assertTrue(lines[1].endswith("STOP | Agent: maxPlanck-developer"))
        ev = self.events()
        self.assertEqual([e["event"] for e in ev], ["start", "stop"])
        self.assertEqual(ev[0]["agent_id"], "abc")
        self.assertEqual(ev[0]["session_id"], "sess1")
        self.assertTrue(ev[0]["transcript"].endswith(os.path.join("sess1", "subagents", "agent-abc.jsonl")))
        self.assertIsInstance(ev[1]["duration_s"], int)
        self.assertFalse(ev[0]["herdr"]["env"])
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "logs", ".pipeline", "agents", "abc")))

    def test_stop_name_from_meta_json_when_stamp_missing(self):
        meta = os.path.join(self.transcripts, "sess1", "subagents", "agent-abc.meta.json")
        with open(meta, "w") as fh:
            json.dump({"agentType": "maxPlanck-qa-tester"}, fh)
        self.hook("STOP", self.payload())
        self.assertTrue(self.log_lines()[-1].endswith("STOP | Agent: maxPlanck-qa-tester"))
        self.assertEqual(self.events()[-1]["agent"], "maxPlanck-qa-tester")

    def test_namespaced_agent_type(self):
        self.hook("START", self.payload(agent_type="maxplanck:maxPlanck-architect"))
        self.assertTrue(self.log_lines()[-1].endswith("Agent: maxPlanck-architect"))
        self.assertEqual(self.events()[-1]["agent"], "maxPlanck-architect")

    def test_noise_agent_gets_human_line_only(self):
        self.hook("START", self.payload(agent_type="Explore", agent_id="zzz"))
        self.hook("STOP", self.payload(agent_id="zzz"))
        lines = self.log_lines()
        self.assertTrue(lines[0].endswith("START | Agent: Explore"))
        self.assertTrue(lines[1].endswith("STOP | Agent: Explore"))
        self.assertEqual(self.events(), [])

    def test_garbage_payload(self):
        self.hook("STOP", "not json at all")
        self.assertTrue(self.log_lines()[-1].endswith("STOP | Agent: unknown"))
        self.assertEqual(self.events(), [])

    def test_auto_open_once_inside_herdr(self):
        shim_dir = os.path.join(self.tmp, "shim")
        os.makedirs(shim_dir)
        shim = os.path.join(shim_dir, "herdr")
        with open(shim, "w") as fh:
            fh.write(FAKE_HERDR)
        os.chmod(shim, os.stat(shim).st_mode | stat.S_IEXEC)
        argv_log = os.path.join(self.tmp, "herdr-argv.log")
        env = dict(HERDR_ENV="1", HERDR_PANE_ID="w1:p1", HERDR_WORKSPACE_ID="w1", HERDR_BIN_PATH=shim, FAKE_HERDR_LOG=argv_log)

        self.hook("START", self.payload(agent_type="maxPlanck-product-owner", agent_id="a1"), **env)
        self.wait_for(lambda: os.path.exists(argv_log + ".opened"))
        time.sleep(0.5)
        self.hook("STOP", self.payload(agent_id="a1"), **env)
        self.hook("START", self.payload(agent_type="maxPlanck-ux-designer", agent_id="a2"), **env)
        time.sleep(1.0)

        with open(argv_log) as fh:
            calls = [l.strip() for l in fh if l.strip()]
        opens = [c for c in calls if c.startswith("plugin pane open")]
        self.assertEqual(len(opens), 1, calls)
        self.assertIn("--plugin maxplanck.pipeline", opens[0])
        self.assertIn("--target-pane w1:p1", opens[0])
        self.assertIn(f"--cwd {self.tmp}", opens[0])
        self.assertIn("PIPELINE_DASHBOARD_CLAUDE_PANE=w1:p1", opens[0])
        self.assertIn("pane rename w1:p9 pipeline dashboard", calls)
        with open(os.path.join(self.tmp, "logs", ".pipeline", "herdr.json")) as fh:
            state = json.load(fh)
        self.assertEqual(state["dashboard_pane_id"], "w1:p9")
        self.assertEqual(state["claude_pane_id"], "w1:p1")
        self.assertEqual(state["session_id"], "sess1")
        self.assertTrue(self.events()[0]["herdr"]["env"])
        self.assertEqual(self.events()[0]["herdr"]["pane_id"], "w1:p1")
        self.assertFalse(os.path.exists(os.path.join(self.tmp, "logs", ".pipeline", "auto-open.lock")))

    def wait_for(self, cond, timeout=8.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            if cond():
                return
            time.sleep(0.1)
        self.fail("condition not met in time")


if __name__ == "__main__":
    unittest.main()
