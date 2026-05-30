#!/bin/bash
# Guard: Prevent Claude 1 (Planner) from writing implementation code.
# Used as a Claude Code PreToolUse hook for Write/Edit tools.
#
# Modes:
#   default (no flag) — block (exit 2) on impl path violation
#   --advisory        — print warning to stderr but allow (exit 0)
#
# The advisory mode is useful for sessions where the user has explicitly
# acknowledged that some impl-path edits are needed (e.g., during cherry-pick
# integration work) but still wants visibility into boundary crossings.
# Inspired by GSD's gsd-workflow-guard.js advisory pattern.

ADVISORY=0
for arg in "$@"; do
  if [ "$arg" = "--advisory" ]; then
    ADVISORY=1
  fi
done

INPUT=$(cat)

# osn v0.1: .claude-b/ removed (W6 sunset). Account B branch retired.
# Sub-agents (builder/reviewer/designer/security) run in-session — their own scope is enforced by
# subagent_type Tools whitelist, not by this hook.

FILE_PATH=$(echo "$INPUT" | python3 -c "import json,sys; d=json.load(sys.stdin); print(d.get('file_path',''))" 2>/dev/null)

if [ -z "$FILE_PATH" ]; then
  exit 0
fi

# Implementation directories Claude 1 must NOT write to
IMPL_PATTERNS=(
  "apps/"
  "packages/"
  "infra/"
  "scripts/"
  "tests/"
  "__tests__/"
  "src/"
  "lib/"
  "components/"
  "pages/"
  "styles/"
  "public/"
  "assets/"
)

for pattern in "${IMPL_PATTERNS[@]}"; do
  if echo "$FILE_PATH" | grep -qE "(^|/)${pattern}"; then
    if [ "$ADVISORY" = "1" ]; then
      # Advisory mode: print to stderr, allow tool to proceed
      echo "" >&2
      echo "⚠ PLANNER ADVISORY: writing to an implementation path." >&2
      echo "   File: $FILE_PATH" >&2
      echo "   This edit is allowed because --advisory is set, but it crosses CLAUDE1's role boundary." >&2
      echo "   Consider: ticket in devos/tasks/QUEUE.yaml owned by BUILDER or CODEX." >&2
      echo "" >&2
      exit 0
    fi
    echo ""
    echo "PLANNER GUARD: You are trying to write to an implementation file."
    echo "   File: $FILE_PATH"
    echo ""
    echo "   As Planner (Claude 1), you must NOT write implementation code."
    echo "   Instead: Create a ticket in devos/tasks/QUEUE.yaml"
    echo "   Owner: BUILDER for ambiguous/product-facing UI, CODEX for infra/tests/backend/data/shared/policy work."
    echo ""
    echo "   Override: If this is a config/setup file, the user can approve."
    echo "   Advisory: pass --advisory to log violations without blocking."
    echo ""
    exit 2
  fi
done

exit 0
