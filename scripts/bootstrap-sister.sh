#!/usr/bin/env bash

set -euo pipefail

usage() {
  echo "Usage: scripts/bootstrap-sister.sh [--force] <target-dir>" >&2
}

FORCE=0
if [ "${1:-}" = "--force" ]; then
  FORCE=1
  shift
fi

if [ "$#" -ne 1 ] || [ -z "${1:-}" ]; then
  usage
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TARGET_DIR="$1"

SOURCE_PROMPTS_DIR="$ROOT_DIR/devos/prompts"
TARGET_PROMPTS_DIR="$TARGET_DIR/devos/prompts"
INHERIT_PROMPTS=(
  "claude/decompose-prd.md"
  "claude/prd-intake-checklist.md"
  "common/scope-reduction-prohibition.md"
)

# V39-01: inherit decompose-prd / prd-intake-checklist / scope-reduction
# (Step 0.5/3.5 user journey + Type A/B/C 분류 + 금지어 검사 자동 inherit)
for rel in "${INHERIT_PROMPTS[@]}"; do
  src="$SOURCE_PROMPTS_DIR/$rel"
  dst="$TARGET_PROMPTS_DIR/$rel"
  if [ ! -f "$src" ]; then
    echo "warn: source prompt missing: $rel" >&2
    continue
  fi
  if [ -e "$dst" ] && [ "$FORCE" -eq 0 ]; then
    echo "skip (exists): $rel"
    continue
  fi
  mkdir -p "$(dirname "$dst")"
  cp "$src" "$dst"
  echo "inherited prompt: $rel"
done

echo "bootstrapped prompts in $TARGET_DIR"
