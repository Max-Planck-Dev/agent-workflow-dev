#!/usr/bin/env python3
"""Lifecycle hook for the maxPlanck agent workflow.

Called by .claude/hooks/log-agent-lifecycle.sh on SubagentStart / SubagentStop
with the event name (START | STOP) as argv[1] and the hook payload as JSON on
stdin. It never fails the hook: every step is wrapped, and the exit code is
always 0.

It writes two layers:

1. The human log line the rest of the workflow already relies on:
       [YYYY-MM-DD HH:MM:SS] START | Agent: <name>
   On STOP the payload usually lacks the agent name, so it is resolved from a
   stamp written at START, or from the subagent's own transcript metadata.

2. A machine file, logs/pipeline-events.jsonl, written only for workflow
   agents (maxPlanck-*). It carries what the human log cannot: agent_id,
   session_id, the subagent transcript path (for the dashboard's activity
   heartbeat) and the herdr pane id. Agents never read this file.

When Claude runs inside a herdr pane (HERDR_ENV=1) the first workflow agent of
a run also opens the pipeline dashboard as a split pane next to Claude. That
happens in a detached child process (`--auto-open`) so the hook returns
immediately.
"""

import glob
import json
import os
import subprocess
import sys
import time

# Rewritten by setup.sh --prefix; the herdr identifiers below are deliberately
# lower-case and prefix-free so a rebrand never touches them.
AGENT_PREFIX = "maxPlanck"
PLUGIN_ID = "maxplanck.pipeline"
PANE_ENTRYPOINT = "dashboard"
PANE_LABEL = "pipeline dashboard"

STAMP_MAX_AGE_S = 24 * 3600
LOCK_STALE_S = 30
HERDR_TIMEOUT_S = 2


# ── Small helpers ────────────────────────────────────────


def now_human() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S")


def project_root() -> str:
    root = os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    return os.path.abspath(root)


def logs_dir(root: str) -> str:
    return os.path.join(root, "logs")


def pipeline_dir(root: str) -> str:
    return os.path.join(logs_dir(root), ".pipeline")


def read_payload() -> dict:
    try:
        data = json.load(sys.stdin)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def strip_namespace(name: str) -> str:
    """`maxplanck:maxPlanck-developer` → `maxPlanck-developer`."""
    if ":" in name:
        head, tail = name.split(":", 1)
        if head and all(c.isalnum() or c in "_-" for c in head) and tail:
            return tail
    return name


def agent_name(payload: dict) -> str:
    raw = payload.get("agent_type") or payload.get("subagent_type") or ""
    return strip_namespace(str(raw).strip())


def is_workflow_agent(name: str, prefix: str = AGENT_PREFIX) -> bool:
    return bool(name) and name.startswith(prefix + "-")


def subagent_transcript(payload: dict):
    """Best-effort path of the subagent's own transcript.

    Claude stores it at <session dir>/subagents/agent-<agent_id>.jsonl, where
    <session dir> sits next to the main transcript and is named after the
    session id. The file may not exist yet at START; return the composed path
    anyway so the dashboard can pick it up once it appears.
    """
    tp = payload.get("transcript_path")
    if not isinstance(tp, str) or not tp:
        return None
    if os.path.basename(tp).startswith("agent-"):
        return tp
    agent_id = payload.get("agent_id")
    if not isinstance(agent_id, str) or not agent_id:
        return None
    base = os.path.dirname(tp)
    session_id = payload.get("session_id")
    if isinstance(session_id, str) and session_id:
        composed = os.path.join(base, session_id, "subagents", f"agent-{agent_id}.jsonl")
        if os.path.exists(composed):
            return composed
    else:
        composed = None
    hits = glob.glob(os.path.join(base, "*", "subagents", f"agent-{agent_id}.jsonl"))
    if hits:
        return hits[0]
    return composed


def meta_agent_type(payload: dict):
    """Read agentType from agent-<id>.meta.json next to the subagent transcript."""
    transcript = subagent_transcript(payload)
    if not transcript:
        return None
    meta = transcript[: -len(".jsonl")] + ".meta.json" if transcript.endswith(".jsonl") else None
    if not meta or not os.path.exists(meta):
        return None
    try:
        with open(meta, encoding="utf-8") as fh:
            data = json.load(fh)
        value = data.get("agentType")
        return strip_namespace(str(value)) if value else None
    except Exception:
        return None


# ── Stamps (START → STOP name and duration) ──────────────


def stamps_dir(root: str) -> str:
    return os.path.join(pipeline_dir(root), "agents")


def stamp_path(root: str, agent_id: str) -> str:
    safe = "".join(c for c in agent_id if c.isalnum() or c in "_-") or "unknown"
    return os.path.join(stamps_dir(root), safe)


def stamp_start(root: str, agent_id: str, name: str) -> None:
    os.makedirs(stamps_dir(root), exist_ok=True)
    with open(stamp_path(root, agent_id), "w", encoding="utf-8") as fh:
        fh.write(f"{name}\n{int(time.time())}\n")


def read_stamp(root: str, agent_id: str):
    try:
        with open(stamp_path(root, agent_id), encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        name = lines[0].strip() if lines else ""
        started = int(lines[1]) if len(lines) > 1 and lines[1].strip().isdigit() else None
        return (name or None), started
    except Exception:
        return None, None


def clear_stamp(root: str, agent_id: str) -> None:
    try:
        os.remove(stamp_path(root, agent_id))
    except Exception:
        pass


def prune_stamps(root: str) -> None:
    d = stamps_dir(root)
    try:
        cutoff = time.time() - STAMP_MAX_AGE_S
        for entry in os.listdir(d):
            p = os.path.join(d, entry)
            try:
                if os.path.getmtime(p) < cutoff:
                    os.remove(p)
            except Exception:
                pass
    except Exception:
        pass


def resolve_stop_name(payload: dict, root: str) -> str:
    name = agent_name(payload)
    if name:
        return name
    agent_id = payload.get("agent_id")
    if isinstance(agent_id, str) and agent_id:
        stamped, _ = read_stamp(root, agent_id)
        if stamped:
            return stamped
    return meta_agent_type(payload) or "unknown"


# ── Writers ──────────────────────────────────────────────


def write_human_line(root: str, event: str, name: str) -> None:
    os.makedirs(logs_dir(root), exist_ok=True)
    with open(os.path.join(logs_dir(root), "agent-workflow.log"), "a", encoding="utf-8") as fh:
        fh.write(f"[{now_human()}] {event} | Agent: {name}\n")


def write_event(root: str, record: dict) -> None:
    os.makedirs(logs_dir(root), exist_ok=True)
    with open(os.path.join(logs_dir(root), "pipeline-events.jsonl"), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def herdr_state_path(root: str) -> str:
    return os.path.join(pipeline_dir(root), "herdr.json")


def load_herdr_state(root: str) -> dict:
    try:
        with open(herdr_state_path(root), encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_herdr_state(root: str, updates: dict) -> dict:
    state = load_herdr_state(root)
    state.update(updates)
    state["updated"] = now_iso()
    os.makedirs(pipeline_dir(root), exist_ok=True)
    tmp = herdr_state_path(root) + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=2)
        fh.write("\n")
    os.replace(tmp, herdr_state_path(root))
    return state


def herdr_env() -> dict:
    return {
        "env": os.environ.get("HERDR_ENV") == "1",
        "pane_id": os.environ.get("HERDR_PANE_ID") or None,
        "workspace_id": os.environ.get("HERDR_WORKSPACE_ID") or None,
    }


# ── herdr integration ────────────────────────────────────


def herdr_bin():
    candidate = os.environ.get("HERDR_BIN_PATH") or "herdr"
    if os.path.sep in candidate:
        return candidate if os.access(candidate, os.X_OK) else None
    for d in os.environ.get("PATH", "").split(os.pathsep):
        p = os.path.join(d, candidate)
        if os.access(p, os.X_OK):
            return p
    return None


def herdr(args, timeout=HERDR_TIMEOUT_S):
    """Run a herdr CLI command; return parsed JSON, or None on any failure."""
    bin_path = herdr_bin()
    if not bin_path:
        return None
    try:
        out = subprocess.run(
            [bin_path] + list(args),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        if out.returncode != 0:
            return None
        text = out.stdout.strip()
        if not text:
            return {}
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {}
    except Exception:
        return None


def list_panes():
    data = herdr(["pane", "list"])
    try:
        panes = data["result"]["panes"]
        return panes if isinstance(panes, list) else []
    except Exception:
        return []


def pane_exists(pane_id: str) -> bool:
    if not pane_id:
        return False
    data = herdr(["pane", "get", pane_id])
    try:
        return bool(data["result"]["pane"])
    except Exception:
        return False


def find_dashboard_pane(state: dict):
    pane_id = state.get("dashboard_pane_id")
    if pane_id and pane_exists(pane_id):
        return pane_id
    for pane in list_panes():
        if pane.get("label") == PANE_LABEL or pane.get("terminal_title_stripped") == PANE_LABEL:
            return pane.get("pane_id")
    return None


def find_claude_pane(session_id, fallback):
    if session_id:
        for pane in list_panes():
            session = pane.get("agent_session") or {}
            if isinstance(session, dict) and session.get("value") == session_id:
                return pane.get("pane_id")
    return fallback


class AutoOpenLock:
    def __init__(self, root: str):
        self.path = os.path.join(pipeline_dir(root), "auto-open.lock")
        self.held = False

    def __enter__(self):
        os.makedirs(os.path.dirname(self.path), exist_ok=True)
        try:
            if time.time() - os.path.getmtime(self.path) > LOCK_STALE_S:
                os.remove(self.path)
        except Exception:
            pass
        try:
            fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, str(os.getpid()).encode())
            os.close(fd)
            self.held = True
        except FileExistsError:
            self.held = False
        return self

    def __exit__(self, *exc):
        if self.held:
            try:
                os.remove(self.path)
            except Exception:
                pass
        return False


def auto_open(root: str) -> None:
    if os.environ.get("HERDR_ENV") != "1" or not herdr_bin():
        return
    with AutoOpenLock(root) as lock:
        if not lock.held:
            return
        state = load_herdr_state(root)
        existing = find_dashboard_pane(state)
        if existing:
            if existing != state.get("dashboard_pane_id"):
                save_herdr_state(root, {"dashboard_pane_id": existing})
            return
        claude_pane = find_claude_pane(
            state.get("session_id"),
            state.get("claude_pane_id") or os.environ.get("HERDR_PANE_ID"),
        )
        args = [
            "plugin", "pane", "open",
            "--plugin", PLUGIN_ID,
            "--entrypoint", PANE_ENTRYPOINT,
            "--placement", "split",
            "--direction", "right",
            "--cwd", root,
            "--no-focus",
            "--env", f"PIPELINE_DASHBOARD_PROJECT_DIR={root}",
            "--env", f"PIPELINE_DASHBOARD_AGENT_PREFIX={AGENT_PREFIX}",
        ]
        if claude_pane:
            args += ["--target-pane", claude_pane, "--env", f"PIPELINE_DASHBOARD_CLAUDE_PANE={claude_pane}"]
        result = herdr(args, timeout=10)
        if result is None:
            return
        pane_id = None
        try:
            pane_id = result["result"]["plugin_pane"]["pane"]["pane_id"]
        except Exception:
            pane_id = None
        if not pane_id:
            for pane in list_panes():
                if pane.get("label") == PANE_LABEL:
                    pane_id = pane.get("pane_id")
                    break
        if pane_id:
            herdr(["pane", "rename", pane_id, PANE_LABEL])
            save_herdr_state(root, {"dashboard_pane_id": pane_id, "claude_pane_id": claude_pane})


def spawn_auto_open(root: str) -> None:
    try:
        subprocess.Popen(
            [sys.executable, os.path.abspath(__file__), "--auto-open", root],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
            close_fds=True,
        )
    except Exception:
        pass


# ── Entrypoints ──────────────────────────────────────────


def handle_start(root: str, payload: dict) -> None:
    name = agent_name(payload) or "unknown"
    agent_id = payload.get("agent_id") if isinstance(payload.get("agent_id"), str) else None
    workflow = is_workflow_agent(name)

    try:
        write_human_line(root, "START", name)
    except Exception:
        pass
    if agent_id:
        try:
            stamp_start(root, agent_id, name)
            prune_stamps(root)
        except Exception:
            pass
    if not workflow:
        return
    try:
        write_event(root, {
            "ts": now_iso(),
            "event": "start",
            "agent": name,
            "agent_id": agent_id,
            "session_id": payload.get("session_id"),
            "transcript": subagent_transcript(payload),
            "project_dir": root,
            "herdr": herdr_env(),
        })
    except Exception:
        pass
    henv = herdr_env()
    if henv["env"]:
        try:
            save_herdr_state(root, {
                "claude_pane_id": henv["pane_id"],
                "workspace_id": henv["workspace_id"],
                "session_id": payload.get("session_id"),
            })
        except Exception:
            pass
        spawn_auto_open(root)


def handle_stop(root: str, payload: dict) -> None:
    name = resolve_stop_name(payload, root)
    agent_id = payload.get("agent_id") if isinstance(payload.get("agent_id"), str) else None
    started = None
    if agent_id:
        _, started = read_stamp(root, agent_id)
    try:
        write_human_line(root, "STOP", name)
    except Exception:
        pass
    if is_workflow_agent(name):
        try:
            write_event(root, {
                "ts": now_iso(),
                "event": "stop",
                "agent": name,
                "agent_id": agent_id,
                "session_id": payload.get("session_id"),
                "transcript": subagent_transcript(payload),
                "project_dir": root,
                "duration_s": (int(time.time()) - started) if started else None,
                "herdr": herdr_env(),
            })
        except Exception:
            pass
    if agent_id:
        clear_stamp(root, agent_id)


def main(argv) -> int:
    if len(argv) >= 3 and argv[1] == "--auto-open":
        try:
            auto_open(os.path.abspath(argv[2]))
        except Exception:
            pass
        return 0
    event = (argv[1] if len(argv) > 1 else "EVENT").upper()
    root = project_root()
    payload = read_payload()
    try:
        if event == "START":
            handle_start(root, payload)
        elif event == "STOP":
            handle_stop(root, payload)
        else:
            write_human_line(root, event, agent_name(payload) or "unknown")
    except Exception:
        try:
            write_human_line(root, event, "unknown")
        except Exception:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
