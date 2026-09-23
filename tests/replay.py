#!/usr/bin/env python3
"""Replay a log fixture into a scratch project so the dashboard can be watched live.

    python3 tests/replay.py tests/fixtures/agent-workflow.modern.log /tmp/proj --delay 0.4 --heartbeat

Then, in another pane:

    python3 bin/pipeline_dashboard.py --cwd /tmp/proj

Timestamps are rewritten so the last line lands at "now", keeping the
fixture's relative spacing compressed to one --delay per line. With
--heartbeat, every workflow START also gets a pipeline-events.jsonl record
pointing at a fake subagent transcript that grows while the agent "runs", so
the tool-call heartbeat animates too.
"""

import argparse
import json
import os
import random
import re
import sys
import time

LINE_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] (\w+)\s*\| Agent: ([^|]*?)\s*(?:\| (.*))?$")
TOOLS = ["Read", "Grep", "Glob", "Edit", "Bash", "Write"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("fixture")
    ap.add_argument("target")
    ap.add_argument("--delay", type=float, default=0.4)
    ap.add_argument("--heartbeat", action="store_true")
    ap.add_argument("--prefix", default="maxPlanck")
    ap.add_argument("--keep", action="store_true", help="append to an existing log instead of starting fresh")
    args = ap.parse_args()

    logs = os.path.join(args.target, "logs")
    fake_dir = os.path.join(logs, ".pipeline", "fake-transcripts")
    os.makedirs(fake_dir, exist_ok=True)
    log_path = os.path.join(logs, "agent-workflow.log")
    events_path = os.path.join(logs, "pipeline-events.jsonl")
    if not args.keep:
        for p in (log_path, events_path):
            if os.path.exists(p):
                os.remove(p)

    with open(args.fixture, encoding="utf-8") as fh:
        lines = [l.rstrip("\n") for l in fh if l.strip()]

    start = time.time()
    n = len(lines)
    open_transcript = None
    counter = 0
    for i, raw in enumerate(lines):
        m = LINE_RE.match(raw)
        when = start + i * args.delay
        stamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(when))
        line = f"[{stamp}] {raw[22:]}" if m else raw
        with open(log_path, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")

        if args.heartbeat and m:
            action, agent = m.group(2).upper(), m.group(3).strip().split(":")[-1]
            if action == "START" and agent.startswith(args.prefix + "-"):
                counter += 1
                open_transcript = os.path.join(fake_dir, f"agent-fake{counter}.jsonl")
                with open(events_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": stamp, "event": "start", "agent": agent, "agent_id": f"fake{counter}", "transcript": open_transcript}) + "\n")
            elif action == "STOP" and open_transcript:
                with open(events_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps({"ts": stamp, "event": "stop", "agent": agent, "agent_id": f"fake{counter}"}) + "\n")
                open_transcript = None
        if open_transcript:
            with open(open_transcript, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({
                    "type": "assistant",
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.000Z", time.gmtime()),
                    "message": {"content": [{"type": "tool_use", "name": random.choice(TOOLS)}]},
                }) + "\n")
        sys.stdout.write(f"\r{i + 1}/{n} {line[:70]:<70}")
        sys.stdout.flush()
        time.sleep(args.delay)
    print("\nreplay done; the last agent stays open (running) if the fixture ends mid-phase")
    return 0


if __name__ == "__main__":
    sys.exit(main())
