# Vibe Coding OS — Makefile
# Usage: make <target>     (run `make help` for a full list)

.PHONY: start stop restart ps tail handoff pickup install setup install-daemon uninstall-daemon \
        status queue logs pending approve reject dispatch resume dispatch-all \
        test test-queue-schema scan-secrets security-check check-tdd-first-commit pr-check \
        release-template help

PID_FILE := .os2-server.pid
LOG_FILE := $(shell .venv/bin/python3 -c 'from pathlib import Path; import yaml; default = ".os2-server.log"; path = Path("os2.yaml"); config = yaml.safe_load(path.read_text()) if path.exists() else {}; print((((config or {}).get("server") or {}).get("log_file")) or default)')

# ── Server lifecycle ─────────────────────────────────────────────────────────

## Start the dispatcher server (background)
start:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Already running (PID: $$(cat $(PID_FILE)))"; \
	else \
		echo "Log file: $(LOG_FILE)"; \
		.venv/bin/python3 -m server >> $(LOG_FILE) 2>&1 & echo $$! > $(PID_FILE); \
		echo "os2-server started (PID: $$(cat $(PID_FILE)), log: $(LOG_FILE))"; \
	fi

## Stop the dispatcher server
stop:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		kill $$(cat $(PID_FILE)) && rm -f $(PID_FILE); \
		echo "os2-server stopped"; \
	else \
		echo "No running server"; rm -f $(PID_FILE); \
	fi

## Restart the dispatcher server
restart: stop start

## Show server status
ps:
	@if [ -f $(PID_FILE) ] && kill -0 $$(cat $(PID_FILE)) 2>/dev/null; then \
		echo "Running (PID: $$(cat $(PID_FILE)))"; \
	else \
		echo "Stopped"; \
	fi

## Tail the server log
tail:
	@tail -f $(LOG_FILE)

# ── Multi-machine handoff ────────────────────────────────────────────────────

## Wrap up on this machine: stop server, commit, push
handoff:
	@make stop
	@git add -A && git diff --cached --quiet || git commit -m "handoff: $(shell date '+%Y-%m-%d %H:%M')"
	@git push
	@echo "Handoff complete. Run 'make pickup' on the other machine."

## Resume on another machine: pull, preflight, start
pickup:
	@git pull
	@bash scripts/preflight-claude2.sh
	@make start
	@echo "Pickup complete."

## Install Python dependencies
install:
	python3 -m venv .venv && .venv/bin/pip install -r requirements.txt

## Run first-time setup
setup:
	bash scripts/setup.sh

## Sub-machine only: register the server with launchd (auto-start on boot)
install-daemon:
	@cp com.os2.server.plist ~/Library/LaunchAgents/
	@launchctl load ~/Library/LaunchAgents/com.os2.server.plist
	@echo "Registered with launchd — auto-starts on reboot"

## Sub-machine only: unregister the server from launchd
uninstall-daemon:
	@launchctl unload ~/Library/LaunchAgents/com.os2.server.plist
	@rm -f ~/Library/LaunchAgents/com.os2.server.plist
	@echo "Unregistered from launchd"

# ── Status queries (no LLM) ──────────────────────────────────────────────────

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

# ── Approval ─────────────────────────────────────────────────────────────────

## Approve latest pending plan (or: make approve P=plan-id)
approve:
	@.venv/bin/python3 -m server approve $(P)

## Reject latest pending plan: make reject R="reason" [P=plan-id]
reject:
	@if [ -z "$(R)" ]; then echo "Usage: make reject R='reason' [P=plan-id]"; exit 1; fi
	@.venv/bin/python3 -m server reject "$(R)" $(P)

# ── Dispatch ─────────────────────────────────────────────────────────────────

## Dispatch a single ticket: make dispatch T=T-001
dispatch:
	@if [ -z "$(T)" ]; then echo "Usage: make dispatch T=T-001"; exit 1; fi
	@bash scripts/preflight-claude2.sh
	@.venv/bin/python3 -m server dispatch $(T)

## Resume a blocked ticket and dispatch it: make resume T=T-001
resume:
	@if [ -z "$(T)" ]; then echo "Usage: make resume T=T-001"; exit 1; fi
	@bash scripts/preflight-claude2.sh
	@.venv/bin/python3 -m server resume $(T)

## Dispatch every todo ticket in order
dispatch-all:
	@bash scripts/preflight-claude2.sh
	@.venv/bin/python3 -m server dispatch-all

# ── Gates / Verification ─────────────────────────────────────────────────────

## Run tests (gate command — wire to your stack)
test:
	@echo "WARN test runner not wired for this stack yet"

## Run queue schema unit tests
test-queue-schema:
	@python3 -m pytest tests/unit/test_queue_schema.py -v

## Scan for secrets (gate command)
scan-secrets:
	@printf '[1/4] scan-secrets\n'
	@if ! command -v gitleaks >/dev/null 2>&1; then \
		echo "❌ FAIL scan-secrets: gitleaks not found. Install with: brew install gitleaks"; \
		exit 1; \
	fi
	@if gitleaks git --no-banner --redact .; then \
		echo "✅ PASS scan-secrets"; \
	else \
		echo "❌ FAIL scan-secrets"; \
		exit 1; \
	fi

## Run security checks (contract sync + ticket scope + session log)
security-check:
	@bash scripts/check-contract-sync.sh
	@bash scripts/check-ticket-scope.sh
	@bash scripts/check-session-log.sh

## Enforce test-first on required TDD tickets
check-tdd-first-commit:
	@bash scripts/check-tdd-first-commit.sh

## Run all baseline gates
pr-check:
	@status=0; \
	$(MAKE) --no-print-directory scan-secrets || status=1; \
	$(MAKE) --no-print-directory security-check || status=1; \
	$(MAKE) --no-print-directory check-tdd-first-commit || status=1; \
	if [ "$$status" -eq 0 ]; then \
		echo "All baseline gates passed"; \
	else \
		echo "Baseline gates failed"; \
		exit $$status; \
	fi

# ── Release / template ───────────────────────────────────────────────────────

release-template:
	bash scripts/release-template.sh

# ── Help ─────────────────────────────────────────────────────────────────────

help:
	@echo "Vibe Coding OS — v3.4"
	@echo ""
	@echo "Setup:"
	@echo "  make setup              First-time setup wizard"
	@echo "  make install            Install Python dependencies"
	@echo ""
	@echo "Server:"
	@echo "  make start              Start dispatcher (background)"
	@echo "  make stop               Stop dispatcher"
	@echo "  make restart            Restart dispatcher"
	@echo "  make ps                 Show server status"
	@echo "  make tail               Tail server log"
	@echo ""
	@echo "Multi-machine:"
	@echo "  make handoff            Stop server + git push"
	@echo "  make pickup             git pull + start server"
	@echo "  make install-daemon     Register launchd plist (sub-machine)"
	@echo "  make uninstall-daemon   Unregister launchd plist"
	@echo ""
	@echo "Status:"
	@echo "  make status             Show project status"
	@echo "  make queue              Show ticket queue"
	@echo "  make logs               Show recent session logs"
	@echo "  make pending            Show pending approval plans"
	@echo ""
	@echo "Approval:"
	@echo "  make approve            Approve latest pending plan"
	@echo "  make reject R='...'     Reject latest pending plan"
	@echo ""
	@echo "Dispatch:"
	@echo "  make dispatch T=T-001   Dispatch a single ticket"
	@echo "  make resume T=T-001     Resume a blocked ticket"
	@echo "  make dispatch-all       Dispatch every todo ticket"
	@echo ""
	@echo "Gates:"
	@echo "  make test               Run tests (wire to your stack)"
	@echo "  make scan-secrets       Run gitleaks secret scan"
	@echo "  make pr-check           Run all baseline gates"
