# Vibe Coding OS Makefile
# Usage: make <target>

.PHONY: start stop restart ps tail handoff pickup install setup install-daemon uninstall-daemon status queue logs pending approve reject dispatch dispatch-all test scan-secrets security-check pr-check help

PID_FILE := .os2-server.pid
LOG_FILE := $(shell .venv/bin/python3 -c 'from pathlib import Path; import yaml; default = ".os2-server.log"; path = Path("os2.yaml"); config = yaml.safe_load(path.read_text()) if path.exists() else {}; print((((config or {}).get("server") or {}).get("log_file")) or default)' 2>/dev/null || echo ".os2-server.log")

# ── Server ────────────────────────────────────────────────────────────────────

## Start server in background
start:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Server already running (PID: $$(cat $(PID_FILE)))"; \
	else \
		echo "Log file: $(LOG_FILE)"; \
		.venv/bin/python3 -m server >> $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE); \
		echo "os2-server started (PID: $$(cat $(PID_FILE)), log: $(LOG_FILE))"; \
	fi

## Stop server
stop:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		kill $$(cat $(PID_FILE)) && rm -f $(PID_FILE); \
		echo "os2-server stopped"; \
	else \
		echo "No server running"; rm -f $(PID_FILE); \
	fi

## Restart server
restart: stop start

## Check server status
ps:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Running (PID: $$(cat $(PID_FILE)))"; \
	else \
		echo "Stopped"; \
	fi

## Tail server log live
tail:
	@tail -f $(LOG_FILE)

# ── Multi-computer Handoff ────────────────────────────────────────────────────

## Hand off to another machine (stop + git push)
handoff:
	@make stop
	@git add devos/ && git diff --cached --quiet || git commit -m "handoff: $(shell date '+%Y-%m-%d %H:%M')"
	@git push
	@echo "Handoff complete. Run 'make pickup' on the other machine."

## Pick up from another machine (git pull + start)
pickup:
	@git pull
	@make start
	@echo "Pickup complete."

# ── Setup ─────────────────────────────────────────────────────────────────────

## Install Python dependencies
install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

## Run first-time setup
setup:
	bash scripts/setup.sh

## Register server as launchd daemon (macOS auto-start on boot)
install-daemon:
	@cp com.os2.server.plist ~/Library/LaunchAgents/
	@launchctl load ~/Library/LaunchAgents/com.os2.server.plist
	@echo "launchd registered — server will auto-start on boot"

## Unregister launchd daemon
uninstall-daemon:
	@launchctl unload ~/Library/LaunchAgents/com.os2.server.plist
	@rm -f ~/Library/LaunchAgents/com.os2.server.plist
	@echo "launchd registration removed"

# ── Status Queries (no LLM) ───────────────────────────────────────────────────

## Show current project status
status:
	@.venv/bin/python3 -m server status

## Show ticket queue
queue:
	@.venv/bin/python3 -m server queue

## Show recent session logs
logs:
	@.venv/bin/python3 -m server logs

## Show pending approval plans
pending:
	@.venv/bin/python3 -m server pending

# ── Approval ──────────────────────────────────────────────────────────────────

## Approve latest pending plan (or: make approve P=plan-id)
approve:
	@.venv/bin/python3 -m server approve $(P)

## Reject latest pending plan: make reject R="reason" [P=plan-id]
reject:
	@if [ -z "$(R)" ]; then echo "Usage: make reject R='reason' [P=plan-id]"; exit 1; fi
	@.venv/bin/python3 -m server reject "$(R)" $(P)

# ── Dispatch ──────────────────────────────────────────────────────────────────

## Dispatch a single ticket: make dispatch T=T-001
dispatch:
	@if [ -z "$(T)" ]; then echo "Usage: make dispatch T=T-001"; exit 1; fi
	@.venv/bin/python3 -m server dispatch $(T)

## Dispatch all todo tickets
dispatch-all:
	@.venv/bin/python3 -m server dispatch-all

# ── Gates / Verification ──────────────────────────────────────────────────────

## Run tests (wire to your test runner)
test:
	@echo "TODO: wire to your test runner (e.g. pytest, vitest)"

## Scan for secrets
scan-secrets:
	@echo "TODO: wire to secret scanner (e.g. trufflehog, gitleaks)"

## Run security checks (tag-based gate for auth tickets)
security-check:
	@echo "TODO: wire to security scanner"

## Run all pre-PR checks
pr-check: test scan-secrets
	@echo "All checks passed."

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo "Vibe Coding OS v3.1 — Agentic Coding OS"
	@echo ""
	@echo "Setup:"
	@echo "  make setup            First-time setup (CLI checks + venv + Claude 2)"
	@echo "  make install          Install Python dependencies"
	@echo ""
	@echo "Server:"
	@echo "  make start            Start server in background"
	@echo "  make stop             Stop server"
	@echo "  make restart          Restart server"
	@echo "  make ps               Check server status"
	@echo "  make tail             Tail server log live"
	@echo ""
	@echo "Multi-computer:"
	@echo "  make handoff          Stop + git push (switch to another machine)"
	@echo "  make pickup           git pull + start (resume on this machine)"
	@echo ""
	@echo "Status:"
	@echo "  make status           Project status"
	@echo "  make queue            Ticket queue"
	@echo "  make logs             Recent session logs"
	@echo "  make pending          Plans awaiting approval"
	@echo ""
	@echo "Approval:"
	@echo "  make approve          Approve latest plan"
	@echo "  make reject R='...'   Reject latest plan with reason"
	@echo ""
	@echo "Dispatch:"
	@echo "  make dispatch T=T-001 Dispatch a single ticket"
	@echo "  make dispatch-all     Dispatch all todo tickets"
	@echo ""
	@echo "Gates:"
	@echo "  make test             Run tests"
	@echo "  make scan-secrets     Scan for secrets"
	@echo "  make pr-check         Run all pre-PR checks"
