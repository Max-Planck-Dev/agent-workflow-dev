#!/usr/bin/env bash
# Pipeline dashboard controller for herdr: open | close | toggle
#
# Invoked by the plugin actions in herdr-plugin.toml (and usable by hand from
# any pane inside herdr). Auto-open on pipeline start is NOT done here: the
# Claude lifecycle hook (.claude/hooks/pipeline-events.py) does that, because
# script-installed projects have the hook but not this repo.
#
# Requires python3 (already required by the workflow hooks).
set -euo pipefail

cmd="${1:-toggle}"
H="${HERDR_BIN_PATH:-herdr}"
PLUGIN_ID="${HERDR_PLUGIN_ID:-maxplanck.pipeline}"
ENTRYPOINT="dashboard"
PANE_LABEL="pipeline dashboard"
ws="${HERDR_WORKSPACE_ID:-}"

if ! command -v python3 >/dev/null 2>&1; then
  echo "pipeline dashboard: python3 is required but was not found on PATH." >&2
  exit 1
fi

# json_get <python expression over `d`> — read JSON from stdin, print the
# expression's value (or nothing on any error).
json_get() {
  python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
    v = eval(sys.argv[1])
    if isinstance(v, list):
        print("\n".join(str(x) for x in v))
    elif v is not None:
        print(v)
except Exception:
    pass
' "$1" 2>/dev/null
}

config_file="${HERDR_PLUGIN_CONFIG_DIR:-}/config.toml"

# cfg <key> <default> — minimal TOML scalar lookup, good enough for flat keys.
cfg() {
  local key="$1" def="$2" v=""
  if [ -f "$config_file" ]; then
    v=$(sed -n -E "s/^[[:space:]]*${key}[[:space:]]*=[[:space:]]*\"?([^\"#]*)\"?.*/\1/p" "$config_file" | head -1 | tr -d '[:space:]')
  fi
  if [ -n "$v" ]; then echo "$v"; else echo "$def"; fi
}

placement=$(cfg placement split)
direction=$(cfg direction right)
case "$placement" in
  split|overlay|zoomed|tab) ;;
  *) placement=split ;;
esac

list_panes() {
  # shellcheck disable=SC2086
  "$H" pane list ${ws:+--workspace "$ws"} 2>/dev/null \
    | json_get '[p["pane_id"] for p in d["result"]["panes"] if p.get("label") == "'"$PANE_LABEL"'"]'
}

# Focus goes back to the pane that opened the dashboard when it closes.
return_file="${HERDR_PLUGIN_STATE_DIR:-}/return-pane"

save_return_pane() {
  [ -n "${HERDR_PANE_ID:-}" ] && [ -n "${HERDR_PLUGIN_STATE_DIR:-}" ] || return 0
  mkdir -p "$HERDR_PLUGIN_STATE_DIR" 2>/dev/null || return 0
  printf '%s' "$HERDR_PANE_ID" > "$return_file" 2>/dev/null || true
}

focus_return_pane() {
  [ -f "$return_file" ] || return 0
  local rp
  rp=$(cat "$return_file" 2>/dev/null) || true
  rm -f "$return_file"
  [ -n "$rp" ] && "$H" pane focus "$rp" >/dev/null 2>&1 || true
}

# Walk up from a directory to the project root: the first ancestor holding
# logs/agent-workflow.log or .claude/agents; else the git toplevel; else itself.
project_root_of() {
  local dir="$1" cur
  cur="$dir"
  while [ -n "$cur" ] && [ "$cur" != "/" ]; do
    if [ -f "$cur/logs/agent-workflow.log" ] || [ -d "$cur/.claude/agents" ]; then
      echo "$cur"; return 0
    fi
    cur=$(dirname "$cur")
  done
  local root
  root=$(git -C "$dir" rev-parse --show-toplevel 2>/dev/null) || true
  echo "${root:-$dir}"
}

resolve_cwd() {
  local cwd=""
  if [ -n "${PIPELINE_DASHBOARD_PROJECT_DIR:-}" ]; then
    echo "$PIPELINE_DASHBOARD_PROJECT_DIR"; return 0
  fi
  if [ -n "${HERDR_PANE_ID:-}" ]; then
    cwd=$("$H" pane get "$HERDR_PANE_ID" 2>/dev/null | json_get 'd["result"]["pane"].get("foreground_cwd") or d["result"]["pane"].get("cwd")') || true
  fi
  if [ -z "$cwd" ] && [ -n "$ws" ]; then
    cwd=$("$H" workspace get "$ws" 2>/dev/null | json_get 'd["result"]["workspace"].get("cwd")') || true
  fi
  [ -n "$cwd" ] || cwd="$PWD"
  project_root_of "$cwd"
}

# The invoking pane is a Claude pane when herdr has detected the claude agent
# on it; the dashboard then pushes phase/agent tokens to that pane's sidebar row.
claude_pane_env() {
  [ -n "${HERDR_PANE_ID:-}" ] || return 0
  local agent
  agent=$("$H" pane get "$HERDR_PANE_ID" 2>/dev/null | json_get 'd["result"]["pane"].get("agent")') || true
  [ "$agent" = "claude" ] && echo "$HERDR_PANE_ID" || true
}

record_pane_id() {
  local cwd="$1" pane_id="$2"
  python3 - "$cwd" "$pane_id" <<'PY' 2>/dev/null || true
import json, os, sys, time
cwd, pane_id = sys.argv[1], sys.argv[2]
d = os.path.join(cwd, "logs", ".pipeline")
os.makedirs(d, exist_ok=True)
p = os.path.join(d, "herdr.json")
try:
    with open(p) as fh:
        state = json.load(fh)
except Exception:
    state = {}
state["dashboard_pane_id"] = pane_id
state["updated"] = time.strftime("%Y-%m-%dT%H:%M:%S")
with open(p, "w") as fh:
    json.dump(state, fh, indent=2)
    fh.write("\n")
PY
}

open_pane() {
  local cwd out pane_id tab claude_pane
  cwd=$(resolve_cwd)
  claude_pane=$(claude_pane_env)
  local args=(plugin pane open --plugin "$PLUGIN_ID" --entrypoint "$ENTRYPOINT"
              --placement "$placement" --cwd "$cwd" --focus
              --env "PIPELINE_DASHBOARD_PROJECT_DIR=$cwd")
  [ -n "$claude_pane" ] && args+=(--env "PIPELINE_DASHBOARD_CLAUDE_PANE=$claude_pane")
  if [ "$placement" = "split" ]; then
    [ -n "${HERDR_PANE_ID:-}" ] && args+=(--target-pane "$HERDR_PANE_ID")
    args+=(--direction "$direction")
  fi
  save_return_pane
  out=$("$H" "${args[@]}")
  pane_id=$(echo "$out" | json_get 'd["result"]["plugin_pane"]["pane"]["pane_id"]') || true
  if [ -n "$pane_id" ]; then
    "$H" pane rename "$pane_id" "$PANE_LABEL" >/dev/null 2>&1 || true
    record_pane_id "$cwd" "$pane_id"
  fi
  if [ "$placement" = "tab" ]; then
    tab=$(echo "$out" | json_get 'd["result"]["plugin_pane"]["pane"]["tab_id"]') || true
    [ -n "$tab" ] && "$H" tab rename "$tab" "$PANE_LABEL" >/dev/null 2>&1 || true
  fi
}

close_panes() {
  local id closed=1 was_inside=1
  while IFS= read -r id; do
    [ -n "$id" ] || continue
    "$H" pane close "$id" >/dev/null 2>&1 || true
    [ "$id" = "${HERDR_PANE_ID:-}" ] && was_inside=0
    closed=0
  done <<EOF2
$(list_panes)
EOF2
  if [ "$was_inside" -eq 0 ]; then
    focus_return_pane
  else
    rm -f "$return_file"
  fi
  return $closed
}

case "$cmd" in
  open)
    [ -n "$(list_panes)" ] || open_pane
    ;;
  close)
    close_panes || true
    ;;
  toggle)
    if ! close_panes; then
      open_pane
    fi
    ;;
  *)
    echo "usage: dashboard.sh <open|close|toggle>" >&2
    exit 2
    ;;
esac
