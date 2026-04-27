#!/usr/bin/env bash

set -euo pipefail

SCOPE_REDUCTION_PATTERN='(^|[^[:alnum:]_])(v1[[:space:]]*로|v1[[:space:]]*으로[[:space:]]*일단|TODO([[:space:]]*:[[:space:]]*implement)?|FIXME|XXX|WIP[[:space:]-]+placeholder|placeholder[[:space:]-]+for[[:space:]-]+now|stub[[:space:]-]+for[[:space:]-]+now|static[[:space:]-]+for[[:space:]-]+now|나중에|임시|추후|simplified([[:space:]-]+version)?|basic[[:space:]-]+version|minimal[[:space:]-]+implementation|quick[[:space:]-]+fix|wired[[:space:]-]+later|skip[[:space:]-]+for[[:space:]-]+now|future[[:space:]-]+enhancement|hardcoded[[:space:]-]+for[[:space:]-]+now)([^[:alnum:]_]|$)'

run_scope_reduction_self_test() {
  local status=0
  local documented_pattern
  local label expected text actual

  documented_pattern="$(
    python3 - <<'PY'
from pathlib import Path

prompt = Path("devos/prompts/common/scope-reduction-prohibition.md")
marker = "SCOPE_REDUCTION_PATTERN="
for line in prompt.read_text().splitlines():
    stripped = line.strip()
    if stripped.startswith(marker):
        print(stripped.split("=", 1)[1].strip().strip("'"))
        break
PY
  )"

  if [ "$documented_pattern" = "$SCOPE_REDUCTION_PATTERN" ]; then
    printf 'PASS scope-reduction pattern sync: prompt and script match\n'
  else
    printf 'FAIL scope-reduction pattern sync: prompt and script differ\n'
    status=1
  fi

  while IFS=$'\t' read -r label expected text; do
    [ -n "$label" ] || continue
    if printf '%s\n' "$text" | grep -Eiq "$SCOPE_REDUCTION_PATTERN"; then
      actual="match"
    else
      actual="nomatch"
    fi

    if [ "$actual" = "$expected" ]; then
      printf 'PASS scope-reduction fixture: %s (%s)\n' "$label" "$actual"
    else
      printf 'FAIL scope-reduction fixture: %s expected %s got %s\n' "$label" "$expected" "$actual"
      status=1
    fi
  done <<'EOF'
positive-wip-placeholder	match	WIP placeholder remains blocked.
positive-placeholder-for-now	match	Use placeholder for now until the API is wired.
positive-todo-implement	match	TODO: implement validation later.
negative-fallback-placeholder-ui	nomatch	Use fallback placeholder UI copy while loading.
negative-data-placeholder	nomatch	데이터 placeholder 명칭은 UX 용어로 허용.
EOF

  return "$status"
}

if [ "${1:-}" = "--self-test-scope-reduction" ]; then
  run_scope_reduction_self_test
  exit $?
fi

printf '[3/4] ticket-scope\n'

ROOT_DIR="$(pwd)"
QUEUE_FILE="$ROOT_DIR/devos/tasks/QUEUE.yaml"

if [ ! -f "$QUEUE_FILE" ]; then
  echo "⚠️ WARN ticket-scope: queue file missing"
  exit 0
fi

AGENT_NAME_VALUE="${AGENT_NAME:-}"
export AGENT_NAME_VALUE

out_of_scope="$(
python3 - <<'PY'
from pathlib import Path
import os
import subprocess
import sys
import re

queue_path = Path("devos/tasks/QUEUE.yaml")
agent_name = os.environ.get("AGENT_NAME_VALUE", "").strip().upper()


def collect_changed_files() -> list[str]:
    changed: list[str] = []
    seen: set[str] = set()
    commands = []
    head_ok = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode == 0
    if head_ok:
        commands.append(["git", "diff", "--name-only", "HEAD", "--"])
    else:
        commands.append(["git", "diff", "--name-only", "--cached", "--"])
    commands.append(["git", "ls-files", "--others", "--exclude-standard"])
    for cmd in commands:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
        for line in proc.stdout.splitlines():
            path = line.strip()
            if path and path not in seen:
                seen.add(path)
                changed.append(path)
    return changed


def parse_queue() -> list[dict]:
    tickets: list[dict] = []
    current: dict | None = None
    in_files = False
    ticket_start = re.compile(r"^- id:\s*(.+)$")
    field = re.compile(r"^  ([A-Za-z_]+):\s*(.*)$")
    list_item = re.compile(r"^  -\s*(.+)$")

    for raw_line in queue_path.read_text().splitlines():
        match = ticket_start.match(raw_line)
        if match:
            if current:
                tickets.append(current)
            current = {"id": match.group(1).strip(), "files": []}
            in_files = False
            continue
        if current is None:
            continue
        match = field.match(raw_line)
        if match:
            key, value = match.groups()
            if key == "files":
                current["files"] = []
                in_files = True
            else:
                current[key] = value.strip()
                in_files = False
            continue
        if in_files:
            match = list_item.match(raw_line)
            if match:
                current["files"].append(match.group(1).strip())
                continue
        if raw_line and not raw_line.startswith(" "):
            in_files = False
    if current:
        tickets.append(current)
    return tickets


tickets = parse_queue()
doing_tickets = [ticket for ticket in tickets if ticket.get("status") == "doing"]
if agent_name:
    scoped_tickets = [ticket for ticket in doing_tickets if ticket.get("owner", "").upper() == agent_name]
else:
    scoped_tickets = doing_tickets

allowed = {
    path for ticket in scoped_tickets for path in ticket.get("files", [])
    if path and not Path(path).is_absolute()
}

if not allowed:
    sys.exit(0)

outside = [path for path in collect_changed_files() if path not in allowed]
print("\n".join(outside))
PY
)"

if [ -n "$out_of_scope" ]; then
  echo "⚠️ WARN ticket-scope: scope guard warning"
  printf '%s\n' "$out_of_scope"
else
  echo "✅ PASS ticket-scope"
fi
