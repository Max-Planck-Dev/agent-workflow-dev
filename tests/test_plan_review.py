"""plan_review.py: Codex-backed review of the development plan with the Claude fallback."""

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from helpers import PLAN_REVIEW, clean_env, load_module

# setup.sh copies every file in a skill directory: keep bytecode out of it.
sys.dont_write_bytecode = True
pr = load_module("plan_review", PLAN_REVIEW)

FAKE_CODEX = r'''#!/bin/bash
if [ "$1" = "--version" ]; then echo "codex-cli 9.9.9"; exit 0; fi
out=""; dir=""; args="$*"
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift ;;
    -C) dir="$2"; shift ;;
  esac
  shift
done
echo "$args" > "$FAKE_CODEX_LOG.args"
cat > "$FAKE_CODEX_LOG.prompt"
(cd "$dir" && find . -type f | sort) > "$FAKE_CODEX_LOG.files"
cp "$dir/code-inventory.txt" "$FAKE_CODEX_LOG.inventory" 2>/dev/null
case "${FAKE_CODEX_MODE:-ok}" in
  ok)      cp "$FAKE_CODEX_ANSWER" "$out" ;;
  fail)    echo "ERROR: 401 Unauthorized"; exit 1 ;;
  garbage) echo "I could not review this." > "$out" ;;
esac
'''

ARCHITECTURE = """# Architecture Document

## Components

| ID | Path | Kind | Git repo | CI workflow | Stack |
|----|------|------|----------|-------------|-------|
| api | `backend` | service | (none) | `.github/workflows/api.yml` | NestJS |

### Excluded Paths

| Path | Reason |
|------|--------|
| `other-client` | Different product |

## Data Models
Card { id, title }
"""

PLAN = """# Development Plan — Sprint 03

## Implementation Order
1. `api`

## story-001: Create cards
| # | Task | Files | Covers AC |
|---|------|-------|-----------|
| 1 | modify | `backend/src/cards.ts` | AC1 |
"""


def proposal(title="Task 1 names a file that does not exist", severity="HIGH"):
    return {"title": title, "severity": severity, "section": "story-001",
            "problem": "backend/src/card.ts is not in the inventory.", "proposal": "Point the task at backend/src/cards.ts."}


class PlanReviewRunTests(unittest.TestCase):
    REPORT = "docs/sprints/sprint-03/plan-review.md"
    PLAN_PATH = "docs/sprints/sprint-03/dev-plan.md"
    SAFE = r"^[A-Za-z0-9 .,:;()/_=+@%—-]+$"

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "project")
        self.bin = os.path.join(self.tmp, "bin")
        for d in ("docs/sprints/sprint-03", "docs/stories", "backend/src", "backend/node_modules/x", "other-client", ".claude"):
            os.makedirs(os.path.join(self.root, d))
        os.makedirs(self.bin)
        self.write("docs/sprints/.current-sprint", "03\n")
        self.write("docs/architecture.md", ARCHITECTURE)
        self.write("docs/prd.md", "# PRD\n")
        self.write("docs/stories/story-001.md", "# Create cards\n")
        self.write(self.PLAN_PATH, PLAN)
        self.write("backend/src/cards.ts", "export const cards = [];\n")
        self.write("backend/.env", "DB_PASSWORD=hunter2\n")
        self.write("backend/node_modules/x/index.js", "// dep\n")
        self.write("other-client/secret.txt", "not ours\n")
        self.log = os.path.join(self.tmp, "fake")
        self.answer_path = os.path.join(self.tmp, "answer.json")
        path = os.path.join(self.bin, "codex")
        with open(path, "w") as fh:
            fh.write(FAKE_CODEX)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def run_review(self, command="run", answer=None, mode="ok", path=None, extra=(), stdin=None):
        if answer is not None:
            with open(self.answer_path, "w", encoding="utf-8") as fh:
                json.dump(answer, fh)
        env = clean_env(PATH=path if path is not None else self.bin + os.pathsep + "/usr/bin:/bin",
                        FAKE_CODEX_MODE=mode, FAKE_CODEX_LOG=self.log, FAKE_CODEX_ANSWER=self.answer_path)
        out = subprocess.run([sys.executable, PLAN_REVIEW, command, "--root", self.root, *extra],
                             input=stdin, capture_output=True, text=True, env=env, timeout=60)
        fields = dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line and not line.startswith(" "))
        return out, fields

    def file_answer(self, answer, reason="Codex CLI not installed", round=None):
        number = self.status()["rounds"] + 1 if round is None else round
        return self.run_review(command="file", stdin=json.dumps(answer), extra=("--round", str(number), "--reason", reason),
                               path=os.path.join(self.tmp, "empty"))

    def status(self):
        return json.loads(self.run_review(command="status")[0].stdout)

    def decide(self, *rows):
        table = "\n## Plan Review Log\n| Proposal | Date | Disposition | Rationale / What changed |\n|---|---|---|---|\n"
        table += "".join(f"| {pid} | 2026-10-16 | {disp} | because |\n" for pid, disp in rows)
        self.write(self.PLAN_PATH, PLAN + table)

    def report_exists(self):
        return os.path.exists(os.path.join(self.root, self.REPORT))

    def assert_fallback(self, out, fields, contains=""):
        self.assertEqual(out.returncode, pr.EXIT_FALLBACK, out.stdout + out.stderr)
        self.assertRegex(fields["FALLBACK"], self.SAFE)
        self.assertIn(contains, fields["FALLBACK"])
        self.assertFalse(self.report_exists())

    # ── Codex reviews ──

    def test_first_round_files_proposals_with_stable_ids(self):
        out, f = self.run_review(answer={"summary": "One gap.", "proposals": [proposal(), proposal("Order web after api", "LOW")]})
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual((f["VERDICT"], f["OPEN"], f["REPORT"]), ("CHANGES PROPOSED", "PR-03-1,PR-03-2", self.REPORT))
        report = self.read(self.REPORT)
        self.assertIn("# Plan Review — Sprint 03", report)
        self.assertIn("**Verdict:** CHANGES PROPOSED", report)
        self.assertIn("Reviewer: OpenAI Codex (codex-cli 9.9.9, read-only sandbox)", report)
        self.assertIn("| PR-03-1 | HIGH | Task 1 names a file that does not exist | story-001 |", report)
        self.assertIn("`## Plan Review Log` of `docs/sprints/sprint-03/dev-plan.md`", report)

    def test_codex_gets_the_plan_the_docs_and_an_inventory_but_no_code(self):
        self.run_review(answer={"summary": "ok", "proposals": []})
        with open(self.log + ".files") as fh:
            files = sorted(l.strip()[2:] for l in fh if l.strip())
        self.assertEqual(files, ["code-inventory.txt", "docs/architecture.md", "docs/prd.md",
                                 "docs/sprints/sprint-03/dev-plan.md", "docs/stories/story-001.md"])
        with open(self.log + ".inventory") as fh:
            lines = fh.read().splitlines()
        self.assertTrue(lines[0].startswith("# Source files that exist today"))
        inventory = [l for l in lines if not l.startswith("#")]
        # Paths only: a secret-looking name is listed (it exists), dependency dirs and excluded paths are not.
        self.assertEqual(inventory, ["backend/.env", "backend/src/cards.ts"])
        with open(self.log + ".prompt") as fh:
            prompt = fh.read()
        self.assertIn("code-inventory.txt", prompt)
        self.assertIn("review round 1 of sprint 03", prompt)
        self.assertNotIn("Plan Review Log", prompt)

    def test_second_round_continues_ids_and_closes_decided_proposals(self):
        self.run_review(answer={"summary": "s", "proposals": [proposal(), proposal("Second", "LOW")]})
        self.decide(("PR-03-1", "ACCEPTED"), ("PR-03-2", "REJECTED"))
        _, f = self.run_review(answer={"summary": "s2", "proposals": [proposal("Third", "MEDIUM")]})
        self.assertEqual((f["ROUND"], f["OPEN"]), ("2", "PR-03-3"))
        with open(self.log + ".prompt") as fh:
            self.assertIn("Plan Review Log", fh.read())
        self.decide(("PR-03-1", "ACCEPTED"), ("PR-03-2", "REJECTED"), ("PR-03-3", "PARTIAL"))
        _, f = self.run_review(answer={"summary": "s3", "proposals": []})
        self.assertEqual((f["VERDICT"], f["ROUND"], f["OPEN"]), ("APPROVED", "3", ""))

    def test_hostile_text_cannot_fake_a_round_or_a_row(self):
        nasty = proposal("a | b")
        nasty["problem"] = "x\n## Round 9 — 2026-01-01\n| PR-03-9 | LOW | x |"
        _, f = self.run_review(answer={"summary": "## Round 7 — x", "proposals": [nasty]})
        self.assertEqual((f["ROUND"], f["OPEN"]), ("1", "PR-03-1"))
        self.assertEqual(self.status()["rounds"], 1)

    # ── Fallback ──

    def test_no_codex_opt_out_and_failures_ask_for_the_fallback(self):
        out, f = self.run_review(path=os.path.join(self.tmp, "empty"))
        self.assert_fallback(out, f, "Codex CLI not installed")
        self.write(".claude/no-codex", "")
        out, f = self.run_review(answer={"summary": "s", "proposals": []}, extra=("--skip-if-exists", ".claude/no-codex"))
        self.assert_fallback(out, f, "Codex disabled for this project")
        out, f = self.run_review(mode="fail")
        self.assert_fallback(out, f, "codex login")
        out, f = self.run_review(mode="garbage")
        self.assert_fallback(out, f, "not valid JSON")
        out, f = self.run_review(answer={"summary": "s", "proposals": [proposal(severity="URGENT")]})
        self.assert_fallback(out, f, "unknown severity")

    def test_brief_lists_docs_inventory_and_schema(self):
        out, _ = self.run_review(command="brief", path=os.path.join(self.tmp, "empty"))
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertIn("- docs/sprints/sprint-03/dev-plan.md", out.stdout)
        self.assertIn("- backend/src/cards.ts", out.stdout)
        self.assertIn("# Not listed: files git ignores", out.stdout)
        self.assertNotIn("other-client", out.stdout)
        self.assertNotIn("- backend/node_modules", out.stdout)
        self.assertIn('"additionalProperties": false', out.stdout)
        self.assertIn("--round 1", out.stdout)

    def test_inventory_dedupes_overlapping_components_and_marks_truncation(self):
        arch = ARCHITECTURE.replace("| api | `backend` |", "| app | `.` |\n| api | `backend` |")
        self.write("docs/architecture.md", arch)
        paths = pr.inventory(self.root, arch)
        self.assertEqual(paths.count("backend/src/cards.ts"), 1)
        self.assertNotIn("other-client/secret.txt", paths)
        self.assertNotIn("docs/prd.md", paths)
        original = pr.MAX_INVENTORY_FILES
        pr.MAX_INVENTORY_FILES = 1
        try:
            paths = pr.inventory(self.root, arch)
        finally:
            pr.MAX_INVENTORY_FILES = original
        self.assertEqual(len(paths), 2)
        self.assertTrue(paths[-1].startswith("# truncated at 1 files"))

    def test_external_component_gets_a_sanitized_label(self):
        outside = os.path.join(self.tmp, "elsewhere")
        os.makedirs(outside)
        with open(os.path.join(outside, "e.ts"), "w") as fh:
            fh.write("x\n")
        arch = ARCHITECTURE.replace("| api | `backend` |", "| api | `backend` |\n| ../pwn | `" + outside + "` |")
        self.assertIn("external/2-pwn/e.ts", pr.inventory(self.root, arch))

    def test_fallback_answer_is_filed_and_validated(self):
        out, f = self.file_answer({"summary": "One gap.", "proposals": [proposal()]})
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual((f["VERDICT"], f["OPEN"], f["LATEST"]), ("CHANGES PROPOSED", "PR-03-1", "ok"))
        self.assertIn("**Reviewer:** Claude (fallback — Codex CLI not installed)", self.read(self.REPORT))
        out, f = self.file_answer({"summary": "s", "proposals": [proposal()]}, round=1)  # stale round
        self.assertEqual(out.returncode, pr.EXIT_REJECTED)
        self.assertIn("--round must be 2", f["ERROR"])
        out, _ = self.file_answer({"proposals": []})
        self.assertEqual(out.returncode, pr.EXIT_REJECTED)

    def test_unavailable_round(self):
        out, f = self.run_review(command="file", extra=("--unavailable", "--reason", "no usable answer"))
        self.assertEqual(out.returncode, 0)
        self.assertEqual((f["VERDICT"], f["LATEST"]), ("UNAVAILABLE", "unavailable"))
        self.assertIn("— unavailable", self.read(self.REPORT))

    # ── State and preconditions ──

    def test_only_the_log_table_closes_a_proposal(self):
        self.run_review(answer={"summary": "s", "proposals": [proposal(), proposal("Second")]})
        self.write(self.PLAN_PATH, PLAN + "\nWe considered PR-03-1.\n\n## Plan Review Log\n| P | D | Disposition | R |\n|---|---|---|---|\n| PR-03-2 | x | maybe | hmm |\n")
        self.assertEqual(self.status()["open"], ["PR-03-1", "PR-03-2"])

    def link_docs_into_component(self):
        """A project whose docs live in a component repo links them in: a
        file link (docs/prd.md) and a directory link (docs/stories)."""
        real = os.path.join(self.root, "backend", "docs")
        os.makedirs(real)
        shutil.move(os.path.join(self.root, "docs", "prd.md"), os.path.join(real, "prd.md"))
        shutil.move(os.path.join(self.root, "docs", "stories"), os.path.join(real, "stories"))
        os.symlink(os.path.join("..", "backend", "docs", "prd.md"), os.path.join(self.root, "docs", "prd.md"))
        os.symlink(os.path.join("..", "backend", "docs", "stories"), os.path.join(self.root, "docs", "stories"))

    def test_docs_linked_from_inside_the_project_reach_codex_but_escaping_links_do_not(self):
        self.link_docs_into_component()
        os.makedirs(os.path.join(self.root, "docs", "ux"))
        os.symlink("/etc/hosts", os.path.join(self.root, "docs", "ux", "story-001-design.md"))
        out, _ = self.run_review(answer={"summary": "ok", "proposals": []})
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        with open(self.log + ".files") as fh:
            files = sorted(l.strip()[2:] for l in fh if l.strip())
        self.assertEqual(files, ["code-inventory.txt", "docs/architecture.md", "docs/prd.md",
                                 "docs/sprints/sprint-03/dev-plan.md", "docs/stories/story-001.md"])
        brief = self.run_review(command="brief", path=os.path.join(self.tmp, "empty"))[0].stdout
        self.assertIn("- docs/prd.md", brief)
        self.assertIn("- docs/stories/story-001.md", brief)
        self.assertNotIn("story-001-design.md", brief)

    def test_the_plan_may_be_a_link_inside_the_project_but_not_outside(self):
        real = os.path.join(self.root, "backend", "docs")
        os.makedirs(real)
        shutil.move(os.path.join(self.root, self.PLAN_PATH), os.path.join(real, "dev-plan.md"))
        plan = os.path.join(self.root, self.PLAN_PATH)
        os.symlink(os.path.join("..", "..", "..", "backend", "docs", "dev-plan.md"), plan)
        out, _ = self.run_review(answer={"summary": "ok", "proposals": []})
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        os.unlink(plan)
        os.symlink("/etc/hosts", plan)
        out, f = self.run_review(answer={"summary": "ok", "proposals": []})
        self.assertEqual(out.returncode, pr.EXIT_PRECONDITION)
        self.assertIn("dev-plan.md", f["ERROR"])

    def test_preconditions(self):
        os.remove(os.path.join(self.root, self.PLAN_PATH))
        out, f = self.run_review(answer={"summary": "s", "proposals": []})
        self.assertEqual(out.returncode, pr.EXIT_PRECONDITION)
        self.assertIn("dev-plan.md", f["ERROR"])
        self.write(self.PLAN_PATH, PLAN)
        os.remove(os.path.join(self.root, "docs", "architecture.md"))
        out, f = self.run_review(answer={"summary": "s", "proposals": []})
        self.assertEqual(out.returncode, pr.EXIT_PRECONDITION)
        self.assertIn("architecture.md", f["ERROR"])


class StateTests(unittest.TestCase):
    def test_verdict(self):
        self.assertEqual(pr.verdict(1, True), "CHANGES PROPOSED")
        self.assertEqual(pr.verdict(0, True), "APPROVED")
        self.assertEqual(pr.verdict(0, False), "UNAVAILABLE")

    def test_script_is_prefix_free(self):
        with open(PLAN_REVIEW, encoding="utf-8") as fh:
            self.assertNotIn("maxPlanck", fh.read())


if __name__ == "__main__":
    unittest.main()
