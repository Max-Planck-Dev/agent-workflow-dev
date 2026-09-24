#!/usr/bin/env python3
"""Live progress dashboard for a maxPlanck agent-workflow run.

Reads logs/agent-workflow.log (the human log every agent and orchestrator
already writes), plus the hook-written logs/pipeline-events.jsonl and the
sprint's pipeline-state.json when present, and renders a phase bar with loop
counts, the current agent with its self-reported PROGRESS, a heartbeat from the
subagent's own transcript, and the log tail. Standard library only.

Usage (from a project root, or anywhere with --cwd):

    python3 pipeline_dashboard.py            # live view, q to quit
    python3 pipeline_dashboard.py --once     # one frame to stdout
    python3 pipeline_dashboard.py --json     # the parsed model as JSON

Inside herdr (HERDR_ENV=1) it also pushes the current phase into the herdr
agent sidebar (`$phase` / `$agent` tokens) and shows a notification when the
run completes.
"""

import argparse
import dataclasses
import json
import os
import re
import select
import shutil
import signal
import subprocess
import sys
import textwrap
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

DEFAULT_PREFIX = "maxPlanck"
PLUGIN_ID = "maxplanck.pipeline"
STALE_AFTER_S = 30 * 60
TAIL_DEFAULT = 8
HERDR_TIMEOUT_S = 2

TS_FMT = "%Y-%m-%d %H:%M:%S"

ROLE_TO_PHASE = {
    "product-owner": "kickoff",
    "ux-designer": "ux",
    "architect": "design",
    "developer": "develop",
    "code-reviewer": "review",
    "security": "audit",
    "devops": "infra",
    "qa-tester": "test",
    "scrum-master": "sprint",
    "release-manager": "report",
}
ROLES = tuple(ROLE_TO_PHASE.keys())
PHASE_ALIASES = {"security": "audit", "devops": "infra", "product-owner": "kickoff"}

ORDERS = {
    "feeling-lucky": ["kickoff", "ux", "design", "develop", "review", "audit", "infra", "test", "sprint"],
    "change": ["kickoff", "design", "develop", "review", "audit", "test", "sprint"],
    "adopt": ["adopt"],
}
OPTIONAL = {"change": {"design", "audit"}}

LINE_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (\w+)\s*\| Agent: ([^|]*?)\s*(?:\| (.*))?$"
)
START_RE = re.compile(
    r"^(Full pipeline started|Starting full pipeline|Change request started|Adoption started)\b"
    r"(?: \(sprint (\d+)\))?(?::\s*(.*)|\s*\|\s*(?:Args|Goal|Feature):\s*(.*))?"
)
COMPLETE_RE = re.compile(
    r"^(Full pipeline complete|Pipeline complete|Change request complete|Adoption complete)\b"
    r"(?: \(sprint (\d+)\))?.*?(?:Unresolved: (\d+))?\s*$"
)
ROUTE_RE = re.compile(
    r"^Phase ([\w-]+)(?: \(([^)]*)\))? (finished|force-advanced) (?:→|->) routing to ([\w-]+)"
    r"(?: \| Reason: (.*))?$"
)
SKIP_RE = re.compile(r"^Phase ([\w-]+) skipped(?: \| Reason: (.*))?$")
PROGRESS_RE = re.compile(r"^(\d+)/(\d+)\s*\|\s*(.*?)(?:\s*\| Output: (.*))?$")
NAMESPACE_RE = re.compile(r"^[a-z0-9_-]+:")
ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")


# ── Model ────────────────────────────────────────────────


@dataclass
class PhaseState:
    name: str
    status: str = "pending"  # pending | queued | running | done | skipped | forced | missed
    runs: int = 0
    started: Optional[float] = None
    finished: Optional[float] = None
    last_reason: Optional[str] = None
    durations: List[float] = field(default_factory=list)


@dataclass
class AgentSession:
    agent: str
    start_ts: float
    stop_ts: Optional[float] = None
    noise: bool = False
    progress: Optional[Tuple[int, int, str]] = None
    events: List[Tuple[float, str, str]] = field(default_factory=list)
    transcript: Optional[str] = None
    agent_id: Optional[str] = None


@dataclass
class Transition:
    ts: float
    src: str
    dst: str
    reason: Optional[str]
    note: Optional[str]
    verb: str


@dataclass
class Run:
    prefix: str = DEFAULT_PREFIX
    kind: Optional[str] = None
    sprint: Optional[str] = None
    description: Optional[str] = None
    started_ts: Optional[float] = None
    completed_ts: Optional[float] = None
    unresolved_count: Optional[int] = None
    order: List[str] = field(default_factory=list)
    optional: List[str] = field(default_factory=list)
    phases: Dict[str, PhaseState] = field(default_factory=dict)
    transitions: List[Transition] = field(default_factory=list)
    loops: List[Transition] = field(default_factory=list)
    agent_sessions: List[AgentSession] = field(default_factory=list)
    tail: List[str] = field(default_factory=list)
    state: str = "idle"  # idle | running | complete | stale
    last_line_ts: Optional[float] = None
    unresolved: List[str] = field(default_factory=list)
    verdicts: Dict[str, Optional[str]] = field(default_factory=dict)
    malformed: int = 0
    now: float = 0.0
    history: Dict[str, List[float]] = field(default_factory=dict)  # phase -> past run durations (all runs in the log)

    def current_session(self) -> Optional[AgentSession]:
        for s in reversed(self.agent_sessions):
            if s.stop_ts is None and not s.noise:
                return s
        return None

    def current_phase(self) -> Optional[str]:
        for name in self.order:
            if self.phases[name].status == "running":
                return name
        for name in self.order:
            if self.phases[name].status == "queued":
                return name
        return None


# ── Parsing ──────────────────────────────────────────────


def parse_ts(ts: str) -> float:
    return time.mktime(time.strptime(ts, TS_FMT))


def parse_line(line: str):
    m = LINE_RE.match(line.rstrip("\n"))
    if not m:
        return None
    ts, action, agent, rest = m.groups()
    return ts, action.upper(), agent.strip(), (rest or "").strip()


def role_of(name: str) -> Optional[str]:
    for role in ROLES:
        if name == role or name.endswith("-" + role):
            return role
    return None


def norm_agent(raw: str, prefix: str) -> Optional[str]:
    """Canonical `<prefix>-<role>` / `orchestrator`, or None for noise."""
    name = NAMESPACE_RE.sub("", raw.strip())
    if not name:
        return None
    if name == "orchestrator":
        return name
    role = role_of(name)
    if role is None:
        return None
    return f"{prefix}-{role}"


def infer_prefix(lines) -> Optional[str]:
    pattern = re.compile(r"Agent: (?:[a-z0-9_-]+:)?([A-Za-z][A-Za-z0-9]*)-(" + "|".join(ROLES) + r")\b")
    counts: Dict[str, int] = {}
    for line in lines:
        m = pattern.search(line)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    if not counts:
        return None
    return max(counts.items(), key=lambda kv: kv[1])[0]


def resolve_prefix(root: str, lines) -> str:
    env = os.environ.get("PIPELINE_DASHBOARD_AGENT_PREFIX")
    if env:
        return env
    try:
        import glob as _glob

        for path in _glob.glob(os.path.join(root, ".claude", "*-workflow-version.json")):
            with open(path, encoding="utf-8") as fh:
                data = json.load(fh)
            if isinstance(data, dict) and data.get("prefix"):
                return str(data["prefix"])
    except Exception:
        pass
    return infer_prefix(lines) or DEFAULT_PREFIX


def canon_phase(name: str) -> str:
    name = name.strip().lower()
    return PHASE_ALIASES.get(name, name)


def _ensure_phase(run: Run, name: str) -> PhaseState:
    if name not in run.phases:
        run.phases[name] = PhaseState(name=name)
    return run.phases[name]


def _open_session(run: Run, agent: str) -> Optional[AgentSession]:
    for s in reversed(run.agent_sessions):
        if s.stop_ts is None and s.agent == agent:
            return s
    return None


def _latest_open(run: Run) -> Optional[AgentSession]:
    for s in reversed(run.agent_sessions):
        if s.stop_ts is None:
            return s
    return None


def parse_log(lines, prefix: str = DEFAULT_PREFIX, now: Optional[float] = None, tail_n: int = TAIL_DEFAULT) -> Run:
    now = time.time() if now is None else now
    run = Run(prefix=prefix, now=now)
    records = []
    for line in lines:
        parsed = parse_line(line)
        if parsed is None:
            if line.strip():
                run.malformed += 1
            continue
        records.append(parsed)

    # Run boundary: the latest start line wins.
    start_idx = None
    for i, (ts, action, agent, rest) in enumerate(records):
        if action == "PIPELINE" and START_RE.match(rest):
            start_idx = i
    window = records[start_idx:] if start_idx is not None else records
    run.history = phase_history(records, prefix)

    for ts, action, agent, rest in window:
        t = parse_ts(ts)
        run.last_line_ts = t
        name = norm_agent(agent, prefix)

        if action == "PIPELINE":
            _apply_pipeline(run, t, rest)
        elif action == "START":
            sess = AgentSession(agent=name or agent or "unknown", start_ts=t, noise=name is None)
            run.agent_sessions.append(sess)
            if name:
                role = role_of(name)
                phase = ROLE_TO_PHASE.get(role) if role else None
                if phase and (phase in run.phases or run.order):
                    ps = _ensure_phase(run, phase)
                    if ps.status != "done" or phase in run.order:
                        ps.status = "running"
                        ps.started = t
        elif action == "STOP":
            sess = _open_session(run, name) if name else None
            if sess is None:
                sess = _latest_open(run)
            if sess is not None:
                sess.stop_ts = t
        elif action == "PROGRESS":
            sess = (_open_session(run, name) if name else None) or _latest_open(run)
            m = PROGRESS_RE.match(rest)
            if sess is not None and m:
                sess.progress = (int(m.group(1)), int(m.group(2)), m.group(3).strip())
            elif sess is not None:
                sess.events.append((t, action, rest))
        else:
            sess = (_open_session(run, name) if name else None) or _latest_open(run)
            if sess is not None and name and not sess.noise:
                text = rest.split(" | Output:")[0].strip()
                sess.events.append((t, action, text))
                sess.events = sess.events[-6:]

    _finalise(run, now)
    run.tail = tail_lines(lines, prefix, tail_n)
    return run


def tail_lines(lines, prefix: str, tail_n: int) -> List[str]:
    """Last N log lines that belong to the workflow (noise subagents dropped)."""
    keep: List[str] = []
    for raw in lines:
        raw = raw.rstrip("\n")
        if not raw.strip():
            continue
        parsed = parse_line(raw)
        if parsed is None:
            continue
        _, action, agent, _ = parsed
        if action == "PIPELINE" or norm_agent(agent, prefix):
            keep.append(raw)
    return keep[-tail_n:]


def phase_history(records, prefix: str) -> Dict[str, List[float]]:
    """Durations of every finished phase run in the log, keyed by phase.

    Used to estimate how far along the current agent is when it has not
    logged PROGRESS: elapsed time against the median of earlier runs of the
    same phase is a ballpark, but a useful one on multi-hour pipelines.
    """
    started: Dict[str, float] = {}
    out: Dict[str, List[float]] = {}
    for ts, action, agent, rest in records:
        t = parse_ts(ts)
        if action == "START":
            name = norm_agent(agent, prefix)
            role = role_of(name) if name else None
            phase = ROLE_TO_PHASE.get(role) if role else None
            if phase:
                started[phase] = t
        elif action == "PIPELINE":
            m = ROUTE_RE.match(rest)
            if m and m.group(3) == "finished":
                phase = canon_phase(m.group(1))
                if phase in started:
                    dur = t - started.pop(phase)
                    if dur > 0:
                        out.setdefault(phase, []).append(dur)
    return out


def median(values: List[float]) -> float:
    vals = sorted(values)
    n = len(vals)
    return vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2


def estimate_progress(run: Run, sess: "AgentSession"):
    """(pct, basis) ballpark for a session without PROGRESS, or None."""
    role = role_of(sess.agent)
    phase = ROLE_TO_PHASE.get(role) if role else None
    if not phase or not run.history.get(phase):
        return None
    typical = median(run.history[phase])
    if typical <= 0:
        return None
    elapsed = max(0.0, run.now - sess.start_ts)
    pct = min(95, int(100 * elapsed / typical))
    return pct, f"est. from {len(run.history[phase])} earlier {phase} run{'s' if len(run.history[phase]) != 1 else ''}, median {fmt_dur(typical)}"


def _apply_pipeline(run: Run, t: float, rest: str) -> None:
    m = START_RE.match(rest)
    if m:
        head, sprint, desc_a, desc_b = m.groups()
        run.kind = {
            "Full pipeline started": "feeling-lucky",
            "Starting full pipeline": "feeling-lucky",
            "Change request started": "change",
            "Adoption started": "adopt",
        }[head]
        run.sprint = sprint
        run.description = (desc_a or desc_b or "").strip() or None
        run.started_ts = t
        run.completed_ts = None
        run.order = list(ORDERS[run.kind])
        run.optional = sorted(OPTIONAL.get(run.kind, set()))
        run.phases = {p: PhaseState(name=p) for p in run.order}
        if run.order:
            run.phases[run.order[0]].status = "queued"
        run.transitions, run.loops, run.agent_sessions = [], [], []
        return

    m = COMPLETE_RE.match(rest)
    if m:
        _, sprint, unresolved = m.groups()
        run.completed_ts = t
        if sprint and not run.sprint:
            run.sprint = sprint
        if unresolved is not None:
            run.unresolved_count = int(unresolved)
        return

    m = ROUTE_RE.match(rest)
    if m:
        src, note, verb, dst, reason = m.groups()
        src, dst = canon_phase(src), canon_phase(dst)
        ps = _ensure_phase(run, src)
        if verb == "finished":
            ps.runs += 1
            ps.status = "done"
        else:
            ps.status = "forced"
        ps.finished = t
        if ps.started:
            ps.durations.append(max(0.0, t - ps.started))
        ps.last_reason = reason
        tr = Transition(ts=t, src=src, dst=dst, reason=reason, note=note, verb=verb)
        run.transitions.append(tr)
        if run.order and src in run.order and dst in run.order:
            si, di = run.order.index(src), run.order.index(dst)
            if di < si:
                run.loops.append(tr)
            elif di > si + 1:
                for skipped in run.order[si + 1:di]:
                    if run.phases[skipped].status in ("pending", "queued"):
                        run.phases[skipped].status = "skipped"
        dps = _ensure_phase(run, dst)
        if dps.status != "running":
            dps.status = "queued"
        return

    m = SKIP_RE.match(rest)
    if m:
        name, reason = m.groups()
        ps = _ensure_phase(run, canon_phase(name))
        ps.status = "skipped"
        ps.last_reason = reason


def _finalise(run: Run, now: float) -> None:
    if run.started_ts is None:
        run.state = "running" if run.current_session() else "idle"
        return
    if run.completed_ts is not None:
        run.state = "complete"
        # The orchestrator logs no routing line after the final phase, so a
        # running or queued last phase counts as done once the run completes.
        last = run.order[-1] if run.order else None
        for name in run.order:
            ps = run.phases[name]
            if ps.status == "running" or (name == last and ps.status == "queued"):
                ps.status = "done"
                ps.runs = max(ps.runs, 1)
                ps.finished = ps.finished or run.completed_ts
                if ps.started and not ps.durations:
                    ps.durations.append(max(0.0, run.completed_ts - ps.started))
            elif ps.status in ("pending", "queued"):
                ps.status = "skipped" if name in run.optional else "missed"
        return
    run.state = "running"
    if run.last_line_ts and now - run.last_line_ts > STALE_AFTER_S:
        run.state = "stale"


# ── Supplementary sources ────────────────────────────────


def load_pipeline_state(root: str, sprint: Optional[str]) -> dict:
    if not sprint:
        try:
            with open(os.path.join(root, "docs", "sprints", ".current-sprint"), encoding="utf-8") as fh:
                sprint = fh.read().strip()
        except Exception:
            return {}
    path = os.path.join(root, "docs", "sprints", f"sprint-{sprint}", "pipeline-state.json")
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def load_events(root: str, limit: int = 400) -> List[dict]:
    path = os.path.join(root, "logs", "pipeline-events.jsonl")
    try:
        with open(path, encoding="utf-8") as fh:
            lines = fh.readlines()[-limit:]
    except Exception:
        return []
    out = []
    for line in lines:
        try:
            rec = json.loads(line)
            if isinstance(rec, dict):
                out.append(rec)
        except Exception:
            continue
    return out


def open_event(events: List[dict]) -> Optional[dict]:
    """The latest start record with no matching stop."""
    stopped = set()
    for rec in reversed(events):
        if rec.get("event") == "stop" and rec.get("agent_id"):
            stopped.add(rec["agent_id"])
        elif rec.get("event") == "start":
            if rec.get("agent_id") in stopped:
                return None
            return rec
    return None


def load_herdr_state(root: str) -> dict:
    try:
        with open(os.path.join(root, "logs", ".pipeline", "herdr.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class Heartbeat:
    """Incremental reader of a subagent transcript (JSONL)."""

    def __init__(self):
        self.path: Optional[str] = None
        self.offset = 0
        self.buffer = b""
        self.tool_count = 0
        self.last_tool: Optional[str] = None
        self.last_ts: Optional[float] = None
        self.last_text: Optional[str] = None
        self.lines = 0

    def reset(self, path: Optional[str]) -> None:
        self.__init__()
        self.path = path

    def update(self, path: Optional[str]):
        if path != self.path:
            self.reset(path)
        if not self.path or not os.path.exists(self.path):
            return None
        try:
            size = os.path.getsize(self.path)
            if size < self.offset:
                self.reset(path)
            with open(self.path, "rb") as fh:
                fh.seek(self.offset)
                chunk = fh.read()
                self.offset = fh.tell()
        except Exception:
            return self.snapshot()
        data = self.buffer + chunk
        parts = data.split(b"\n")
        self.buffer = parts.pop()  # partial trailing line, kept for next time
        for raw in parts:
            if not raw.strip():
                continue
            try:
                rec = json.loads(raw.decode("utf-8", "replace"))
            except Exception:
                continue
            self._absorb(rec)
        return self.snapshot()

    def _absorb(self, rec: dict) -> None:
        self.lines += 1
        ts = rec.get("timestamp")
        if isinstance(ts, str):
            parsed = parse_iso(ts)
            if parsed:
                self.last_ts = parsed
        msg = rec.get("message")
        content = msg.get("content") if isinstance(msg, dict) else None
        if isinstance(content, list):
            for item in content:
                if not isinstance(item, dict):
                    continue
                if item.get("type") == "tool_use":
                    self.tool_count += 1
                    self.last_tool = str(item.get("name") or "?")
                elif item.get("type") == "text" and rec.get("type") == "assistant":
                    text = str(item.get("text") or "").strip().splitlines()
                    if text:
                        self.last_text = text[0][:200]

    def snapshot(self) -> dict:
        return {
            "path": self.path,
            "lines": self.lines,
            "tool_count": self.tool_count,
            "last_tool": self.last_tool,
            "last_ts": self.last_ts,
            "last_text": self.last_text,
        }


def parse_iso(ts: str) -> Optional[float]:
    try:
        ts = ts.strip()
        if ts.endswith("Z"):
            ts = ts[:-1]
        if "." in ts:
            ts = ts.split(".")[0]
        import calendar

        return float(calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%S")))
    except Exception:
        return None


# ── herdr bridge ─────────────────────────────────────────


class HerdrBridge:
    def __init__(self, root: str, enabled: bool):
        self.enabled = enabled and os.environ.get("HERDR_ENV") == "1" and shutil.which(
            os.environ.get("HERDR_BIN_PATH") or "herdr"
        ) is not None
        self.bin = os.environ.get("HERDR_BIN_PATH") or "herdr"
        self.root = root
        self.claude_pane = os.environ.get("PIPELINE_DASHBOARD_CLAUDE_PANE") or load_herdr_state(root).get("claude_pane_id")
        self.last_state: Optional[str] = None
        self.last_run_key = None
        self.notified = set()
        self.last_tokens: Optional[Tuple[str, str]] = None
        self.last_push = 0.0

    def _run(self, args, timeout=HERDR_TIMEOUT_S) -> bool:
        if not self.enabled:
            return False
        try:
            subprocess.run([self.bin] + args, capture_output=True, timeout=timeout, check=False)
            return True
        except Exception:
            return False

    def observe(self, run: Run) -> None:
        if not self.enabled:
            return
        key = run.started_ts
        if self.last_run_key != key:
            self.last_run_key, self.last_state = key, run.state
        if run.state == "complete" and self.last_state in ("running", "stale") and key not in self.notified:
            self.notified.add(key)
            title = f"Pipeline complete (sprint {run.sprint})" if run.sprint else "Pipeline complete"
            unresolved = run.unresolved_count if run.unresolved_count is not None else len(run.unresolved)
            body = f"{run.kind or 'run'} · {unresolved} unresolved · {fmt_dur((run.completed_ts or run.now) - (run.started_ts or run.now))}"
            self._run(["notification", "show", title, "--body", body, "--sound", "done"], timeout=5)
        self.last_state = run.state
        self.push_metadata(run)

    def push_metadata(self, run: Run) -> None:
        if not self.enabled or not self.claude_pane:
            return
        phase = run.current_phase()
        if run.state == "complete":
            phase_txt = f"done {len(run.order)}/{len(run.order)}"
        elif phase:
            ps = run.phases[phase]
            idx = run.order.index(phase) + 1 if phase in run.order else 0
            phase_txt = f"{phase} {idx}/{len(run.order)}" + (f" r{ps.runs + 1}" if ps.runs else "")
        else:
            phase_txt = "idle"
        sess = run.current_session()
        agent_txt = short_agent(sess.agent, run.prefix) if sess else "-"
        if sess and sess.progress:
            n, total, _ = sess.progress
            agent_txt += f" {round(100 * min(n, total) / max(total, 1))}%"
        elif sess:
            est = estimate_progress(run, sess)
            if est:
                agent_txt += f" ~{est[0]}%"
        tokens = (phase_txt, agent_txt)
        now = time.time()
        if tokens == self.last_tokens and now - self.last_push < 10:
            return
        self.last_tokens, self.last_push = tokens, now
        self._run([
            "pane", "report-metadata", self.claude_pane, "--source", PLUGIN_ID,
            "--token", f"phase={phase_txt}", "--token", f"agent={agent_txt}", "--ttl-ms", "15000",
        ])

    def clear(self) -> None:
        if not self.enabled or not self.claude_pane:
            return
        self._run(["pane", "report-metadata", self.claude_pane, "--source", PLUGIN_ID,
                   "--clear-token", "phase", "--clear-token", "agent"])

    def focus_return_pane(self) -> None:
        state_dir = os.environ.get("HERDR_PLUGIN_STATE_DIR")
        if not state_dir:
            return
        path = os.path.join(state_dir, "return-pane")
        try:
            with open(path, encoding="utf-8") as fh:
                pane = fh.read().strip()
            os.remove(path)
        except Exception:
            return
        if pane:
            self._run(["pane", "focus", pane])


# ── Rendering ────────────────────────────────────────────

COLORS = {
    "green": "\x1b[32m", "yellow": "\x1b[33m", "red": "\x1b[31m", "cyan": "\x1b[36m",
    "magenta": "\x1b[35m", "dim": "\x1b[2m", "bold": "\x1b[1m", "reset": "\x1b[0m",
}

STATUS_GLYPH = {
    "pending": "·", "queued": "»", "running": "▶", "done": "✓",
    "skipped": "–", "forced": "✗", "missed": "✗",
}
STATUS_COLOR = {
    "pending": "dim", "queued": "cyan", "running": "yellow", "done": "green",
    "skipped": "dim", "forced": "red", "missed": "red",
}
STATE_GLYPH = {"idle": "○", "running": "●", "complete": "✓", "stale": "!"}
STATE_COLOR = {"idle": "dim", "running": "yellow", "complete": "green", "stale": "red"}

Seg = Tuple[str, Optional[str]]


def fmt_dur(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h{m:02d}m"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"


def fmt_clock(ts: Optional[float]) -> str:
    return time.strftime("%H:%M:%S", time.localtime(ts)) if ts else "--:--:--"


def short_agent(name: str, prefix: str) -> str:
    if name.startswith(prefix + "-"):
        return name[len(prefix) + 1:]
    return name


def fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"


def render_segments(segs: List[Seg], width: int, color: bool) -> str:
    out, used = [], 0
    for text, col in segs:
        if used >= width:
            break
        piece = fit(text, width - used) if used + len(text) > width else text
        used += len(piece)
        if color and col:
            out.append(COLORS[col] + piece + COLORS["reset"])
        else:
            out.append(piece)
    return "".join(out)


def wrapped(prefix: List[Seg], text: str, color: Optional[str], width: int) -> List[List[Seg]]:
    """Segment lines for `prefix + text`, wrapping the text under a hanging indent.

    Long reasons and unresolved items carry the information the dashboard
    exists for, so they are wrapped rather than cut off with an ellipsis.
    """
    indent = sum(len(t) for t, _ in prefix)
    avail = max(8, width - indent)
    pieces = textwrap.wrap(text, width=avail, break_long_words=True, break_on_hyphens=False) or [""]
    out = [prefix + [(pieces[0], color)]]
    for piece in pieces[1:]:
        out.append([(" " * indent, None), (piece, color)])
    return out


def bar(n: int, total: int, width: int) -> str:
    width = max(4, width)
    total = max(total, 1)
    filled = int(round(width * min(n, total) / total))
    return "[" + "█" * filled + "░" * (width - filled) + "]"


def build_sections(run: Run, heartbeat: Optional[dict], width: int, tail_n: int):
    """Return ([(name, [segments-per-line])], {name: compact alternative})."""
    now = run.now
    sections = []
    alternates: Dict[str, List[List[Seg]]] = {}

    # Header
    glyph, gcol = STATE_GLYPH[run.state], STATE_COLOR[run.state]
    if run.started_ts:
        end = run.completed_ts or now
        elapsed = fmt_dur(end - run.started_ts)
    else:
        elapsed = ""
    head = [(f"{glyph} {run.state}", gcol)]
    if elapsed:
        head.append((f" {elapsed}", "bold"))
    if run.sprint:
        head.append((f"  sprint {run.sprint}", None))
    if run.kind:
        head.append((f"  {run.kind}", "cyan"))
    lines = [head]
    if run.started_ts:
        sub = f"started {fmt_clock(run.started_ts)}"
        if run.description:
            sub += " · "
        lines.extend(wrapped([(sub, "dim")], run.description or "", "dim", width))
    elif run.state == "idle":
        lines.append([("no pipeline run in this log", "dim")])
    if run.state == "stale" and run.last_line_ts:
        lines.append([(f"no log activity for {fmt_dur(now - run.last_line_ts)}", "red")])
    sections.append(("header", lines))

    # Phase list: one phase per row, what each finished phase did underneath.
    if run.order:
        full, compact = [], []
        last = run.transitions[-1] if run.transitions else None
        for name in run.order:
            ps = run.phases[name]
            col = STATUS_COLOR[ps.status]
            segs = [(f"{STATUS_GLYPH[ps.status]} ", col), (f"{name:<8}", col if ps.status != "done" else None)]
            extra = ""
            if ps.status == "running":
                extra = f" r{ps.runs + 1}" if ps.runs else ""
                if ps.started:
                    extra += f"  {fmt_dur(now - ps.started)}"
            elif ps.runs > 1:
                extra = f" r{ps.runs}"
                if ps.durations:
                    extra += f"  {fmt_dur(sum(ps.durations))}"
            elif ps.durations:
                extra = f"     {fmt_dur(sum(ps.durations))}"
            if extra:
                segs.append((extra, "dim"))
            full.append(segs)
            compact.append(segs)
            if ps.last_reason:
                reason_lines = wrapped([("    ↳ ", "dim")], ps.last_reason, "dim", width)
                full.extend(reason_lines)
                if last and (name == last.src) and ps.last_reason == last.reason:
                    compact.extend(reason_lines)
        sections.append(("phases", full))
        alternates["phases"] = compact

    # Current agent
    sess = run.current_session()
    lines = []
    if sess:
        name = short_agent(sess.agent, run.prefix)
        lines.append([(name, "bold"), (f"  {fmt_dur(now - sess.start_ts)}", "yellow")])
        bw = min(20, max(4, width - 16))
        if sess.progress:
            n, total, text = sess.progress
            pct = round(100 * min(n, total) / max(total, 1))
            lines.extend(wrapped([(bar(n, total, bw), "cyan"), (f" {pct:>3}% ", "bold"), (f"{n}/{total} ", "bold")], text, None, width))
        else:
            est = estimate_progress(run, sess)
            if est:
                pct, basis = est
                lines.extend(wrapped([(bar(pct, 100, bw), "dim"), (f" ~{pct:>2}% ", "bold")], basis, "dim", width))
            else:
                lines.append([(bar(0, 1, bw), "dim"), ("   ?% no PROGRESS reported yet", "dim")])
        if heartbeat and heartbeat.get("path"):
            hb = f"tools {heartbeat['tool_count']}"
            if heartbeat.get("last_tool"):
                hb += f" · last {heartbeat['last_tool']}"
            if heartbeat.get("last_ts"):
                hb += f" {fmt_dur(now - heartbeat['last_ts'])} ago"
            lines.append([(hb, "dim")])
        for ts, action, text in sess.events[-3:]:
            lines.extend(wrapped([("▸ ", "dim"), (f"{action} ", "magenta")], text, None, width))
    elif run.state in ("running", "stale"):
        lines.append([("waiting for next agent…", "dim")])
    if lines:
        sections.append(("agent", lines))

    # Loops
    if run.loops:
        counts: Dict[Tuple[str, str], List[Transition]] = {}
        for tr in run.loops:
            counts.setdefault((tr.src, tr.dst), []).append(tr)
        lines = [[("loops", "bold")]]
        for (src, dst), trs in counts.items():
            reason = trs[-1].reason or ""
            lines.extend(wrapped([(f"{src} → {dst} ×{len(trs)}  ", "red")], reason, "dim", width))
        sections.append(("loops", lines))

    # Unresolved
    unresolved = list(run.unresolved)
    if unresolved:
        lines = [[(f"unresolved ({len(unresolved)})", "red")]]
        for item in unresolved:
            lines.extend(wrapped([("• ", "red")], str(item), None, width))
        sections.append(("unresolved", lines))

    # Tail
    if run.tail:
        lines = [[("log", "bold")]]
        for raw in run.tail[-tail_n:]:
            parsed = parse_line(raw)
            if parsed:
                ts, action, agent, rest = parsed
                who = short_agent(NAMESPACE_RE.sub("", agent), run.prefix) or "-"
                lines.append([(ts[11:], "dim"), (f" {action:<8} ", "magenta"), (f"{who} ", "cyan"), (rest, None)])
            else:
                lines.append([(raw, "dim")])
        sections.append(("tail", lines))

    if width >= 30:
        sections.append(("footer", [[("q quit · r refresh", "dim")]]))
    return sections, alternates


def render(run: Run, width: int, height: int, color: bool = True, heartbeat: Optional[dict] = None, tail_n: int = TAIL_DEFAULT) -> List[str]:
    width, height = max(10, width), max(3, height)
    sections, alternates = build_sections(run, heartbeat, width, tail_n)
    blocks = {name: lines for name, lines in sections}
    order = [name for name, _ in sections]

    def total() -> int:
        return sum(len(blocks[n]) for n in order) + max(0, len(order) - 1)

    # Trim until it fits, least valuable first: the log tail, the footer,
    # agent extras, loops. Unresolved items go last and are cut from the end
    # rather than dropped wholesale, so what remains is still complete lines.
    def drop(name: str) -> None:
        if name in blocks:
            del blocks[name]
            order.remove(name)

    while total() > height and len(blocks.get("tail", [])) > 2:
        blocks["tail"].pop(1)
    if total() > height and "phases" in alternates and "phases" in blocks:
        blocks["phases"] = list(alternates["phases"])
    if total() > height:
        drop("tail")
    if total() > height:
        drop("footer")
    while total() > height and len(blocks.get("agent", [])) > 2:
        blocks["agent"].pop()
    if total() > height:
        drop("loops")
    while total() > height and len(blocks.get("unresolved", [])) > 1:
        blocks["unresolved"].pop()
    if total() > height:
        drop("unresolved")
    while total() > height and len(blocks.get("agent", [])) > 0:
        blocks["agent"].pop()
    if total() > height:
        drop("agent")

    out: List[str] = []
    for i, name in enumerate(order):
        if i:
            out.append("")
        for segs in blocks[name]:
            out.append(render_segments(segs, width, color))
    out = out[:height]
    while len(out) < height:
        out.append("")
    return out


# ── Model assembly ───────────────────────────────────────


def find_root(start: Optional[str]) -> str:
    env = os.environ.get("PIPELINE_DASHBOARD_PROJECT_DIR")
    if start:
        return os.path.abspath(start)
    if env:
        return os.path.abspath(env)
    cur = os.path.abspath(os.getcwd())
    while True:
        if os.path.exists(os.path.join(cur, "logs", "agent-workflow.log")) or os.path.isdir(os.path.join(cur, ".claude", "agents")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return os.path.abspath(os.getcwd())
        cur = parent


class Model:
    def __init__(self, root: str, tail_n: int = TAIL_DEFAULT):
        self.root = root
        self.log_path = os.path.join(root, "logs", "agent-workflow.log")
        self.tail_n = tail_n
        self.prefix: Optional[str] = None
        self.sig = None
        self.run = Run(now=time.time())
        self.heartbeat = Heartbeat()
        self.hb_snapshot: Optional[dict] = None

    def refresh(self, force: bool = False) -> Run:
        now = time.time()
        try:
            st = os.stat(self.log_path)
            sig = (st.st_mtime_ns, st.st_size)
        except OSError:
            sig = None
        if force or sig != self.sig or self.run is None:
            self.sig = sig
            lines: List[str] = []
            if sig is not None:
                try:
                    with open(self.log_path, encoding="utf-8", errors="replace") as fh:
                        lines = fh.readlines()
                except OSError:
                    lines = []
            if self.prefix is None or force:
                self.prefix = resolve_prefix(self.root, lines)
            self.run = parse_log(lines, self.prefix, now=now, tail_n=self.tail_n)
            self._merge_state()
        else:
            self.run.now = now
            _finalise(self.run, now)
        self._merge_events()
        return self.run

    def _merge_state(self) -> None:
        state = load_pipeline_state(self.root, self.run.sprint)
        if state:
            unresolved = state.get("unresolved")
            if isinstance(unresolved, list):
                self.run.unresolved = [str(u) for u in unresolved]
            verdicts = state.get("verdicts")
            if isinstance(verdicts, dict):
                self.run.verdicts = {str(k): (str(v) if v is not None else None) for k, v in verdicts.items()}
            if not self.run.sprint and state.get("sprint"):
                self.run.sprint = str(state["sprint"])

    def _merge_events(self) -> None:
        rec = open_event(load_events(self.root))
        sess = self.run.current_session()
        transcript = None
        if rec and sess and rec.get("agent") == sess.agent:
            transcript = rec.get("transcript")
            sess.transcript = transcript
            sess.agent_id = rec.get("agent_id")
        self.hb_snapshot = self.heartbeat.update(transcript) if transcript else None


def model_to_json(run: Run, heartbeat: Optional[dict]) -> str:
    data = dataclasses.asdict(run)
    data["current_phase"] = run.current_phase()
    sess = run.current_session()
    data["current_agent"] = dataclasses.asdict(sess) if sess else None
    data["heartbeat"] = heartbeat
    return json.dumps(data, indent=2, default=str)


# ── Terminal loop ────────────────────────────────────────


def run_tui(model: Model, bridge: HerdrBridge, interval: float, color: bool, tail_n: int) -> int:
    import termios
    import tty

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    resized = {"flag": False}

    def on_winch(*_):
        resized["flag"] = True

    try:
        signal.signal(signal.SIGWINCH, on_winch)
    except Exception:
        pass

    out = sys.stdout
    out.write("\x1b[?1049h\x1b[?25l\x1b[H\x1b[2J")
    out.flush()
    try:
        tty.setcbreak(fd)
        force = True
        while True:
            run = model.refresh(force=force)
            force = False
            bridge.observe(run)
            size = shutil.get_terminal_size((80, 24))
            frame = render(run, size.columns, size.lines, color=color, heartbeat=model.hb_snapshot, tail_n=tail_n)
            out.write("\x1b[H" + "\n".join(line + "\x1b[K" for line in frame) + "\x1b[J")
            out.flush()
            try:
                ready, _, _ = select.select([fd], [], [], interval)
            except InterruptedError:
                ready = []
            if ready:
                ch = os.read(fd, 1)
                if ch in (b"q", b"Q", b"\x03"):
                    break
                if ch in (b"r", b"R"):
                    force = True
    except KeyboardInterrupt:
        pass
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)
        out.write("\x1b[?25h\x1b[?1049l")
        out.flush()
        bridge.clear()
        bridge.focus_return_pane()
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Live maxPlanck pipeline dashboard")
    ap.add_argument("--cwd", help="project root (default: $PIPELINE_DASHBOARD_PROJECT_DIR or walk up from cwd)")
    ap.add_argument("--interval", type=float, default=1.0)
    ap.add_argument("--once", action="store_true", help="print one frame and exit")
    ap.add_argument("--json", action="store_true", help="print the parsed model as JSON and exit")
    ap.add_argument("--width", type=int)
    ap.add_argument("--height", type=int)
    ap.add_argument("--no-herdr", action="store_true")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--tail", type=int, default=TAIL_DEFAULT)
    args = ap.parse_args(argv)

    root = find_root(args.cwd)
    model = Model(root, tail_n=args.tail)
    color = not args.no_color and not os.environ.get("NO_COLOR")

    if args.json:
        run = model.refresh(force=True)
        print(model_to_json(run, model.hb_snapshot))
        return 0

    if args.once or not sys.stdout.isatty() or not sys.stdin.isatty():
        run = model.refresh(force=True)
        size = shutil.get_terminal_size((80, 24))
        width = args.width or size.columns
        height = args.height or size.lines
        color = color and sys.stdout.isatty()
        frame = render(run, width, height, color=color, heartbeat=model.hb_snapshot, tail_n=args.tail)
        while frame and not frame[-1].strip():
            frame.pop()
        print("\n".join(frame))
        return 0

    bridge = HerdrBridge(root, enabled=not args.no_herdr)
    return run_tui(model, bridge, args.interval, color, args.tail)


if __name__ == "__main__":
    sys.exit(main())
