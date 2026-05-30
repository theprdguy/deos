#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel)"
tmp_parent="${OS3_BASELINE_TMP_PARENT:-/tmp}"
timestamp="$(date '+%Y%m%d%H%M%S')"
base_dir="${tmp_parent%/}/os3-baseline-${timestamp}-$$"
control_dir="$base_dir/control.git"
worktree_dir="$base_dir/worktree"
pytest_pid=""

stop_pytest() {
  if [ -n "${pytest_pid:-}" ] && kill -0 "$pytest_pid" 2>/dev/null; then
    local signal="${1:-TERM}"
    kill "-$signal" "$pytest_pid" 2>/dev/null || true
    for _ in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
      if ! kill -0 "$pytest_pid" 2>/dev/null; then
        break
      fi
      sleep 0.1
    done
    if kill -0 "$pytest_pid" 2>/dev/null; then
      kill -KILL "$pytest_pid" 2>/dev/null || true
    fi
    wait "$pytest_pid" 2>/dev/null || true
  fi
  pytest_pid=""
}

cleanup() {
  stop_pytest TERM

  if [ -n "${base_dir:-}" ]; then
    if [ -d "$control_dir" ]; then
      git -C "$control_dir" worktree remove --force "$worktree_dir" >/dev/null 2>&1 || true
      git -C "$control_dir" worktree prune >/dev/null 2>&1 || true
    fi
    rm -rf "$base_dir"
  fi
}

on_exit() {
  local status=$?
  trap - EXIT INT TERM
  cleanup
  exit "$status"
}

on_int() {
  trap - EXIT INT TERM
  # Background jobs in a non-interactive bash shell may inherit SIGINT ignored.
  # Use TERM with a KILL fallback so Ctrl-C cannot leave the baseline worktree
  # cleanup stuck behind a sleeping pytest process.
  stop_pytest TERM
  cleanup
  exit 130
}

on_term() {
  trap - EXIT INT TERM
  stop_pytest TERM
  cleanup
  exit 143
}

trap on_exit EXIT
trap on_int INT
trap on_term TERM

mkdir -p "$tmp_parent"
mkdir -p "$base_dir"
cd "$repo_root"
git clone --bare --no-local "$repo_root" "$control_dir"
(
  cd "$control_dir"
  git worktree add --detach "$worktree_dir" HEAD
)

cd "$worktree_dir"
set +e
python3 -m pytest "$@" &
pytest_pid=$!
wait "$pytest_pid"
pytest_status=$?
pytest_pid=""
set -e

exit "$pytest_status"
