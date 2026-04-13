#!/usr/bin/env bash

set -e

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT_DIR/.env"

WARN_COUNT=0

GREEN="$(printf '\033[32m')"
YELLOW="$(printf '\033[33m')"
RED="$(printf '\033[31m')"
BLUE="$(printf '\033[34m')"
RESET="$(printf '\033[0m')"

section() {
  printf "\n${BLUE}%s${RESET}\n" "$1"
}

success() {
  printf "${GREEN}✅ %s${RESET}\n" "$1"
}

warn() {
  WARN_COUNT=$((WARN_COUNT + 1))
  printf "${YELLOW}⚠️ %s${RESET}\n" "$1"
}

error() {
  printf "${RED}❌ %s${RESET}\n" "$1" >&2
}

summary_warn() {
  printf "${YELLOW}⚠️ %s${RESET}\n" "$1"
}

load_env_file() {
  if [ -f "$ENV_FILE" ]; then
    set -a
    # shellcheck disable=SC1090
    . "$ENV_FILE"
    set +a
    success "Loaded .env"
  else
    success "No .env found; continuing"
  fi
}

section "1/4 Check required CLI tools"

check_required() {
  local tool="$1"
  local url="$2"
  if command -v "$tool" >/dev/null 2>&1; then
    success "$tool found"
  else
    error "$tool is required. Install: $url"
    exit 1
  fi
}

check_optional() {
  local tool="$1"
  local url="$2"
  if command -v "$tool" >/dev/null 2>&1; then
    success "$tool found"
  else
    warn "$tool not found. Install if needed: $url"
  fi
}

check_required "python3" "https://www.python.org/downloads/"
check_required "pip3" "https://pip.pypa.io/en/stable/installation/"
check_required "git" "https://git-scm.com/downloads"
check_optional "claude" "https://docs.anthropic.com/en/docs/claude-code/overview"
check_optional "codex" "https://platform.openai.com/docs/codex/overview"
check_optional "tmux" "https://github.com/tmux/tmux/wiki/Installing"

section "2/4 Install Python dependencies"
VENV_DIR="$ROOT_DIR/.venv"
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
  success "Created virtual environment at .venv"
else
  success "Virtual environment already exists"
fi
"$VENV_DIR/bin/pip" install -r "$ROOT_DIR/requirements.txt" -q
success "Installed Python dependencies"

section "3/4 Environment variables"
load_env_file
success "Add any project-specific env vars to .env (it is gitignored)"

section "4/4 Check Claude 2 credentials (Account B)"
if [ -f "$ROOT_DIR/.claude-b/.credentials.json" ]; then
  success "Claude 2 credentials found"
else
  warn "Claude 2 credentials not found. To set up Account B:"
  warn "  CLAUDE_CONFIG_DIR=.claude-b claude login"
fi

printf "\n"
if [ "$WARN_COUNT" -eq 0 ]; then
  success "Setup complete with no warnings"
else
  summary_warn "Setup complete with ${WARN_COUNT} warning(s)"
fi
