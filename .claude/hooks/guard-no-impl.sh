#!/bin/bash
# Guard: Prevent Claude 1 (Planner) from writing implementation code.
# Used as a Claude Code PreToolUse hook for Write/Edit tools.
#
# Exit 0 = allow, Exit 2 = block with message

INPUT=$(cat)

FILE_PATH=$(echo "$INPUT" | grep -oE '"file_path"\s*:\s*"[^"]*"' | head -1 | sed 's/.*"file_path"\s*:\s*"//;s/"$//')

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
    echo ""
    echo "PLANNER GUARD: You are trying to write to an implementation file."
    echo "   File: $FILE_PATH"
    echo ""
    echo "   As Planner (Claude 1), you must NOT write implementation code."
    echo "   Instead: Create a ticket in devos/tasks/QUEUE.yaml"
    echo "   Owner: CLAUDE2 (app), CODEX (infra/data)"
    echo ""
    echo "   Override: If this is a config/setup file, the user can approve."
    echo ""
    exit 2
  fi
done

exit 0
