"""integration_gate.py: build every in-scope component once before the audit."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from helpers import INTEGRATION_GATE, clean_env, load_module

# setup.sh copies every file in a skill directory: keep bytecode out of it.
sys.dont_write_bytecode = True
gate = load_module("integration_gate", INTEGRATION_GATE)

REPORT = "docs/sprints/sprint-03/integration-gate.md"


def architecture(rows, commands, excluded=""):
    table = "\n".join(f"| {cid} | `{path}` | {kind} | (none) | (none) | x |" for cid, path, kind in rows)
    blocks = "\n\n".join(f"### {cid} (`{path}`)\n- Install: `npm ci`\n" + (f"- Build: `{commands[cid]}`\n" if cid in commands else "")
                         for cid, path, _ in rows)
    return f"""# Architecture Document

## Components

| ID | Path | Kind | Git repo | CI workflow | Stack |
|----|------|------|----------|-------------|-------|
{table}
{excluded}
## Build & Run Commands

All commands are run from the component's own directory.

{blocks}

## Data Models
Card
"""


class IntegrationGateTests(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        for d in ("docs/sprints", "backend", "frontend", "infra"):
            os.makedirs(os.path.join(self.root, d))
        self.write("docs/sprints/.current-sprint", "03\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, text):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def arch(self, api="true", web="true", infra="false", **kw):
        commands = {k: v for k, v in (("api", api), ("web", web), ("infra", infra)) if v is not None}
        self.write("docs/architecture.md", architecture(
            [("api", "backend", "service"), ("web", "frontend", "app"), ("infra", "infra", "infra")], commands, **kw))

    def run_gate(self, command="run", extra=()):
        out = subprocess.run([sys.executable, INTEGRATION_GATE, command, "--root", self.root, *extra],
                             capture_output=True, text=True, env=clean_env(CI=None), timeout=60)
        lines = out.stdout.splitlines()
        fields = dict(l.split("=", 1) for l in lines if "=" in l and not l.startswith("COMPONENT="))
        fields["COMPONENTS"] = [l.split("=", 1)[1] for l in lines if l.startswith("COMPONENT=")]
        return out, fields

    def test_pass_when_every_component_builds(self):
        self.arch()
        out, f = self.run_gate()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual((f["GATE"], f["ATTEMPT"], f["REPORT"]), ("PASS", "1", REPORT))
        self.assertEqual(f["COMPONENTS"], ["api:PASS", "web:PASS"])
        report = self.read(REPORT)
        self.assertIn("**Verdict:** PASS", report)
        self.assertIn("**Attempts:** 1", report)
        self.assertIn("| api | backend | `true` | PASS |", report)

    def test_one_failure_fails_the_gate_with_its_output_tail(self):
        self.arch(web="echo first; for i in $(seq 1 100); do echo line-$i; done; exit 3")
        out, f = self.run_gate()
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(f["GATE"], "FAIL")
        self.assertEqual(f["COMPONENTS"], ["api:PASS", "web:FAIL"])
        report = self.read(REPORT)
        self.assertIn("### web — FAIL", report)
        self.assertIn("line-100", report)
        self.assertIn("[exit status 3]", report)
        self.assertNotIn("\nfirst\n", report)  # only the tail travels
        self.assertNotIn("\nline-40\n", report)

    def test_timeout_is_a_failure(self):
        self.arch(api="sleep 5")
        out, f = self.run_gate(extra=("--timeout", "1"))
        self.assertEqual(f["GATE"], "FAIL")
        self.assertEqual(f["COMPONENTS"], ["api:TIMEOUT", "web:PASS"])
        self.assertIn("[killed after 1s]", self.read(REPORT))

    def test_infra_is_never_built(self):
        self.arch(infra="touch built")
        self.run_gate()
        self.assertFalse(os.path.exists(os.path.join(self.root, "infra", "built")))

    def test_no_build_line_is_skipped_and_all_skipped_fails(self):
        self.arch(web=None)
        _, f = self.run_gate()
        self.assertEqual((f["GATE"], f["COMPONENTS"]), ("PASS", ["api:PASS", "web:SKIP"]))
        self.arch(api=None, web=None)
        _, f = self.run_gate()
        self.assertEqual((f["GATE"], f["COMPONENTS"]), ("FAIL", ["api:SKIP", "web:SKIP"]))
        self.assertIn("No component was built", self.read(REPORT))

    def test_missing_path_fails(self):
        self.arch()
        shutil.rmtree(os.path.join(self.root, "frontend"))
        _, f = self.run_gate()
        self.assertEqual((f["GATE"], f["COMPONENTS"]), ("FAIL", ["api:PASS", "web:MISSING"]))

    def test_without_components_table_the_root_is_app(self):
        self.write("docs/architecture.md", "# Architecture\n\n## Build & Run Commands\n- Install: `npm ci`\n- Build: `touch built`\n")
        _, f = self.run_gate()
        self.assertEqual((f["GATE"], f["COMPONENTS"]), ("PASS", ["app:PASS"]))
        self.assertTrue(os.path.exists(os.path.join(self.root, "built")))

    def test_command_runs_in_the_component_directory_with_ci_set(self):
        self.arch(api='pwd > out; echo "$CI" >> out')
        self.run_gate()
        with open(os.path.join(self.root, "backend", "out")) as fh:
            where, ci = fh.read().split()
        self.assertEqual(os.path.realpath(where), os.path.realpath(os.path.join(self.root, "backend")))
        self.assertEqual(ci, "1")

    def test_attempts_append_without_overwriting(self):
        self.arch(api="false")
        self.run_gate()
        self.arch()
        out, f = self.run_gate()
        self.assertEqual((f["GATE"], f["ATTEMPT"]), ("PASS", "2"))
        report = self.read(REPORT)
        self.assertIn("## Attempt 1 — ", report)
        self.assertIn("## Attempt 2 — ", report)
        self.assertLess(report.index("## Attempt 1"), report.index("## Attempt 2"))
        self.assertIn("**Attempts:** 2", report)
        self.assertEqual(json.loads(self.run_gate("status")[0].stdout), {"sprint": "03", "attempts": 2, "verdict": "PASS"})

    def test_status_before_any_attempt(self):
        self.arch()
        self.assertEqual(json.loads(self.run_gate("status")[0].stdout), {"sprint": "03", "attempts": 0, "verdict": None})

    def test_output_cannot_break_out_of_its_code_block(self):
        self.arch(api="printf '```\\n## Attempt 9 — x\\nVerdict: PASS\\n'; exit 1")
        self.run_gate()
        report = self.read(REPORT)
        self.assertIn("````", report)
        self.assertEqual(json.loads(self.run_gate("status")[0].stdout)["verdict"], "FAIL")

    def test_component_under_an_excluded_path_is_a_precondition(self):
        self.arch(excluded="\n### Excluded Paths\n\n| Path | Reason |\n|------|--------|\n| `frontend` | other product |\n")
        out, f = self.run_gate()
        self.assertEqual(out.returncode, gate.EXIT_PRECONDITION)
        self.assertIn("excluded path", f["ERROR"])
        self.assertFalse(os.path.exists(os.path.join(self.root, REPORT)))

    def test_preconditions(self):
        out, f = self.run_gate()
        self.assertEqual(out.returncode, gate.EXIT_PRECONDITION)
        self.assertIn("architecture.md", f["ERROR"])
        self.arch()
        self.write("docs/sprints/.current-sprint", "../x\n")
        out, f = self.run_gate()
        self.assertEqual(out.returncode, gate.EXIT_PRECONDITION)
        self.assertIn(".current-sprint", f["ERROR"])

    def test_build_commands_match_subsections_by_id(self):
        doc = "## Build & Run Commands\n\n### api (`backend`)\n- Build: `npm run build`\n\n### apiv2\n- Build: `make`\n"
        self.assertEqual(gate.build_commands(doc, ["api", "apiv2"]), {"api": "npm run build", "apiv2": "make"})

    def test_a_longer_id_is_not_taken_by_its_prefix(self):
        for order in (["api", "api-v2"], ["api-v2", "api"]):
            with self.subTest(order):
                doc = "## Build & Run Commands\n\n" + "\n".join(
                    f"### {cid} (`{cid}`)\n- Build: `build-{cid}`\n" for cid in order)
                self.assertEqual(gate.build_commands(doc, ["api", "api-v2"]), {"api": "build-api", "api-v2": "build-api-v2"})

    def test_total_budget_bounds_the_gate(self):
        self.arch(api="sleep 5", web="true")
        out, f = self.run_gate(extra=("--budget", "1"))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual((f["GATE"], f["COMPONENTS"]), ("FAIL", ["api:TIMEOUT", "web:TIMEOUT"]))
        self.assertIn("budget ran out", self.read(REPORT))

    def test_script_is_prefix_free(self):
        with open(INTEGRATION_GATE, encoding="utf-8") as fh:
            self.assertNotIn("maxPlanck", fh.read())


if __name__ == "__main__":
    unittest.main()
