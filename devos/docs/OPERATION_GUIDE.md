# Operation Guide (os2 v3.1)

## System Structure

```
[Main machine] ─── Work hub
  Claude 1 CLI (interactive)
  os2-server (run as needed)
  Claude 2 / Codex execution
        │
        │ git push/pull (GitHub private repo)
        │
[Sub machine] ─── Always-on server
  os2-server (launchd, always running)
  Telegram Bot (remote control)
```

---

## Two-machine Handoff

### Main → Sub (leaving your desk)
```bash
make handoff
# Internally: make stop → git commit → git push
# Sub machine Telegram bot continues to accept commands
```

### Sub → Main (returning)
```bash
make pickup
# Internally: git pull → make start
# Claude 1 CLI: claude
```

The sub machine requires no manual intervention — launchd keeps the server running.

---

## PRD → Implementation Workflow

```
1. Submit PRD
   - Local: directly in Claude 1 CLI

2. Claude 1 decomposes
   - Breaks into tickets → saves to devos/plans/pending/

3. Approve
   - Local: review plan then run make approve
   - Remote: Telegram /approve

4. Auto-dispatch
   - CLAUDE2: app work — backend + GUI design/impl (fallback: CODEX)
   - CODEX: platform work — infra + data + tests + mechanical changes

5. Completion notification
   - Receive done/error notification
   - Session log recorded in devos/logs/

6. PR review
   - Claude 1 reviews → approves or requests changes
```

---

## Per-agent Operations

### Claude 1 (Account A, Planner)
- Local: run `claude` → `.claude/CLAUDE.md` auto-loads
- Remote: os2-server calls `claude -p`
- No-impl guard: `.claude/hooks/guard-no-impl.sh`

### Claude 2 (Account B, App Builder)
- os2-server runs `CLAUDE_CONFIG_DIR=.claude-b claude -p`
- Handles backend logic + GUI design/implementation
- Shares `apps/web/**` scope with CODEX — ticket `files:` defines exclusive assignment
- Strength: design judgment, component architecture, UX flow
- Fallback to CODEX if `.claude-b` credentials are not configured

### Codex (Platform Builder)
- os2-server runs `codex exec -s workspace-write`
- Highest token budget → assign complex/large tickets here
- Strength: large file precision edits, bulk renames, pattern replacements

---

## SSOT Management Principles

```
Truth priority:
1. devos/PROJECT_STATE.md
2. devos/docs/API_CONTRACT.md + UI_CONTRACT.md
3. devos/docs/ADR/
4. devos/tasks/QUEUE.yaml
5. Code
6. devos/logs/ (session logs)
7. Chat (lowest)
```

- QUEUE.yaml writes: only by os2-server after approval
- PROJECT_STATE.md writes: only Claude 1
- Contract changes: commit before code changes

---

## Ticket Lifecycle

```
todo → doing → done
           └→ blocked (on error)
```

| Status | Meaning | Set by |
|--------|---------|--------|
| `todo` | Awaiting dispatch (new tickets must use this) | Claude 1 (Planner) |
| `doing` | Agent working | Dispatcher (auto) |
| `done` | Complete + all gates passed | Dispatcher (auto) |
| `blocked` | Failed or gate error | Dispatcher (auto) |
| `parked` | Manually paused | Manual |

> **Note:** `ready`, `pending`, `queued` and other values are not recognized by the dispatcher and will be silently skipped.

- `make queue` to check current status
- For blocked tickets: check `devos/logs/` for error details
- Retry: `make dispatch T=T-XXX`

---

## Troubleshooting

### Server not responding
```bash
make ps       # check status
make tail     # check logs
make restart  # restart
```

### Agent crashed
```bash
make logs           # check session logs
make queue          # check blocked tickets
make dispatch T=T-XXX  # retry
```

### Git conflicts
```bash
# If both machines edited simultaneously
git pull --rebase
# For devos/ files, Claude 1 rewrites from the latest truth
```

### Claude 2 not dispatching
```bash
# Check if Account B credentials exist
ls .claude-b/.credentials.json
# If not found, log in:
CLAUDE_CONFIG_DIR=.claude-b claude login
# Codex will handle CLAUDE2 tickets as fallback in the meantime
```
