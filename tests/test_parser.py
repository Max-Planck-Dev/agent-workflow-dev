import json
import os
import tempfile
import time
import unittest

from helpers import FIXTURES, dashboard, fixture_lines, upto

pd = dashboard()


def ts(s: str) -> float:
    return time.mktime(time.strptime(s, "%Y-%m-%d %H:%M:%S"))


class ModernChangeRunTests(unittest.TestCase):
    """The in-flight change request at the end of the modern fixture."""

    def setUp(self):
        self.lines = fixture_lines("agent-workflow.modern.log")
        self.run = pd.parse_log(self.lines, "maxPlanck", now=ts("2026-09-21 11:07:00"))

    def test_latest_start_wins(self):
        self.assertEqual(self.run.kind, "change")
        self.assertEqual(self.run.sprint, "02")
        self.assertEqual(self.run.description, "Make card titles editable inline")
        self.assertEqual(self.run.started_ts, ts("2026-09-21 11:00:00"))
        self.assertIsNone(self.run.completed_ts)

    def test_state_running(self):
        self.assertEqual(self.run.state, "running")

    def test_phase_statuses(self):
        st = {p: s.status for p, s in self.run.phases.items()}
        self.assertEqual(st["kickoff"], "done")
        self.assertEqual(st["design"], "skipped")
        self.assertEqual(st["develop"], "running")
        self.assertEqual(st["review"], "pending")
        self.assertEqual(st["sprint"], "pending")
        self.assertEqual(self.run.phases["kickoff"].runs, 1)
        self.assertEqual(self.run.phases["design"].last_reason, "behaviour-only change, no structural impact")
        self.assertEqual(self.run.current_phase(), "develop")

    def test_current_agent_and_progress(self):
        sess = self.run.current_session()
        self.assertIsNotNone(sess)
        self.assertEqual(sess.agent, "maxPlanck-developer")
        self.assertEqual(sess.progress, (3, 7, "Wiring PATCH /cards/:id title endpoint"))
        self.assertIn(("ACTION", "Added inline edit to CardTitle"), [(a, t) for _, a, t in sess.events])

    def test_noise_does_not_close_the_workflow_session(self):
        # The trailing Explore/claude-code-guide START + `STOP unknown` pair
        # must close the noise session, not the developer.
        noise = [s for s in self.run.agent_sessions if s.noise]
        self.assertTrue(noise)
        self.assertTrue(all(s.stop_ts is not None for s in noise))
        self.assertIsNone(self.run.current_session().stop_ts)

    def test_namespaced_agent_is_normalised(self):
        names = [s.agent for s in self.run.agent_sessions if not s.noise]
        self.assertEqual(names[0], "maxPlanck-product-owner")
        self.assertTrue(all(":" not in n for n in names))

    def test_malformed_line_is_ignored(self):
        self.assertEqual(self.run.malformed, 1)

    def test_tail_drops_noise(self):
        self.assertTrue(self.run.tail)
        self.assertFalse(any("claude-code-guide" in t or "Explore" in t for t in self.run.tail))

    def test_stale_after_quiet_period(self):
        run = pd.parse_log(self.lines, "maxPlanck", now=ts("2026-09-21 11:06:20") + pd.STALE_AFTER_S + 60)
        self.assertEqual(run.state, "stale")


class ModernFeelingLuckyRunTests(unittest.TestCase):
    """The completed feeling-lucky run in the modern fixture."""

    def setUp(self):
        lines = upto(fixture_lines("agent-workflow.modern.log"), "Pipeline complete (sprint 02)")
        self.run = pd.parse_log(lines, "maxPlanck", now=ts("2026-09-20 10:00:00"))

    def test_complete(self):
        self.assertEqual(self.run.kind, "feeling-lucky")
        self.assertEqual(self.run.sprint, "02")
        self.assertEqual(self.run.state, "complete")
        self.assertEqual(self.run.unresolved_count, 1)
        self.assertEqual(self.run.completed_ts, ts("2026-09-20 09:47:05"))

    def test_all_phases_done_with_reruns(self):
        for name in self.run.order:
            self.assertEqual(self.run.phases[name].status, "done", name)
        self.assertEqual(self.run.phases["develop"].runs, 2)
        self.assertEqual(self.run.phases["review"].runs, 2)
        self.assertEqual(self.run.phases["sprint"].runs, 1)

    def test_loops(self):
        self.assertEqual([(l.src, l.dst) for l in self.run.loops], [("review", "develop")])
        self.assertEqual(self.run.loops[0].reason, "NEEDS CHANGES — 2 critical findings")
        self.assertEqual(self.run.transitions[-1].reason, "40/40 tests pass")

    def test_progress_recorded_per_session(self):
        dev = [s for s in self.run.agent_sessions if s.agent == "maxPlanck-developer"]
        self.assertEqual(len(dev), 2)
        self.assertEqual(dev[0].progress, (5, 5, "Build passes"))
        self.assertIsNone(dev[1].progress)

    def test_unknown_stop_closes_latest_session(self):
        ux = [s for s in self.run.agent_sessions if s.agent == "maxPlanck-ux-designer"][0]
        self.assertEqual(ux.stop_ts, ts("2026-09-20 09:04:00"))
        self.assertIsNone(self.run.current_session())

    def test_phase_durations(self):
        dev = self.run.phases["develop"]
        self.assertEqual(len(dev.durations), 2)
        self.assertAlmostEqual(dev.durations[0], ts("2026-09-20 09:20:35") - ts("2026-09-20 09:06:40"))


class LegacyLogTests(unittest.TestCase):
    def setUp(self):
        self.lines = fixture_lines("agent-workflow.legacy.log")

    def test_last_run_parses(self):
        run = pd.parse_log(self.lines, "maxPlanck", now=ts("2026-02-21 00:00:00"))
        self.assertEqual(run.kind, "feeling-lucky")
        self.assertEqual(run.state, "complete")
        self.assertTrue(run.description.startswith("Fix attachment state sync"))
        self.assertEqual(run.phases["sprint"].status, "done")
        self.assertEqual(run.phases["audit"].status, "skipped")
        self.assertEqual(run.malformed, 0)

    def test_rerun_loop_in_fourth_run(self):
        lines = upto(self.lines, "[2026-02-20 19:10:12]")
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-02-20 19:20:00"))
        self.assertEqual(run.started_ts, ts("2026-02-20 18:41:30"))
        self.assertEqual(run.phases["develop"].runs, 2)
        self.assertEqual(run.phases["review"].runs, 2)
        self.assertEqual([(l.src, l.dst) for l in run.loops], [("review", "develop")])
        self.assertEqual(run.transitions[2].note, None)
        self.assertIn("(re-run)", [f"({t.note})" for t in run.transitions if t.note])

    def test_fix_pass_annotations_count_as_reruns(self):
        lines = upto(self.lines, "Phase review (re-review) finished")
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-02-20 18:00:00"))
        self.assertGreaterEqual(run.phases["develop"].runs, 2)
        self.assertGreaterEqual(run.phases["review"].runs, 2)
        self.assertTrue(run.loops)

    def test_prefix_falls_back_when_log_has_bare_names(self):
        # The legacy log only ever wrote bare role names (`Agent: developer`).
        self.assertIsNone(pd.infer_prefix(self.lines))
        with tempfile.TemporaryDirectory() as tmp:
            saved = os.environ.pop("PIPELINE_DASHBOARD_AGENT_PREFIX", None)
            try:
                self.assertEqual(pd.resolve_prefix(tmp, self.lines), "maxPlanck")
                os.makedirs(os.path.join(tmp, ".claude"))
                with open(os.path.join(tmp, ".claude", "acme-workflow-version.json"), "w") as fh:
                    json.dump({"prefix": "acme"}, fh)
                self.assertEqual(pd.resolve_prefix(tmp, self.lines), "acme")
            finally:
                if saved is not None:
                    os.environ["PIPELINE_DASHBOARD_AGENT_PREFIX"] = saved

    def test_empty_name_stop_lines_are_tolerated(self):
        run = pd.parse_log(self.lines, "maxPlanck", now=ts("2026-02-21 00:00:00"))
        self.assertEqual(run.malformed, 0)


class HelperTests(unittest.TestCase):
    def test_norm_agent(self):
        self.assertEqual(pd.norm_agent("maxPlanck-developer", "maxPlanck"), "maxPlanck-developer")
        self.assertEqual(pd.norm_agent("acme-developer", "acme"), "acme-developer")
        self.assertEqual(pd.norm_agent("developer", "maxPlanck"), "maxPlanck-developer")
        self.assertEqual(pd.norm_agent("maxplanck:maxPlanck-security", "maxPlanck"), "maxPlanck-security")
        self.assertEqual(pd.norm_agent("orchestrator", "maxPlanck"), "orchestrator")
        self.assertIsNone(pd.norm_agent("Explore", "maxPlanck"))
        self.assertIsNone(pd.norm_agent("unknown", "maxPlanck"))
        self.assertIsNone(pd.norm_agent("", "maxPlanck"))

    def test_infer_prefix_rebranded(self):
        lines = ["[2026-01-01 00:00:00] START | Agent: acme-developer\n"] * 2 + ["[2026-01-01 00:00:00] ACTION | Agent: developer | x\n"]
        self.assertEqual(pd.infer_prefix(lines), "acme")
        self.assertIsNone(pd.infer_prefix(["[2026-01-01 00:00:00] ACTION | Agent: developer | x\n"]))

    def test_start_line_variants(self):
        cases = {
            "Full pipeline started (sprint 03)": ("feeling-lucky", "03", None),
            "Full pipeline started | Args: build a thing": ("feeling-lucky", None, "build a thing"),
            "Full pipeline started | Goal: ship it": ("feeling-lucky", None, "ship it"),
            "Starting full pipeline | Feature: add DnD": ("feeling-lucky", None, "add DnD"),
            "Change request started (sprint 02): tweak copy": ("change", "02", "tweak copy"),
            "Adoption started": ("adopt", None, None),
        }
        for rest, (kind, sprint, desc) in cases.items():
            run = pd.parse_log([f"[2026-01-01 00:00:00] PIPELINE | Agent: orchestrator | {rest}\n"], "maxPlanck", now=ts("2026-01-01 00:01:00"))
            self.assertEqual((run.kind, run.sprint, run.description), (kind, sprint, desc), rest)
            self.assertEqual(run.state, "running")

    def test_complete_line_variants(self):
        for rest, n in {
            "Full pipeline complete": None,
            "Pipeline complete (sprint 02) | Unresolved: 3": 3,
            "Change request complete (sprint 01) | Unresolved: 0": 0,
            "Full pipeline complete (sprint 04): all phases clean": None,
        }.items():
            lines = [
                "[2026-01-01 00:00:00] PIPELINE | Agent: orchestrator | Full pipeline started (sprint 02)\n",
                f"[2026-01-01 00:10:00] PIPELINE | Agent: orchestrator | {rest}\n",
            ]
            run = pd.parse_log(lines, "maxPlanck", now=ts("2026-01-01 00:11:00"))
            self.assertEqual(run.state, "complete", rest)
            self.assertEqual(run.unresolved_count, n, rest)

    def test_force_advance(self):
        lines = [
            "[2026-01-01 00:00:00] PIPELINE | Agent: orchestrator | Full pipeline started (sprint 02)\n",
            "[2026-01-01 00:01:00] PIPELINE | Agent: orchestrator | Phase kickoff finished → routing to ux | Reason: ok\n",
            "[2026-01-01 00:02:00] PIPELINE | Agent: orchestrator | Phase ux force-advanced → routing to design | Reason: 3 runs\n",
        ]
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-01-01 00:03:00"))
        self.assertEqual(run.phases["ux"].status, "forced")
        self.assertEqual(run.phases["design"].status, "queued")
        self.assertEqual(run.current_phase(), "design")

    def test_idle_without_run(self):
        run = pd.parse_log(["[2026-01-01 00:00:00] START | Agent: Explore\n"], "maxPlanck", now=ts("2026-01-01 00:01:00"))
        self.assertEqual(run.state, "idle")
        # A lone phase skill run (no orchestrator) still shows the agent.
        run = pd.parse_log(["[2026-01-01 00:00:00] START | Agent: maxPlanck-developer\n"], "maxPlanck", now=ts("2026-01-01 00:01:00"))
        self.assertEqual(run.state, "running")
        self.assertEqual(run.current_session().agent, "maxPlanck-developer")

    def test_pipeline_state_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = os.path.join(tmp, "docs", "sprints", "sprint-02")
            os.makedirs(d)
            with open(os.path.join(FIXTURES, "pipeline-state.sprint-02.json")) as src, open(os.path.join(d, "pipeline-state.json"), "w") as dst:
                dst.write(src.read())
            state = pd.load_pipeline_state(tmp, "02")
            self.assertEqual(state["unresolved"], ["devops: BLOCKED (ISR-004)"])
            with open(os.path.join(tmp, "docs", "sprints", ".current-sprint"), "w") as fh:
                fh.write("02\n")
            self.assertEqual(pd.load_pipeline_state(tmp, None)["sprint"], "02")
            self.assertEqual(pd.load_pipeline_state(tmp, "09"), {})

    def test_model_merges_state_and_events(self):
        with tempfile.TemporaryDirectory() as tmp:
            os.makedirs(os.path.join(tmp, "logs"))
            os.makedirs(os.path.join(tmp, "docs", "sprints", "sprint-02"))
            with open(os.path.join(tmp, "logs", "agent-workflow.log"), "w") as fh:
                fh.writelines(fixture_lines("agent-workflow.modern.log"))
            with open(os.path.join(FIXTURES, "pipeline-state.sprint-02.json")) as src, open(os.path.join(tmp, "docs", "sprints", "sprint-02", "pipeline-state.json"), "w") as dst:
                dst.write(src.read())
            transcript = os.path.join(FIXTURES, "subagent-transcript.jsonl")
            with open(os.path.join(tmp, "logs", "pipeline-events.jsonl"), "w") as fh:
                fh.write(json.dumps({"event": "start", "agent": "maxPlanck-developer", "agent_id": "abc123", "transcript": transcript}) + "\n")
            model = pd.Model(tmp)
            run = model.refresh(force=True)
            self.assertEqual(run.unresolved, ["devops: BLOCKED (ISR-004)"])
            self.assertEqual(run.verdicts["review"], "APPROVED")
            self.assertEqual(run.current_session().transcript, transcript)
            self.assertEqual(model.hb_snapshot["tool_count"], 4)
            # Unchanged file → no re-parse, but the clock still advances.
            before = run.now
            run2 = model.refresh()
            self.assertGreaterEqual(run2.now, before)
            self.assertIs(run2, run)


if __name__ == "__main__":
    unittest.main()
