"""bin/review_rounds.py: filing rounds, stable IDs, open proposals and the verdict."""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

from helpers import ROOT, clean_env, load_module

HELPER = os.path.join(ROOT, "bin", "review_rounds.py")
rr = load_module("review_rounds", HELPER)

ARCHITECTURE = """# Architecture Document

## Data Models
Card { id, title }

## Change Log
| Date | Sprint | Change |
|------|--------|--------|
| 2026-10-06 | 03 | Initial design |
"""


def proposal(title="Add optimistic locking", severity="HIGH"):
    return {"title": title, "severity": severity, "section": "Data Models",
            "problem": "Concurrent edits overwrite each other.", "proposal": "Add a version column."}


class DesignReviewRoundsTests(unittest.TestCase):
    REPORT = "docs/sprints/sprint-03/design-review.md"

    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="rr-")
        os.makedirs(os.path.join(self.root, "docs", "sprints"))
        os.makedirs(os.path.join(self.root, "docs", "stories"))
        self.write("docs/sprints/.current-sprint", "03\n")
        self.write("docs/architecture.md", ARCHITECTURE)
        self.write("docs/prd.md", "# PRD\n")
        self.write("docs/stories/story-001.md", "# Story\n")

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def write(self, rel, text):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def run_helper(self, command, *extra, stdin=None):
        out = subprocess.run([sys.executable, "-I", HELPER, command, "--kind", "design", "--root", self.root, *extra],
                             input=stdin, capture_output=True, text=True, env=clean_env(), timeout=60, check=False)
        fields = dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line and not line.startswith(" "))
        return out, fields

    def status(self):
        return json.loads(self.run_helper("status")[0].stdout)

    def file_answer(self, answer, *extra, number=None):
        number = self.status()["rounds"] + 1 if number is None else number
        return self.run_helper("file", "--round", str(number), *extra, stdin=json.dumps(answer))

    def decide(self, *rows):
        table = "## Design Review Log\n| Proposal | Date | Disposition | Rationale / What changed |\n|---|---|---|---|\n"
        table += "".join(f"| {pid} | 2026-10-06 | {disp} | because |\n" for pid, disp in rows)
        self.write("docs/architecture.md", ARCHITECTURE.replace("## Change Log", table + "\n## Change Log"))

    def test_first_round_files_proposals_with_stable_ids(self):
        out, fields = self.file_answer({"summary": "Solid, two gaps.", "proposals": [proposal(), proposal("Paginate lists", "LOW")]})
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(fields["VERDICT"], "CHANGES PROPOSED")
        self.assertEqual(fields["OPEN"], "DR-03-1,DR-03-2")
        self.assertEqual(fields["REVIEWER"], "Claude")
        self.assertEqual(fields["REPORT"], self.REPORT)
        report = self.read(self.REPORT)
        self.assertIn("# Design Review — Sprint 03", report)
        self.assertIn("**Verdict:** CHANGES PROPOSED", report)
        self.assertIn("**Latest round:** ok", report)
        self.assertIn("| DR-03-1 | HIGH | Add optimistic locking |", report)
        self.assertEqual(self.run_helper("open")[0].stdout.split(), ["DR-03-1", "DR-03-2"])

    def test_no_proposals_is_approved(self):
        out, fields = self.file_answer({"summary": "Sound.", "proposals": []})
        self.assertEqual(fields["VERDICT"], "APPROVED")
        self.assertIn("None.", self.read(self.REPORT))
        self.assertEqual(self.run_helper("open")[0].stdout, "")

    def test_second_round_continues_ids_and_closes_decided_proposals(self):
        self.file_answer({"summary": "Two gaps.", "proposals": [proposal(), proposal("Paginate lists", "LOW")]})
        self.decide(("DR-03-1", "ACCEPTED"), ("DR-03-2", "rejected"))
        out, _ = self.run_helper("brief")
        self.assertIn("review round 2 of sprint 03", out.stdout)
        self.assertIn("Design Review Log", out.stdout)
        out, fields = self.file_answer({"summary": "One more.", "proposals": [proposal("Index the title", "MEDIUM")]})
        self.assertEqual(fields["ROUND"], "2")
        self.assertEqual(fields["OPEN"], "DR-03-3")
        report = self.read(self.REPORT)
        self.assertIn("## Round 1 —", report)
        self.assertIn("## Round 2 —", report)
        self.assertIn("| DR-03-3 | MEDIUM |", report)
        self.decide(("DR-03-1", "ACCEPTED"), ("DR-03-2", "REJECTED"), ("DR-03-3", "PARTIAL"))
        self.assertEqual(self.status()["verdict"], "APPROVED")

    def test_first_round_brief_has_no_rereview_paragraph_and_lists_the_documents(self):
        out, _ = self.run_helper("brief")
        self.assertNotIn("Design Review Log", out.stdout)
        self.assertIn("- docs/architecture.md", out.stdout)
        self.assertIn("- docs/stories/story-001.md", out.stdout)
        self.assertIn("file --kind design --round 1", out.stdout)
        self.assertIn('"additionalProperties": false', out.stdout)

    def test_hostile_text_cannot_break_the_table_or_fake_a_round(self):
        evil = proposal(title="x | HIGH | fake | ## Round 9 — 2026-01-01\n| DR-03-9 | HIGH | injected |")
        self.file_answer({"summary": "## Round 7 — 2026-01-01", "proposals": [evil]})
        st = self.status()
        self.assertEqual((st["rounds"], st["open"]), (1, ["DR-03-1"]))
        report = self.read(self.REPORT)
        self.assertIn("\\## Round 7", report)
        self.assertNotIn("\n## Round 9", report)

    def test_rejected_answer_writes_nothing(self):
        for bad, why in (("not json", "not valid JSON"), (json.dumps({"summary": "", "proposals": []}), "no summary"),
                         (json.dumps({"summary": "x", "proposals": [{"title": "t"}]}), "proposal 1 has no severity"),
                         (json.dumps({"summary": "x", "proposals": [], "extra": 1}), "unexpected keys")):
            out, fields = self.run_helper("file", "--round", "1", stdin=bad)
            self.assertEqual(out.returncode, rr.EXIT_REJECTED, bad)
            self.assertIn(why, fields["ERROR"])
        self.assertFalse(os.path.exists(os.path.join(self.root, self.REPORT)))

    def test_stale_round_number_is_rejected(self):
        out, fields = self.file_answer({"summary": "x", "proposals": []}, number=2)
        self.assertEqual(out.returncode, rr.EXIT_REJECTED)
        self.assertIn("--round must be 1", fields["ERROR"])

    def test_fallback_reason_is_recorded_and_reduced_to_shell_safe_text(self):
        out, fields = self.file_answer({"summary": "x", "proposals": []}, "--reason", "Codex exited `1` $(boom)")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual(fields["REVIEWER"], "Claude (fallback — Codex exited 1 (boom))")
        self.assertIn("Reviewer: Claude (fallback — Codex exited 1 (boom))", self.read(self.REPORT))

    def test_unavailable_round_keeps_earlier_open_proposals_visible(self):
        self.file_answer({"summary": "x", "proposals": [proposal()]})
        out, fields = self.run_helper("file", "--unavailable", "--reason", "no reviewer could run")
        self.assertEqual(out.returncode, 0, out.stdout)
        self.assertEqual((fields["VERDICT"], fields["LATEST"], fields["OPEN"]), ("CHANGES PROPOSED", "unavailable", "DR-03-1"))
        self.decide(("DR-03-1", "ACCEPTED"))
        self.assertEqual(self.status()["verdict"], "UNAVAILABLE")
        out, fields = self.run_helper("file", "--unavailable")
        self.assertEqual(out.returncode, rr.EXIT_REJECTED)

    def test_only_rows_of_the_log_table_close_a_proposal(self):
        self.file_answer({"summary": "x", "proposals": [proposal()]})
        self.write("docs/architecture.md", ARCHITECTURE + "\nDR-03-1 ACCEPTED in prose, not in the table\n| DR-03-1 | 2026-10-06 | ACCEPTED | outside the log section |\n")
        self.assertEqual(self.status()["open"], ["DR-03-1"])
        self.decide(("DR-03-1", "ACCEPTED"))
        self.assertEqual(self.status()["open"], [])

    def test_preconditions(self):
        os.remove(os.path.join(self.root, "docs", "architecture.md"))
        out, fields = self.run_helper("brief")
        self.assertEqual(out.returncode, rr.EXIT_PRECONDITION)
        self.assertIn("design phase", fields["ERROR"])
        self.write("docs/architecture.md", ARCHITECTURE)
        self.write("docs/sprints/.current-sprint", "banana\n")
        out, fields = self.run_helper("status")
        self.assertEqual(out.returncode, rr.EXIT_PRECONDITION)

    def test_status_before_any_round_and_missing_sprint_file(self):
        os.remove(os.path.join(self.root, "docs", "sprints", ".current-sprint"))
        st = self.status()
        self.assertEqual((st["rounds"], st["verdict"], st["open"], st["sprint"], st["kind"]), (0, None, [], "01", "design"))
        self.assertEqual(self.read("docs/sprints/.current-sprint").strip(), "01")

    def test_pure_verdict(self):
        self.assertEqual(rr.verdict(2, True), "CHANGES PROPOSED")
        self.assertEqual(rr.verdict(0, True), "APPROVED")
        self.assertEqual(rr.verdict(0, False), "UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
