import json
import os
import subprocess
import sys
import tempfile
import time
import unittest

from helpers import DASHBOARD, FIXTURES, clean_env, dashboard, fixture_lines, upto

pd = dashboard()


def ts(s: str) -> float:
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))


class RenderTests(unittest.TestCase):
    def setUp(self):
        self.lines = fixture_lines("agent-workflow.modern.log")
        self.run = pd.parse_log(self.lines, "maxPlanck", now=ts("2026-09-21 11:07:00"))
        self.run.unresolved = ["devops: BLOCKED (ISR-004)"]
        self.heartbeat = {"path": "x", "tool_count": 27, "last_tool": "Read", "last_ts": ts("2026-09-21 11:06:57"), "last_text": None, "lines": 40}

    def check_invariants(self, frame, width, height):
        self.assertEqual(len(frame), height)
        for line in frame:
            self.assertLessEqual(len(pd.ANSI_RE.sub("", line)), width, repr(line))

    def test_sizes(self):
        for width, height in ((40, 20), (60, 40), (120, 50), (30, 10), (10, 3)):
            frame = pd.render(self.run, width, height, color=False, heartbeat=self.heartbeat)
            self.check_invariants(frame, width, height)

    def test_required_content_narrow(self):
        frame = pd.render(self.run, 60, 40, color=False, heartbeat=self.heartbeat)
        text = "\n".join(frame)
        self.assertIn("running", text)
        self.assertIn("sprint 02", text)
        self.assertIn("change", text)
        self.assertIn("▶ develop", text)
        self.assertIn("– design", text)
        self.assertIn("3/7", text)
        self.assertIn("Wiring PATCH", text)
        self.assertIn("tools 27", text)
        self.assertIn("unresolved (1)", text)
        self.assertIn("q quit", text)

    def test_required_content_wide(self):
        frame = pd.render(self.run, 120, 50, color=False, heartbeat=self.heartbeat)
        text = "\n".join(frame)
        self.assertIn("kickoff ✓", text)
        self.assertIn("develop ▶", text)
        self.assertIn("design –", text)

    def test_loops_and_rerun_counts(self):
        run = pd.parse_log(upto(self.lines, "Pipeline complete (sprint 02)"), "maxPlanck", now=ts("2026-09-20 10:00:00"))
        text = "\n".join(pd.render(run, 120, 50, color=False))
        self.assertIn("complete", text)
        self.assertIn("develop ✓ r2", text)
        self.assertIn("review → develop ×1", text)
        self.assertIn("NEEDS CHANGES", text)

    def test_tiny_drops_footer_and_tail(self):
        frame = pd.render(self.run, 30, 10, color=False, heartbeat=self.heartbeat)
        text = "\n".join(frame)
        self.assertNotIn("q quit", text)
        self.assertIn("running", text)

    def test_no_ansi_when_color_off(self):
        frame = pd.render(self.run, 80, 30, color=False, heartbeat=self.heartbeat)
        self.assertFalse(any("\x1b" in line for line in frame))
        frame = pd.render(self.run, 80, 30, color=True, heartbeat=self.heartbeat)
        self.assertTrue(any("\x1b" in line for line in frame))

    def test_idle_frame(self):
        run = pd.parse_log([], "maxPlanck", now=ts("2026-01-01 00:00:00"))
        text = "\n".join(pd.render(run, 60, 20, color=False))
        self.assertIn("idle", text)
        self.assertIn("no pipeline run", text)

    def test_fmt_dur(self):
        self.assertEqual(pd.fmt_dur(5), "5s")
        self.assertEqual(pd.fmt_dur(65), "1m05s")
        self.assertEqual(pd.fmt_dur(3725), "1h02m")


class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.tmp, "logs"))
        with open(os.path.join(self.tmp, "logs", "agent-workflow.log"), "w") as fh:
            fh.writelines(fixture_lines("agent-workflow.modern.log"))

    def run_cli(self, *args):
        return subprocess.run(
            [sys.executable, DASHBOARD, "--cwd", self.tmp, "--no-herdr", *args],
            capture_output=True, text=True, env=clean_env(), timeout=20,
        )

    def test_json(self):
        out = self.run_cli("--json")
        self.assertEqual(out.returncode, 0, out.stderr)
        data = json.loads(out.stdout)
        self.assertEqual(data["kind"], "change")
        self.assertEqual(data["current_phase"], "develop")
        self.assertEqual(data["current_agent"]["agent"], "maxPlanck-developer")

    def test_once(self):
        out = self.run_cli("--once", "--no-color", "--width", "70", "--height", "30")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn("3/7", out.stdout)
        self.assertTrue(all(len(l) <= 70 for l in out.stdout.splitlines()))

    def test_root_walk_up(self):
        nested = os.path.join(self.tmp, "frontend", "src")
        os.makedirs(nested)
        out = subprocess.run([sys.executable, DASHBOARD, "--json", "--no-herdr"], cwd=nested, capture_output=True, text=True, env=clean_env(), timeout=20)
        self.assertEqual(json.loads(out.stdout)["kind"], "change")


if __name__ == "__main__":
    unittest.main()
