#!/usr/bin/env bash
# CLAUDE2 preflight check
# Exit 0 = OK, Exit 1 = not ready (hard block mode)
# --advisory flag: always exit 0 (print only, no block)

ADVISORY=0
[[ "${1:-}" == "--advisory" ]] && ADVISORY=1

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

RED="$(printf '\033[31m')"
GREEN="$(printf '\033[32m')"
YELLOW="$(printf '\033[33m')"
RESET="$(printf '\033[0m')"

FAILED=0
MSGS=()

if [ ! -f "$ROOT_DIR/.claude-b/settings.json" ]; then
  FAILED=1
  MSGS+=("  누락: .claude-b/settings.json (레포 clone이 불완전하거나 .claude-b/ 디렉토리 없음)")
fi

if [ ! -f "$ROOT_DIR/.claude-b/.claude.json" ]; then
  FAILED=1
  MSGS+=("  누락: .claude-b/.claude.json (Account B 미인증)")
  MSGS+=("  복구: CLAUDE_CONFIG_DIR=.claude-b claude login")
fi

if [ "$FAILED" -eq 0 ]; then
  printf "${GREEN}✅ CLAUDE2 세팅 확인${RESET}\n"
  exit 0
fi

if [ "$ADVISORY" -eq 1 ]; then
  printf "${YELLOW}⚠️  CLAUDE2 미세팅 — dispatch 전 아래를 확인하세요${RESET}\n"
  for msg in "${MSGS[@]}"; do printf "%s\n" "$msg"; done
  exit 0
else
  printf "${RED}❌ CLAUDE2 미세팅 — 작업을 중단합니다${RESET}\n" >&2
  for msg in "${MSGS[@]}"; do printf "%s\n" "$msg" >&2; done
  exit 1
fi
