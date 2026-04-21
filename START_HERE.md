# START HERE — Vibe Coding OS v3.1

## First-time setup

```bash
make setup          # CLI checks + Python venv + Claude 2 auth guide
# or:
make install        # just Python dependencies
```

**Optional — Claude 2 (Account B):**
```bash
CLAUDE_CONFIG_DIR=.claude-b claude login
# Without this, CLAUDE2 tickets automatically fall back to Codex
```

**Optional — sub-machine daemon (auto-start on boot):**
```bash
# Edit com.os2.server.plist — update WorkingDirectory to your project path
make install-daemon
```

---

## Daily routine

**Start a session:**
```bash
make pickup         # git pull + CLAUDE2 preflight check + start server
# or:
make start          # just start server
```
> `make pickup` blocks if `.claude-b/.claude.json` (Account B auth) is missing.
> To fix: `CLAUDE_CONFIG_DIR=.claude-b claude login`

**Open Claude 1:**
```bash
claude              # auto-reads .claude/CLAUDE.md (shows CLAUDE2 status banner on start)
```

**Submit a PRD to Claude 1 → review the plan → approve:**
```bash
make pending        # review pending plan
make approve        # approve → tickets added → builders auto-dispatched
# or:
make reject R="feedback"  # reject → Claude 1 revises
```

**Check progress:**
```bash
make queue          # ticket statuses
make logs           # recent session logs
make status         # project status
```

**End session:**
```bash
make handoff        # stop + git push (switch machines)
# or:
make stop           # just stop server
```

---

## New project setup

1. Fill in `devos/PROJECT_STATE.md` — north star, milestone
2. Fill in `devos/CONTEXT.md` — what you're building, tech stack
3. Submit first PRD to Claude 1
4. `make approve` → builders start automatically

---

## Command cheat sheet

```bash
# Setup
make setup            # first-time setup
make install          # Python dependencies only

# Server
make start            # start background server
make stop             # stop server
make restart          # restart
make ps               # status check
make tail             # live log tail

# Multi-machine
make handoff          # stop + git push
make pickup           # git pull + start

# Status (no LLM)
make status           # project status
make queue            # ticket queue
make logs             # recent session logs
make pending          # plans awaiting approval

# Approval
make approve          # approve latest plan
make reject R='...'   # reject with reason

# Dispatch
make dispatch T=T-001 # single ticket
make dispatch-all     # all todo tickets

# Gates
make test             # run tests
make scan-secrets     # secret scan
make pr-check         # all pre-PR checks
```

---

## Key rules

- **Claude 1 = Planner + Researcher** — plans, researches, creates tickets, reviews. Never codes.
- **Claude 2 / Codex = Builders** — implement from tickets, write session logs.
- **Tickets = WHAT + CONTEXT** — Claude 1 writes requirements + research; builders decide HOW.
- **Status must be `todo`** for new tickets — dispatcher only picks up `todo`.
- **Approve before dispatch** — no auto-execution without your approval.

---

## Learn more

- Architecture: `devos/docs/ARCHITECTURE.md`
- Operation Guide: `devos/docs/OPERATION_GUIDE.md`
- Builder Guide: `devos/docs/BUILDER_GUIDE.md`
- AI constitution: `devos/AI.md`
