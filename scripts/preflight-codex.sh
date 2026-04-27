#!/usr/bin/env bash
# CODEX dispatch preflight.
# Non-destructive checks only:
# - dangling symlinks under ~/.codex/skills
# - reachable TCP endpoint for ~/.codex/config.toml [mcp_servers.*].url

set -u

CONFIG="$HOME/.codex/config.toml"
SKILLS_DIR="$HOME/.codex/skills"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --config)
      if [ "$#" -lt 2 ]; then
        printf "[preflight] missing value for --config\n" >&2
        exit 1
      fi
      CONFIG="$2"
      shift 2
      ;;
    *)
      printf "[preflight] unknown argument: %s\n" "$1" >&2
      exit 1
      ;;
  esac
done

FAILED=0

display_path() {
  case "$1" in
    "$HOME"/*) printf "~/%s" "${1#"$HOME"/}" ;;
    *) printf "%s" "$1" ;;
  esac
}

check_skill_symlinks() {
  local dir="$1"
  [ -d "$dir" ] || return 0

  local path target display
  for path in "$dir"/*; do
    [ -L "$path" ] || continue
    if [ ! -e "$path" ]; then
      target="$(readlink "$path")"
      display="$(display_path "$path")"
      printf "[preflight] broken skill symlink: %s -> %s (target missing)\n" "$display" "$target" >&2
      printf "[preflight] fix or rm %s\n" "$display" >&2
      FAILED=1
    fi
  done
}

check_mcp_endpoints() {
  local config="$1"
  [ -f "$config" ] || return 0

  python3 - "$config" <<'PY'
import re
import socket
import sys
import time
from urllib.parse import urlparse

config_path = sys.argv[1]
section = None
servers = {}

section_pattern = re.compile(r"^\s*\[([^\]]+)\]\s*(?:#.*)?$")
key_pattern = re.compile(r"^\s*([A-Za-z0-9_-]+)\s*=\s*(.*?)\s*(?:#.*)?$")

try:
    lines = open(config_path, encoding="utf-8").read().splitlines()
except OSError as exc:
    print(f"[preflight] cannot read codex config: {config_path}: {exc}", file=sys.stderr)
    sys.exit(1)

for line in lines:
    section_match = section_pattern.match(line)
    if section_match:
        section = section_match.group(1).strip()
        if section.startswith("mcp_servers."):
            name = section.split(".", 1)[1]
            servers.setdefault(name, {})
        continue

    key_match = key_pattern.match(line)
    if not key_match or not section or not section.startswith("mcp_servers."):
        continue

    name = section.split(".", 1)[1]
    key, raw_value = key_match.groups()
    value = raw_value.strip()
    if (
        (value.startswith('"') and value.endswith('"'))
        or (value.startswith("'") and value.endswith("'"))
    ):
        value = value[1:-1]
    servers.setdefault(name, {})[key] = value

deadline = time.monotonic() + 2.0
failed = False

for name, entry in servers.items():
    if str(entry.get("enabled", "")).strip().lower() == "false":
        continue

    url = entry.get("url")
    if not url:
        continue

    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port
    if port is None:
        if parsed.scheme == "http":
            port = 80
        elif parsed.scheme == "https":
            port = 443

    if not host or port is None:
        print(f"[preflight] codex MCP invalid url: {name} ({url})", file=sys.stderr)
        print("[preflight] disable in ~/.codex/config.toml or fix the url", file=sys.stderr)
        failed = True
        continue

    remaining = deadline - time.monotonic()
    if remaining <= 0:
        print(f"[preflight] codex MCP unreachable: {name} ({url})", file=sys.stderr)
        print("[preflight] disable in ~/.codex/config.toml or start the server", file=sys.stderr)
        failed = True
        continue

    try:
        with socket.create_connection((host, port), timeout=min(remaining, 0.5)):
            pass
    except OSError:
        print(f"[preflight] codex MCP unreachable: {name} ({url})", file=sys.stderr)
        print("[preflight] disable in ~/.codex/config.toml or start the server", file=sys.stderr)
        failed = True

sys.exit(1 if failed else 0)
PY
  local rc=$?
  if [ "$rc" -ne 0 ]; then
    FAILED=1
  fi
}

check_skill_symlinks "$SKILLS_DIR"
check_mcp_endpoints "$CONFIG"

exit "$FAILED"
