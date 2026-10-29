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

    def test_unknown_stop_never_closes_a_workflow_session(self):
        # The `STOP unknown` at 09:04:00 is ignored; ux closes on its routing line.
        ux = [s for s in self.run.agent_sessions if s.agent == "maxPlanck-ux-designer"][0]
        self.assertEqual(ux.stop_ts, ts("2026-09-20 09:04:05"))
        self.assertIsNone(self.run.current_session())

    def test_periodic_unknown_stops_keep_agent_visible(self):
        lines = [
            "[2026-09-25 17:13:00] PIPELINE | Agent: orchestrator | Change request started (sprint 34): x\n",
            "[2026-09-25 17:13:18] START | Agent: maxPlanck-security\n",
        ] + [f"[2026-09-25 17:{14 + i:02d}:00] STOP | Agent: unknown\n" for i in range(6)]
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-09-25 17:20:30"))
        sess = run.current_session()
        self.assertIsNotNone(sess)
        self.assertEqual(sess.agent, "maxPlanck-security")
        self.assertEqual(run.phases["audit"].status, "running")
        self.assertEqual(run.state, "running")

    def test_agent_written_start_line_is_not_a_new_session(self):
        lines = [
            "[2026-09-25 17:20:00] PIPELINE | Agent: orchestrator | Change request started (sprint 34): x\n",
            "[2026-09-25 17:20:43] START | Agent: maxPlanck-devops\n",
            "[2026-09-25 17:25:08] START | Agent: maxPlanck-devops | Documentation-only DevOps pass | Output: docs/devops/deployment.md\n",
            "[2026-09-25 17:25:09] PROGRESS | Agent: maxPlanck-devops | 2/4 | Updating rows\n",
        ]
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-09-25 17:26:00"))
        devops = [s for s in run.agent_sessions if s.agent == "maxPlanck-devops"]
        self.assertEqual(len(devops), 1)
        self.assertEqual(devops[0].start_ts, ts("2026-09-25 17:20:43"))
        self.assertEqual(devops[0].progress, (2, 4, "Updating rows"))

    def test_next_agent_start_closes_previous_session(self):
        lines = [
            "[2026-09-25 17:00:00] PIPELINE | Agent: orchestrator | Change request started (sprint 34): x\n",
            "[2026-09-25 17:00:10] START | Agent: maxPlanck-product-owner\n",
            "[2026-09-25 17:05:00] START | Agent: maxPlanck-architect\n",
        ]
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-09-25 17:06:00"))
        po = [s for s in run.agent_sessions if s.agent == "maxPlanck-product-owner"][0]
        self.assertEqual(po.stop_ts, ts("2026-09-25 17:05:00"))
        self.assertEqual(run.current_session().agent, "maxPlanck-architect")

    def test_improvised_phase_is_slotted_into_the_order(self):
        lines = [
            "[2026-09-25 17:00:00] PIPELINE | Agent: orchestrator | Change request started (sprint 34): x\n",
            "[2026-09-25 17:20:35] PIPELINE | Agent: orchestrator | Phase audit finished → routing to infra | Reason: ISRs\n",
            "[2026-09-25 17:20:43] START | Agent: maxPlanck-devops\n",
        ]
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-09-25 17:21:00"))
        self.assertEqual(run.order, ["kickoff", "design", "develop", "review", "audit", "infra", "test", "sprint"])
        self.assertEqual(run.phases["infra"].status, "running")
        self.assertEqual(run.current_phase(), "infra")

    def test_follow_up_agent_after_completion_shows_running(self):
        lines = [
            "[2026-09-25 17:00:00] PIPELINE | Agent: orchestrator | Change request started (sprint 34): x\n",
            "[2026-09-25 17:29:30] PIPELINE | Agent: orchestrator | Change request complete (sprint 34) | Unresolved: 1\n",
            "[2026-09-25 17:31:05] START | Agent: maxPlanck-security\n",
            "[2026-09-25 17:31:37] STOP | Agent: unknown\n",
        ]
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-09-25 17:32:00"))
        self.assertEqual(run.state, "running")
        self.assertEqual(run.current_session().agent, "maxPlanck-security")

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


class ProfileLineTests(unittest.TestCase):
    """The orchestrators log `Profile <name> | Order: …` right after the start line."""

    def test_profile_order_replaces_the_default_order(self):
        lines = fixture_lines("agent-workflow.profile.log")
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-10-30 09:37:00"))
        self.assertEqual(run.kind, "feeling-lucky")
        self.assertEqual(run.profile, "nacho")
        self.assertEqual(run.order, ["kickoff", "ux", "design", "design-review", "plan", "plan-review",
                                     "develop", "review", "gate", "audit", "infra", "test", "sprint"])
        self.assertEqual(run.state, "running")
        for name in ("design-review", "plan", "plan-review", "gate"):
            self.assertEqual(run.phases[name].status, "done", name)
        self.assertEqual(run.phases["audit"].status, "running")
        self.assertEqual(run.current_session().agent, "maxPlanck-security")
        self.assertEqual(run.loops, [])

    def test_new_roles_map_to_their_phases(self):
        for role, phase in (("design-reviewer", "design-review"), ("tech-lead", "plan"), ("plan-reviewer", "plan-review")):
            self.assertEqual(pd.ROLE_TO_PHASE[role], phase)

    def test_default_profile_line_changes_nothing(self):
        lines = fixture_lines("agent-workflow.modern.log")
        # The fixture holds several runs and the latest start wins: a change request.
        last = max(i for i, line in enumerate(lines) if "Change request started" in line)
        with_line = lines[:last + 1] + ["[2026-09-21 11:00:01] PIPELINE | Agent: orchestrator | Profile default | Order: kickoff design develop review audit test sprint\n"] + lines[last + 1:]
        now = ts("2026-09-21 11:07:00")
        plain, profiled = pd.parse_log(lines, "maxPlanck", now=now), pd.parse_log(with_line, "maxPlanck", now=now)
        self.assertEqual(profiled.order, plain.order)
        self.assertEqual({n: p.status for n, p in profiled.phases.items()}, {n: p.status for n, p in plain.phases.items()})
        self.assertEqual(profiled.profile, "default")

    def test_unknown_phase_names_are_dropped_and_an_empty_order_is_ignored(self):
        head = "[2026-10-30 09:00:00] PIPELINE | Agent: orchestrator | Change request started (sprint 03): x\n"
        run = pd.parse_log([head, "[2026-10-30 09:00:01] PIPELINE | Agent: orchestrator | Profile odd | Order: kickoff bogus develop\n"], "maxPlanck", now=ts("2026-10-30 09:01:00"))
        self.assertEqual(run.order, ["kickoff", "develop"])
        run = pd.parse_log([head, "[2026-10-30 09:00:01] PIPELINE | Agent: orchestrator | Profile odd | Order: bogus\n"], "maxPlanck", now=ts("2026-10-30 09:01:00"))
        self.assertEqual(run.order, pd.ORDERS["change"])
        self.assertIsNone(run.profile)

    def test_optional_phases_of_a_change_run_read_as_skipped_at_completion(self):
        lines = [
            "[2026-10-30 09:00:00] PIPELINE | Agent: orchestrator | Change request started (sprint 03): x\n",
            "[2026-10-30 09:00:01] PIPELINE | Agent: orchestrator | Profile nacho | Order: kickoff design design-review plan plan-review develop review gate audit test sprint\n",
            "[2026-10-30 09:01:00] PIPELINE | Agent: orchestrator | Phase kickoff finished → routing to develop | Reason: not structural\n",
            "[2026-10-30 09:05:00] PIPELINE | Agent: orchestrator | Phase develop finished → routing to review | Reason: builds\n",
            "[2026-10-30 09:08:00] PIPELINE | Agent: orchestrator | Phase review finished → routing to test | Reason: APPROVED\n",
            "[2026-10-30 09:12:00] PIPELINE | Agent: orchestrator | Phase test finished → routing to sprint | Reason: pass\n",
            "[2026-10-30 09:14:00] PIPELINE | Agent: orchestrator | Change request complete (sprint 03) | Unresolved: 0\n",
        ]
        run = pd.parse_log(lines, "maxPlanck", now=ts("2026-10-30 09:15:00"))
        self.assertEqual(run.state, "complete")
        for name in ("design", "design-review", "plan", "plan-review", "gate", "audit"):
            self.assertEqual(run.phases[name].status, "skipped", name)
        self.assertEqual(run.phases["sprint"].status, "done")


class PerStoryLoopTests(unittest.TestCase):
    """With the story-loop switch, plan → plan-review → develop → review run once per
    story; the routing lines carry the story and the dashboard tells advancing from retrying."""

    LINES = [
        "[2026-10-17 10:00:00] PIPELINE | Agent: orchestrator | Full pipeline started (sprint 05): per-story loop\n",
        "[2026-10-17 10:00:01] PIPELINE | Agent: orchestrator | Profile nacho | Order: kickoff ux design design-review plan plan-review develop review gate audit infra test sprint\n",
        "[2026-10-17 10:01:00] PIPELINE | Agent: orchestrator | Phase design-review finished → routing to plan | Reason: APPROVED\n",
        "[2026-10-17 10:01:30] PIPELINE | Agent: orchestrator | Stories in scope (sprint 05): story-001, story-002, story-003\n",
        "[2026-10-17 10:02:00] START | Agent: maxPlanck-tech-lead | Starting\n",
        "[2026-10-17 10:05:00] PIPELINE | Agent: orchestrator | Phase plan (story-001) finished → routing to plan-review (story-001) | Reason: plan written\n",
        "[2026-10-17 10:08:00] PIPELINE | Agent: orchestrator | Phase plan-review (story-001) finished → routing to develop (story-001) | Reason: APPROVED\n",
        "[2026-10-17 10:20:00] PIPELINE | Agent: orchestrator | Phase develop (story-001) finished → routing to review (story-001) | Reason: builds\n",
        "[2026-10-17 10:25:00] PIPELINE | Agent: orchestrator | Phase review (story-001) finished → routing to develop (story-001) | Reason: NEEDS CHANGES — 1 critical\n",
        "[2026-10-17 10:30:00] PIPELINE | Agent: orchestrator | Phase develop (story-001, re-run) finished → routing to review (story-001) | Reason: fixed\n",
        "[2026-10-17 10:35:00] PIPELINE | Agent: orchestrator | Phase review (story-001, re-run) finished → routing to plan (story-002) | Reason: APPROVED — next story\n",
        "[2026-10-17 10:36:00] START | Agent: maxPlanck-tech-lead | Starting\n",
    ]

    def parse(self, lines, now="2026-10-17 10:40:00"):
        return pd.parse_log(lines, "maxPlanck", now=ts(now))

    def test_stories_and_current_story(self):
        run = self.parse(self.LINES)
        self.assertEqual(run.stories, ["story-001", "story-002", "story-003"])
        self.assertEqual(run.current_story, "story-002")
        self.assertEqual(run.story_index(), (2, 3))
        self.assertEqual(run.current_phase(), "plan")
        self.assertEqual(pd.story_run_label(run, "plan"), " story-002")
        self.assertEqual(pd.story_run_label(run, "audit"), "")

    def test_next_story_is_not_a_loop_but_a_retry_is(self):
        run = self.parse(self.LINES)
        self.assertEqual([(l.src, l.dst, l.story) for l in run.loops], [("review", "develop", "story-001")])
        last = run.transitions[-1]
        self.assertEqual((last.src, last.dst, last.story, last.next_story), ("review", "plan", "story-001", "story-002"))
        self.assertEqual(run.story_runs["story-001"], {"plan": 1, "plan-review": 1, "develop": 2, "review": 2})
        self.assertEqual(run.phases["develop"].runs, 2)

    def test_story_runs_show_the_retry_count_for_the_current_story(self):
        lines = self.LINES[:9] + ["[2026-10-17 10:26:00] START | Agent: maxPlanck-developer | Starting\n"]
        run = self.parse(lines, now="2026-10-17 10:27:00")
        self.assertEqual(run.current_story, "story-001")
        self.assertEqual(pd.story_run_label(run, "develop"), " story-001 r2")

    def test_leaving_the_loop_clears_the_story(self):
        lines = self.LINES + [
            "[2026-10-17 10:50:00] PIPELINE | Agent: orchestrator | Phase review (story-003) finished → routing to gate | Reason: APPROVED — last story\n",
        ]
        run = self.parse(lines, now="2026-10-17 10:55:00")
        self.assertIsNone(run.current_story)
        self.assertEqual(run.stories, ["story-001", "story-002", "story-003"])
        # A sprint-level fix pass back to develop carries no story and is a loop as before.
        run = self.parse(lines + ["[2026-10-17 11:00:00] PIPELINE | Agent: orchestrator | Phase gate finished → routing to develop | Reason: GATE=FAIL\n"],
                         now="2026-10-17 11:05:00")
        self.assertEqual([(l.src, l.dst) for l in run.loops][-1], ("gate", "develop"))
        self.assertIsNone(run.current_story)

    def test_stories_are_learned_from_routing_lines_without_an_announcement(self):
        lines = [l for l in self.LINES if "Stories in scope" not in l]
        run = self.parse(lines)
        self.assertEqual(run.stories, ["story-001", "story-002"])
        self.assertEqual(run.story_index(), (2, 2))

    def test_logs_without_stories_are_unchanged(self):
        run = pd.parse_log(fixture_lines("agent-workflow.modern.log"), "maxPlanck", now=ts("2026-09-21 11:07:00"))
        self.assertEqual(run.stories, [])
        self.assertIsNone(run.current_story)
        self.assertEqual(pd.story_run_label(run, "develop"), "")
