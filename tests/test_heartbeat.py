import os
import shutil
import tempfile
import unittest

from helpers import FIXTURES, dashboard

pd = dashboard()


class HeartbeatTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.path = os.path.join(self.tmp, "agent-abc123.jsonl")
        shutil.copy(os.path.join(FIXTURES, "subagent-transcript.jsonl"), self.path)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_counts_tools_and_last_tool(self):
        hb = pd.Heartbeat()
        snap = hb.update(self.path)
        self.assertEqual(snap["tool_count"], 4)
        self.assertEqual(snap["last_tool"], "Bash")
        self.assertEqual(snap["lines"], 10)
        self.assertEqual(snap["last_text"], "Build passes.")
        self.assertEqual(snap["last_ts"], pd.parse_iso("2026-09-21T09:03:00.000Z"))

    def test_incremental_read(self):
        hb = pd.Heartbeat()
        hb.update(self.path)
        with open(self.path, "a") as fh:
            fh.write('{"type":"assistant","timestamp":"2026-09-21T09:04:00.000Z","message":{"content":[{"type":"tool_use","name":"Write"}]}}\n')
        snap = hb.update(self.path)
        self.assertEqual(snap["tool_count"], 5)
        self.assertEqual(snap["last_tool"], "Write")
        self.assertEqual(snap["lines"], 11)

    def test_partial_trailing_line(self):
        hb = pd.Heartbeat()
        hb.update(self.path)
        with open(self.path, "a") as fh:
            fh.write('{"type":"assistant","timestamp":"2026-09-21T09:05:00.000Z","message":{"content":[{"type":"tool_use","na')
        snap = hb.update(self.path)
        self.assertEqual(snap["tool_count"], 4)  # incomplete line not counted yet
        with open(self.path, "a") as fh:
            fh.write('me":"Glob"}]}}\n')
        snap = hb.update(self.path)
        self.assertEqual(snap["tool_count"], 5)
        self.assertEqual(snap["last_tool"], "Glob")

    def test_missing_file(self):
        hb = pd.Heartbeat()
        self.assertIsNone(hb.update(os.path.join(self.tmp, "nope.jsonl")))
        self.assertIsNone(hb.update(None))

    def test_path_change_resets(self):
        hb = pd.Heartbeat()
        hb.update(self.path)
        other = os.path.join(self.tmp, "agent-other.jsonl")
        with open(other, "w") as fh:
            fh.write('{"type":"assistant","timestamp":"2026-09-21T09:05:00.000Z","message":{"content":[{"type":"tool_use","name":"Read"}]}}\n')
        snap = hb.update(other)
        self.assertEqual(snap["tool_count"], 1)

    def test_truncated_file_restarts(self):
        hb = pd.Heartbeat()
        hb.update(self.path)
        with open(self.path, "w") as fh:
            fh.write('{"type":"assistant","timestamp":"2026-09-21T09:05:00.000Z","message":{"content":[{"type":"tool_use","name":"Read"}]}}\n')
        snap = hb.update(self.path)
        self.assertEqual(snap["tool_count"], 1)


if __name__ == "__main__":
    unittest.main()
