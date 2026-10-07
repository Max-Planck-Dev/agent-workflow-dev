import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest

from helpers import DESIGN_REVIEW, clean_env, load_module

# setup.sh copies every file in a skill directory: keep bytecode out of it.
sys.dont_write_bytecode = True
dr = load_module("design_review", DESIGN_REVIEW)

FAKE_CODEX = r'''#!/bin/bash
# Fake codex: records how it was called, then behaves per $FAKE_CODEX_MODE.
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
echo "$dir" > "$FAKE_CODEX_LOG.dir"
case "${FAKE_CODEX_MODE:-ok}" in
  ok)      cp "$FAKE_CODEX_ANSWER" "$out" ;;
  fail)    echo "ERROR: 401 Unauthorized"; exit 1 ;;
  garbage) echo "I could not review this." > "$out" ;;
  hang)    sleep 30 ;;
esac
'''

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


class DesignReviewRunTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "project")
        self.bin = os.path.join(self.tmp, "bin")
        os.makedirs(os.path.join(self.root, "docs", "sprints"))
        os.makedirs(os.path.join(self.root, "docs", "stories"))
        os.makedirs(os.path.join(self.root, "other-client"))
        os.makedirs(self.bin)
        self.write("docs/sprints/.current-sprint", "03\n")
        self.write("docs/architecture.md", ARCHITECTURE)
        self.write("docs/prd.md", "# PRD\n")
        self.write("docs/stories/story-001.md", "# Story\n")
        self.write("other-client/secret.txt", "not part of this product\n")
        self.log = os.path.join(self.tmp, "fake")
        self.answer_path = os.path.join(self.tmp, "answer.json")
        self.install_codex()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def write(self, rel, text):
        with open(os.path.join(self.root, rel), "w", encoding="utf-8") as fh:
            fh.write(text)

    def read(self, rel):
        with open(os.path.join(self.root, rel), encoding="utf-8") as fh:
            return fh.read()

    def install_codex(self):
        path = os.path.join(self.bin, "codex")
        with open(path, "w") as fh:
            fh.write(FAKE_CODEX)
        os.chmod(path, os.stat(path).st_mode | stat.S_IEXEC)

    def run_review(self, command="run", answer=None, mode="ok", path=None, extra=(), stdin=None):
        if answer is not None:
            with open(self.answer_path, "w", encoding="utf-8") as fh:
                json.dump(answer, fh)
        env = clean_env(PATH=path if path is not None else self.bin + os.pathsep + "/usr/bin:/bin",
                        FAKE_CODEX_MODE=mode, FAKE_CODEX_LOG=self.log, FAKE_CODEX_ANSWER=self.answer_path)
        out = subprocess.run([sys.executable, DESIGN_REVIEW, command, "--root", self.root, *extra],
                             input=stdin, capture_output=True, text=True, env=env, timeout=60)
        fields = dict(line.split("=", 1) for line in out.stdout.splitlines() if "=" in line and not line.startswith(" "))
        return out, fields

    def file_answer(self, answer, *extra, reason="Codex CLI not installed", round=None):
        """The fallback reviewer handing its answer to `file` on stdin."""
        number = self.status()["rounds"] + 1 if round is None else round
        args = ("--round", str(number), "--reason", reason) if reason is not None else ("--round", str(number))
        return self.run_review(command="file", stdin=json.dumps(answer), extra=args + extra, path=os.path.join(self.tmp, "empty"))

    SAFE = r"^[A-Za-z0-9 .,:;()/_=+@%—-]+$"

    def assert_fallback(self, out, fields, contains=""):
        self.assertEqual(out.returncode, dr.EXIT_FALLBACK, out.stdout + out.stderr)
        self.assertRegex(fields["FALLBACK"], self.SAFE)  # an agent pastes this onto a command line
        self.assertIn(contains, fields["FALLBACK"])
        self.assertFalse(self.report_exists())

    def status(self):
        return json.loads(self.run_review(command="status")[0].stdout)

    def decide(self, *rows):
        table = "## Design Review Log\n| Proposal | Date | Disposition | Rationale / What changed |\n|---|---|---|---|\n"
        table += "".join(f"| {pid} | 2026-10-06 | {disp} | because |\n" for pid, disp in rows)
        self.write("docs/architecture.md", ARCHITECTURE.replace("## Change Log", table + "\n## Change Log"))

    REPORT = "docs/sprints/sprint-03/design-review.md"

    def report_exists(self):
        return os.path.exists(os.path.join(self.root, self.REPORT))

    # ── Codex reviews ────────────────────────────────────

    def test_first_round_files_proposals_with_stable_ids(self):
        out, fields = self.run_review(answer={"summary": "Solid, two gaps.", "proposals": [proposal(), proposal("Paginate lists", "LOW")]})
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual(fields["VERDICT"], "CHANGES PROPOSED")
        self.assertEqual(fields["OPEN"], "DR-03-1,DR-03-2")
        self.assertEqual(fields["REPORT"], self.REPORT)
        report = self.read(self.REPORT)
        self.assertIn("**Verdict:** CHANGES PROPOSED", report)
        self.assertIn("**Latest round:** ok", report)
        self.assertIn("Reviewer: OpenAI Codex (codex-cli 9.9.9, read-only sandbox)", report)
        self.assertIn("| DR-03-1 | HIGH | Add optimistic locking | Data Models |", report)
        self.assertIn("- DR-03-2 — LOW — Paginate lists", report)

    def test_codex_reads_a_copy_of_the_docs_only(self):
        self.run_review(answer={"summary": "ok", "proposals": []})
        with open(self.log + ".args") as fh:
            args = fh.read()
        self.assertIn("--sandbox read-only", args)
        self.assertIn("--output-schema", args)
        with open(self.log + ".files") as fh:
            files = fh.read().split()
        self.assertEqual(files, ["./docs/architecture.md", "./docs/prd.md", "./docs/stories/story-001.md"])
        with open(self.log + ".dir") as fh:
            stage = fh.read().strip()
        self.assertFalse(os.path.commonpath([stage, self.root]) == self.root)
        self.assertFalse(os.path.exists(stage))  # temporary copy removed afterwards

    def test_no_proposals_is_approved(self):
        _, fields = self.run_review(answer={"summary": "Nothing to change.", "proposals": []})
        self.assertEqual(fields["VERDICT"], "APPROVED")
        self.assertIn("None.", self.read(self.REPORT))

    def test_second_round_continues_ids_and_closes_decided_proposals(self):
        self.run_review(answer={"summary": "s", "proposals": [proposal(), proposal("Paginate lists", "LOW")]})
        self.decide(("DR-03-1", "ACCEPTED"), ("DR-03-2", "REJECTED"))
        _, fields = self.run_review(answer={"summary": "s2", "proposals": [proposal("Version column lacks a default", "MEDIUM")]})
        self.assertEqual(fields["ROUND"], "2")
        self.assertEqual(fields["OPEN"], "DR-03-3")
        report = self.read(self.REPORT)
        self.assertIn("## Round 1 — ", report)
        self.assertIn("## Round 2 — ", report)
        self.assertIn("| DR-03-1 | HIGH |", report)  # earlier round kept verbatim
        with open(self.log + ".prompt") as fh:
            prompt = fh.read()
        self.assertIn("review round 2 of sprint 03", prompt)
        self.assertIn("Design Review Log", prompt)
        self.decide(("DR-03-1", "ACCEPTED"), ("DR-03-2", "REJECTED"), ("DR-03-3", "PARTIAL"))
        _, fields = self.run_review(answer={"summary": "s3", "proposals": []})
        self.assertEqual((fields["VERDICT"], fields["ROUND"], fields["OPEN"]), ("APPROVED", "3", ""))

    def test_first_round_prompt_has_no_rereview_paragraph(self):
        self.run_review(answer={"summary": "ok", "proposals": []})
        with open(self.log + ".prompt") as fh:
            self.assertNotIn("Design Review Log", fh.read())

    def test_hostile_text_cannot_break_the_table_or_fake_a_round(self):
        nasty = proposal("a | b")
        nasty["problem"] = "line one\n## Round 9 — 2026-01-01\n| DR-03-9 | LOW | x |"
        _, fields = self.run_review(answer={"summary": "s\n## Round 7 — x", "proposals": [nasty]})
        self.assertEqual((fields["ROUND"], fields["OPEN"]), ("1", "DR-03-1"))
        self.assertIn("a \\| b", self.read(self.REPORT))
        self.assertEqual(self.status()["rounds"], 1)

    # ── Codex cannot review: nothing is written, the fallback is asked for ──

    def test_not_installed_asks_for_the_fallback(self):
        out, fields = self.run_review(path=os.path.join(self.tmp, "empty"))
        self.assert_fallback(out, fields, "Codex CLI not installed")

    def test_project_opt_out_asks_for_the_fallback_without_calling_codex(self):
        os.makedirs(os.path.join(self.root, ".claude"))
        self.write(".claude/no-codex", "")
        out, fields = self.run_review(answer={"summary": "s", "proposals": []}, extra=("--skip-if-exists", ".claude/no-codex"))
        self.assert_fallback(out, fields, "Codex disabled for this project")
        self.assertFalse(os.path.exists(self.log + ".args"))
        out, fields = self.run_review(answer={"summary": "s", "proposals": []}, extra=("--skip-if-exists", ".claude/absent"))
        self.assertEqual(out.returncode, 0)

    def test_codex_that_cannot_start_asks_for_the_fallback(self):
        with open(os.path.join(self.bin, "codex"), "wb") as fh:
            fh.write(b"\x00\x01 not a program")
        out, fields = self.run_review()
        self.assert_fallback(out, fields, "could not be started")

    def test_failed_codex_run_asks_for_the_fallback(self):
        out, fields = self.run_review(mode="fail")
        self.assert_fallback(out, fields, "codex login")

    def test_malformed_codex_answers_ask_for_the_fallback(self):
        bad_severity = {"summary": "s", "proposals": [proposal(severity="URGENT")]}
        missing_field = {"summary": "s", "proposals": [{"title": "t", "severity": "LOW"}]}
        extra_key = {"summary": "s", "proposals": [dict(proposal(), note="x")]}
        for mode, answer in (("garbage", None), ("ok", bad_severity), ("ok", missing_field), ("ok", {"proposals": []}), ("ok", extra_key)):
            out, fields = self.run_review(answer=answer, mode=mode)
            self.assert_fallback(out, fields)

    def test_timeout_asks_for_the_fallback(self):
        out, fields = self.run_review(mode="hang", extra=("--timeout", "1"))
        self.assert_fallback(out, fields, "timed out")

    # ── Fallback reviewer ────────────────────────────────

    def test_brief_is_the_same_review_brief_plus_the_schema(self):
        out, _ = self.run_review(command="brief", path=os.path.join(self.tmp, "empty"))
        self.assertEqual(out.returncode, 0)
        self.assertIn("review round 1 of sprint 03", out.stdout)
        self.assertNotIn("Design Review Log", out.stdout)
        self.assertIn('"additionalProperties": false', out.stdout)
        self.assertIn("CRITICAL", out.stdout)
        self.assertIn("--round 1", out.stdout)
        inventory = out.stdout.split("Documents to read", 1)[1]
        listed = [line[2:] for line in inventory.splitlines() if line.startswith("- docs/")]
        self.assertEqual(listed, ["docs/architecture.md", "docs/prd.md", "docs/stories/story-001.md"])
        self.file_answer({"summary": "s", "proposals": [proposal()]})
        out, _ = self.run_review(command="brief", path=os.path.join(self.tmp, "empty"))
        self.assertIn("review round 2 of sprint 03", out.stdout)
        self.assertIn("Design Review Log", out.stdout)
        self.assertIn("--round 2", out.stdout)
        self.assertIn("- docs/sprints/sprint-03/design-review.md", out.stdout)

    def test_fallback_answer_is_filed_like_a_codex_round(self):
        out, fields = self.file_answer({"summary": "Two gaps.", "proposals": [proposal()]})
        self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
        self.assertEqual((fields["VERDICT"], fields["OPEN"], fields["LATEST"]), ("CHANGES PROPOSED", "DR-03-1", "ok"))
        report = self.read(self.REPORT)
        self.assertIn("Reviewer: Claude (fallback — Codex CLI not installed)", report)
        self.assertIn("**Reviewer:** Claude (fallback — Codex CLI not installed)", report)
        self.assertIn("| DR-03-1 | HIGH | Add optimistic locking |", report)

    def test_ids_continue_across_reviewers(self):
        self.run_review(answer={"summary": "s", "proposals": [proposal(), proposal("Second")]})
        self.decide(("DR-03-1", "ACCEPTED"), ("DR-03-2", "REJECTED"))
        _, fields = self.file_answer({"summary": "s2", "proposals": [proposal("Third")]}, reason="Codex timed out after 570s")
        self.assertEqual((fields["ROUND"], fields["OPEN"]), ("2", "DR-03-3"))
        report = self.read(self.REPORT)
        self.assertIn("Reviewer: OpenAI Codex (codex-cli 9.9.9, read-only sandbox)", report)
        self.assertIn("Reviewer: Claude (fallback — Codex timed out after 570s)", report)

    def test_rejected_fallback_answer_writes_nothing(self):
        bad = (
            {"summary": "s", "proposals": [proposal(severity="URGENT")]},
            {"proposals": []},
            "not an object",
            {"summary": "s", "proposals": [], "verdict": "APPROVED"},  # same strictness as Codex's schema
            {"summary": "s", "proposals": [dict(proposal(), note="x")]},
        )
        for answer in bad:
            out, fields = self.file_answer(answer)
            self.assertEqual(out.returncode, dr.EXIT_REJECTED, answer)
            self.assertIn("ERROR", fields)
            self.assertFalse(self.report_exists())
        out, _ = self.run_review(command="file", stdin="{not json", extra=("--round", "1", "--reason", "x"), path=os.path.join(self.tmp, "empty"))
        self.assertEqual(out.returncode, dr.EXIT_REJECTED)

    def test_fallback_must_say_why_and_for_which_round(self):
        good = {"summary": "s", "proposals": [proposal()]}
        for kwargs in ({"reason": None}, {"reason": "`$(;)`"}, {"round": 2}):
            out, fields = self.file_answer(good, **kwargs)
            self.assertEqual(out.returncode, dr.EXIT_REJECTED, kwargs)
            self.assertFalse(self.report_exists())
        self.file_answer(good)
        out, fields = self.file_answer(good, round=1)  # written for a round that is already filed
        self.assertEqual(out.returncode, dr.EXIT_REJECTED)
        self.assertIn("--round must be 2", fields["ERROR"])
        out, _ = self.run_review(command="file", extra=("--unavailable",))
        self.assertEqual(out.returncode, dr.EXIT_REJECTED)

    def test_reason_is_reduced_to_shell_safe_text(self):
        self.file_answer({"summary": "s", "proposals": []}, reason="Codex exited `rm -rf` $(x) 'q' \"q\"")
        self.assertIn("Reviewer: Claude (fallback — Codex exited rm -rf (x) q q)", self.read(self.REPORT))

    def test_unavailable_round(self):
        out, fields = self.run_review(command="file", extra=("--unavailable", "--reason", "no reviewer produced a usable answer"))
        self.assertEqual(out.returncode, 0)
        self.assertEqual((fields["VERDICT"], fields["LATEST"]), ("UNAVAILABLE", "unavailable"))
        report = self.read(self.REPORT)
        self.assertIn("— unavailable", report)
        self.assertIn("Reason: no reviewer produced a usable answer", report)
        self.assertIn("**Latest round:** unavailable", report)

    def test_unavailable_round_keeps_earlier_open_proposals_visible(self):
        self.run_review(answer={"summary": "s", "proposals": [proposal()]})
        _, fields = self.run_review(command="file", extra=("--unavailable", "--reason", "no usable answer"))
        self.assertEqual((fields["VERDICT"], fields["LATEST"], fields["OPEN"]), ("CHANGES PROPOSED", "unavailable", "DR-03-1"))
        self.assertEqual(self.status()["next_id"], 2)

    # ── State ────────────────────────────────────────────

    def test_only_rows_of_the_log_table_close_a_proposal(self):
        self.run_review(answer={"summary": "s", "proposals": [proposal(), proposal("Second")]})
        self.write("docs/architecture.md", ARCHITECTURE
                   + "\nWe considered DR-03-1 but have not decided.\n"
                   + "\n## Other Table\n| Proposal | Date | Disposition |\n|---|---|---|\n| DR-03-1 | x | ACCEPTED |\n"
                   + "\n## Design Review Log\n| Proposal | Date | Disposition | Rationale |\n|---|---|---|---|\n| DR-03-2 | x | maybe | hmm |\n")
        self.assertEqual(self.status()["open"], ["DR-03-1", "DR-03-2"])

    def test_preconditions(self):
        os.remove(os.path.join(self.root, "docs", "architecture.md"))
        for command in ("run", "brief", "file"):
            out, fields = self.run_review(command=command, answer={"summary": "s", "proposals": []}, stdin="{}", extra=("--round", "1", "--reason", "x") if command == "file" else ())
            self.assertEqual(out.returncode, dr.EXIT_PRECONDITION, command)
            self.assertIn("architecture.md", fields["ERROR"])
        self.write("docs/sprints/.current-sprint", "../../etc\n")
        out, _ = self.run_review(command="status")
        self.assertEqual(out.returncode, dr.EXIT_PRECONDITION)

    def test_status_before_any_round(self):
        state = self.status()
        self.assertEqual((state["rounds"], state["verdict"], state["open"], state["next_id"]), (0, None, [], 1))


class StateTests(unittest.TestCase):
    def test_verdict(self):
        self.assertEqual(dr.verdict(2, True), "CHANGES PROPOSED")
        self.assertEqual(dr.verdict(1, False), "CHANGES PROPOSED")
        self.assertEqual(dr.verdict(0, True), "APPROVED")
        self.assertEqual(dr.verdict(0, False), "UNAVAILABLE")

    def test_script_is_prefix_free(self):
        # setup.sh copies it without rewriting the prefix.
        with open(DESIGN_REVIEW, encoding="utf-8") as fh:
            self.assertNotIn("maxPlanck", fh.read())


if __name__ == "__main__":
    unittest.main()
