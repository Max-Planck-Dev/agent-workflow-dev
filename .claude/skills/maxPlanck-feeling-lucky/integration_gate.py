#!/usr/bin/env python3
"""Integration gate for the agent workflow.

Stories are verified one at a time with quick checks (typecheck, lint, the
tests related to the files changed). Once the last story of the sprint is
approved, this gate builds every in-scope component once, so a break between
stories surfaces before the security audit — and QA, which runs the full
suites, never starts on code that does not build.

    python3 integration_gate.py run    [--root DIR] [--timeout SECONDS] [--budget SECONDS]
    python3 integration_gate.py status [--root DIR]

Components are the rows of the `## Components` table of docs/architecture.md
whose Kind is not `infra` (without that table: the whole root as `app`, path
`.`); nothing under `### Excluded Paths` is ever touched. Each one's command is
the `- Build:` line of its `### <ID>` subsection under `## Build & Run
Commands` (with a single component and no subsections, the section's own
`- Build:` line). It runs from the component's directory with CI=1, killed
after --timeout seconds (default 300 per component). All builds together get
at most --budget seconds (default 540, under the 10-minute ceiling of the
calling Bash tool): a build is cut short when the budget runs out, and one
that cannot start for lack of budget is a TIMEOUT too, so the gate always
finishes and reports.

Per component: PASS (exit 0), FAIL (non-zero exit), TIMEOUT, MISSING (the path
does not exist), SKIP (no Build line). The gate is FAIL when any component is
FAIL, TIMEOUT or MISSING, or when none passed — never an empty PASS.

Every run appends an `## Attempt <k>` section to
docs/sprints/sprint-NN/integration-gate.md, with the tail of each failure's
output: that report is the developer's work order when the gate fails. The
calling context gets only KEY=VALUE lines:

    GATE=PASS|FAIL  ATTEMPT=<k>  COMPONENT=<id>:<result> (one per component)  REPORT=<path>

`status` prints {"sprint", "attempts", "verdict"} as JSON. Standard library only.

Exit codes: 0 the gate ran (its verdict is in GATE=), 2 a precondition failed.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time
from typing import List, NamedTuple, Optional, Tuple

DEFAULT_TIMEOUT_S = 300
TOTAL_BUDGET_S = 540  # every build together, under the 10-minute ceiling of the calling Bash tool
TAIL_LINES = 60
MAX_TAIL_CHARS = 16 * 1024
REPORT_NAME = "integration-gate.md"
FAILING = ("FAIL", "TIMEOUT", "MISSING")

EXIT_PRECONDITION = 2

SPRINT_RE = re.compile(r"^\d{2,3}$")
ATTEMPT_RE = re.compile(r"^## Attempt (\d+) — .*$", re.M)
ATTEMPT_VERDICT_RE = re.compile(r"^Verdict: (PASS|FAIL)\s*$", re.M)
BUILD_LINE_RE = re.compile(r"^\s*[-*]\s*Build:\s*(.+?)\s*$")
CELL_SPLIT_RE = re.compile(r"(?<!\\)\|")
CONTROL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]+")


class Precondition(Exception):
    pass


class Component(NamedTuple):
    cid: str
    path: str
    command: Optional[str]


# ── Architecture doc (pure functions) ────────────────────


def cells(row: str) -> List[str]:
    return [c.strip() for c in CELL_SPLIT_RE.split(row.strip())[1:-1]]


def unquote(text: str) -> str:
    return text.strip().strip("`").strip()


def is_heading(line: str, heading: str, level: str) -> bool:
    return line == f"{level} {heading}" or line.startswith(f"{level} {heading} ")


def has_section(doc: str, heading: str, level: str) -> bool:
    return any(is_heading(line.strip(), heading, level) for line in doc.splitlines())


def table(doc: str, heading: str, level: str) -> List[List[str]]:
    """Every row of the first table under `heading`, header included, rule rows left out."""
    rows, inside = [], False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            if inside:
                break
            inside = is_heading(stripped, heading, level)
            continue
        if not inside or not stripped.startswith("|"):
            continue
        row = cells(stripped)
        if row and not set("".join(row)) <= {"-", ":", " "}:
            rows.append(row)
    return rows


def section(doc: str, heading: str) -> List[str]:
    """The lines of a `## heading` section, its `###` subsections included."""
    out, inside = [], False
    for line in doc.splitlines():
        stripped = line.strip()
        if stripped.startswith("## ") or stripped == "##":
            inside = is_heading(stripped, heading, "##")
            continue
        if inside:
            out.append(line)
    return out


def components(architecture: str) -> List[Tuple[str, str]]:
    """(ID, path) of every in-scope component that is not infra; the whole root without a table."""
    rows = table(architecture, "Components", "##")
    if not rows:
        if has_section(architecture, "Components", "##"):
            raise Precondition("docs/architecture.md has a ## Components section but no component rows could be read from it")
        return [("app", ".")]
    header = [unquote(c).lower() for c in rows[0]]
    col = {name: header.index(name) if name in header else i for i, name in enumerate(("id", "path", "kind"))}
    found = []
    for row in rows[1:]:
        cid, path = (unquote(row[col[k]]) if col[k] < len(row) else "" for k in ("id", "path"))
        kind = unquote(row[col["kind"]]).lower() if col["kind"] < len(row) else ""
        if cid and path and kind != "infra":
            found.append((cid, path))
    if not found and len(rows) == 1:
        raise Precondition("docs/architecture.md has a ## Components section but no component rows could be read from it")
    return found


def excluded_paths(architecture: str) -> List[str]:
    return [unquote(r[0]) for r in table(architecture, "Excluded Paths", "###")[1:] if r and unquote(r[0]) not in ("", "...")]


def build_commands(architecture: str, ids: List[str]) -> dict:
    """Component ID → its `- Build:` command, from `## Build & Run Commands`."""
    found, current, loose = {}, None, None
    for line in section(architecture, "Build & Run Commands"):
        stripped = line.strip()
        if stripped.startswith("### "):
            title = unquote(stripped[4:])
            # The longest ID that names the heading wins: `### api-v2` is api-v2's, not api's.
            current = next((cid for cid in sorted(ids, key=len, reverse=True)
                            if title == cid or re.match(rf"`?{re.escape(cid)}`?[\s(:—]", title)), "")
            continue
        m = BUILD_LINE_RE.match(line)
        if not m:
            continue
        if current:
            found.setdefault(current, unquote(m.group(1)))
        elif current is None and loose is None:
            loose = unquote(m.group(1))
    if len(ids) == 1 and ids[0] not in found and loose:
        found[ids[0]] = loose
    return found


def under(path: str, ancestor: str) -> bool:
    path, ancestor = os.path.normcase(path), os.path.normcase(ancestor)
    return path == ancestor or path.startswith(ancestor.rstrip(os.sep) + os.sep)


def plan(root: str, architecture: str) -> List[Component]:
    listed = components(architecture)
    commands = build_commands(architecture, [cid for cid, _ in listed])
    excluded = [os.path.normpath(os.path.join(root, p)) for p in excluded_paths(architecture)]
    for cid, path in listed:
        base = os.path.normpath(os.path.join(root, path))
        for ex in excluded:
            if under(base, ex):
                raise Precondition(f"component {cid} ({path}) lies under excluded path {os.path.relpath(ex, root)} — fix the Components table")
    return [Component(cid, path, commands.get(cid)) for cid, path in listed]


# ── Running ──────────────────────────────────────────────


def run_build(cwd: str, command: str, timeout: int) -> Tuple[str, str, float]:
    """(result, output, seconds) of one Build command run from the component's directory."""
    started = time.monotonic()
    try:
        proc = subprocess.Popen(command, shell=True, cwd=cwd, env={**os.environ, "CI": "1"}, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, errors="replace",
                                start_new_session=True)
    except OSError as exc:
        return "FAIL", f"could not start the command: {exc}", time.monotonic() - started
    try:
        output, _ = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        output, _ = proc.communicate()
        return "TIMEOUT", (output or "") + f"\n[killed after {timeout}s]", time.monotonic() - started
    return ("PASS" if proc.returncode == 0 else "FAIL"), (output or "") + f"\n[exit status {proc.returncode}]", time.monotonic() - started


def tail(output: str) -> str:
    """The last lines of a build's output, unable to pass for a heading or
    a verdict line of the report (those start a line; a space defuses them)."""
    lines = CONTROL_RE.sub("", output).rstrip("\n").splitlines()[-TAIL_LINES:]
    text = "\n".join(" " + l if l.startswith(("#", "Verdict:")) else l for l in lines)
    return text[-MAX_TAIL_CHARS:]


def gate_verdict(results: List[str]) -> str:
    if any(r in FAILING for r in results) or "PASS" not in results:
        return "FAIL"
    return "PASS"


# ── Report ───────────────────────────────────────────────


def read(path: str) -> str:
    try:
        with open(path, encoding="utf-8") as fh:
            return fh.read()
    except FileNotFoundError:
        return ""


def current_sprint(root: str) -> str:
    sprint = read(os.path.join(root, "docs", "sprints", ".current-sprint")).strip()
    if not SPRINT_RE.match(sprint):
        raise Precondition(f"docs/sprints/.current-sprint holds {sprint!r}, expected a sprint number like 02")
    return sprint


def report_path(root: str, sprint: str) -> str:
    return os.path.join(root, "docs", "sprints", f"sprint-{sprint}", REPORT_NAME)


def cell(text: str) -> str:
    return " ".join(CONTROL_RE.sub(" ", text).split()).replace("|", "\\|")


def fence(text: str) -> str:
    longest = max((len(m) for m in re.findall(r"`+", text)), default=0)
    return "`" * max(3, longest + 1)


def attempt_section(number: int, date: str, rows: List[Tuple[Component, str, str, float]], verdict: str) -> str:
    lines = [f"## Attempt {number} — {date}", "", f"Verdict: {verdict}", "",
             "| Component | Path | Command | Result | Seconds |", "|-----------|------|---------|--------|---------|"]
    for comp, result, _, seconds in rows:
        command = f"`{cell(comp.command)}`" if comp.command else "(no Build line)"
        lines.append(f"| {cell(comp.cid)} | {cell(comp.path)} | {command} | {result} | {seconds:.1f} |")
    if "PASS" not in [r for _, r, _, _ in rows]:
        lines += ["", "No component was built: a gate that builds nothing does not pass."]
    for comp, result, output, _ in rows:
        if result in FAILING:
            body = tail(output)
            mark = fence(body)
            lines += ["", f"### {cell(comp.cid)} — {result}", "", f"Last {TAIL_LINES} lines of output:", "", mark, body, mark]
    return "\n".join(lines) + "\n"


def render(sprint: str, attempts: int, verdict: str, body: str) -> str:
    head = [f"# Integration Gate — Sprint {sprint}", "",
            f"**Sprint:** {sprint}",
            f"**Verdict:** {verdict}",
            f"**Attempts:** {attempts}", "",
            "Written by the orchestrator: every in-scope component built once, after the last story and after each fix pass.", ""]
    return "\n".join(head) + "\n" + body.rstrip("\n") + "\n"


def earlier_attempts(report: str) -> Tuple[int, str]:
    found = list(ATTEMPT_RE.finditer(report))
    return len(found), (report[found[0].start():] if found else "")


def latest_verdict(report: str) -> Optional[str]:
    found = list(ATTEMPT_RE.finditer(report))
    if not found:
        return None
    m = ATTEMPT_VERDICT_RE.search(report, found[-1].start())
    return m.group(1) if m else None


def safe_id(cid: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", cid) or "component"


# ── Commands ─────────────────────────────────────────────


def cmd_run(root: str, timeout: int, budget: int) -> int:
    sprint = current_sprint(root)
    architecture = read(os.path.join(root, "docs", "architecture.md"))
    if not architecture:
        raise Precondition("docs/architecture.md does not exist — run the design phase first")
    if timeout < 1 or budget < 1:
        raise Precondition("--timeout and --budget must be at least 1 second")
    deadline = time.monotonic() + budget
    rows = []
    for comp in plan(root, architecture):
        cwd = os.path.normpath(os.path.join(root, comp.path))
        if not os.path.isdir(cwd):
            rows.append((comp, "MISSING", f"{comp.path} does not exist", 0.0))
        elif not comp.command:
            rows.append((comp, "SKIP", "", 0.0))
        elif deadline - time.monotonic() < 1:
            rows.append((comp, "TIMEOUT", f"not started: the gate's {budget}s budget ran out", 0.0))
        else:
            rows.append((comp, *run_build(cwd, comp.command, min(timeout, int(deadline - time.monotonic())))))
    verdict = gate_verdict([r for _, r, _, _ in rows])

    path = report_path(root, sprint)
    count, body = earlier_attempts(read(path))
    number = count + 1
    body += ("\n" if body else "") + attempt_section(number, time.strftime("%Y-%m-%d %H:%M:%S"), rows, verdict)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    partial = path + ".tmp"
    with open(partial, "w", encoding="utf-8") as fh:
        fh.write(render(sprint, number, verdict, body))
    os.replace(partial, path)

    print(f"GATE={verdict}")
    print(f"ATTEMPT={number}")
    for comp, result, _, _ in rows:
        print(f"COMPONENT={safe_id(comp.cid)}:{result}")
    print(f"REPORT={os.path.relpath(path, root)}")
    return 0


def cmd_status(root: str) -> int:
    sprint = current_sprint(root)
    report = read(report_path(root, sprint))
    print(json.dumps({"sprint": sprint, "attempts": earlier_attempts(report)[0], "verdict": latest_verdict(report)}))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Build every in-scope component once and record the result.")
    ap.add_argument("command", choices=("run", "status"))
    ap.add_argument("--root", default=".", help="project root (default: current directory)")
    ap.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT_S, help="run: seconds each component's build may take")
    ap.add_argument("--budget", type=int, default=TOTAL_BUDGET_S, help="run: seconds all builds together may take")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.root)
    try:
        if args.command == "run":
            return cmd_run(root, args.timeout, args.budget)
        return cmd_status(root)
    except Precondition as exc:
        print(f"ERROR={exc}")
        return EXIT_PRECONDITION


if __name__ == "__main__":
    sys.exit(main())
