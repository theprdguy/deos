# Architecture (os2 v3.1)

## System Overview

Vibe Coding OS is a 3-agent Agentic Coding OS that orchestrates AI agents from a single laptop.

```
┌─────────────────────────────────────────┐
│            devos/ (SSOT Brain)           │
│  QUEUE.yaml, PROJECT_STATE.md, logs/     │
│  plans/, questions/, docs/               │
└──────────┬──────────────────┬────────────┘
           │                  │
┌──────────▼──────┐  ┌───────▼───────────────┐
│ Local Mode       │  │ Remote Mode            │
│ Claude Code CLI  │  │ os2-server             │
│ (interactive)    │  │ • Telegram bot         │
│ Account A        │  │ • claude -p pipe mode  │
│                  │  │ • Status queries       │
└──────────┬───────┘  └───────┬───────────────┘
           └─────────┬─────────┘
                     │ Dispatch
         ┌───────────┴───────────┐
         ▼                       ▼
    Claude 2                   Codex
    (Account B)              (Platform)
    App (Backend + GUI)      subprocess
```

## Component Descriptions

### devos/ (The Brain)
All SSOT state lives here. Stack-agnostic. Never in the app code.

| File | Purpose |
|------|---------|
| `AI.md` | Shared operating constitution for all agents |
| `PROJECT_STATE.md` | Current milestone, agent status, blockers |
| `CONTEXT.md` | TL;DR updated each session |
| `TASKS.md` | Human-readable task board |
| `agents/registry.yaml` | 3-agent registry with scopes |
| `tasks/QUEUE.yaml` | Machine-readable ticket queue |
| `plans/pending/` | Plans awaiting approval |
| `plans/approved/` | Approved plans (archive) |
| `plans/rejected/` | Rejected plans with feedback |
| `logs/` | Session logs for cross-agent context |
| `questions/QUEUE.md` | Async question queue |
| `docs/` | API/UI contracts, ADRs, architecture |

### os2-server (The Nervous System)
Python process handling dispatch and automation.

| Module | Purpose |
|--------|---------|
| `planner.py` | `claude -p` pipe mode wrapper |
| `dispatcher.py` | 3-agent dispatch with gate pipeline |
| `ssot.py` | SSOT file readers/writers |
| `approval.py` | Approval workflow state machine |
| `config.py` | Load os2.yaml |

### Agents

| Agent | Mode | Config | Scope |
|-------|------|--------|-------|
| Claude 1 | interactive + pipe | .claude/ | devos/ |
| Claude 2 | subprocess (claude -p) | .claude-b/ | apps/api/src/**, apps/web/** (shared, design-heavy) |
| Codex | subprocess | AGENTS.md | apps/web/** (shared, mechanical), apps/api/**, packages/**, infra/**, scripts/**, tests/**, styles/** |

## Key Design Decisions

### File-based SSOT
All inter-agent communication is through files in devos/.
No shared memory, no RPC. The repo IS the communication channel.

### Dual-mode Claude 1
Local: interactive Claude Code CLI (primary path)
Remote: os2-server invokes `claude -p` for automated workflows
Both modes share the same devos/ state.

### Approval Workflow
PRD → plan → user approval → dispatch. No auto-execution.
Plans saved to plans/pending/, moved to approved/ or rejected/.

### Pipe Mode for Builders
Claude 2 runs as `claude -p` (non-interactive, one-shot).
Fresh context window each invocation = no degradation.
Account B credentials via `CLAUDE_CONFIG_DIR=.claude-b`.

### Shared Scope (apps/web/**)
Both Claude 2 and Codex can modify `apps/web/**`.
Ticket `files:` field enforces exclusive ownership per task.
Claude 2: design judgment, component architecture, UX flow.
Codex: bulk renames, pattern replacements, large mechanical edits.

### Gate Pipeline
After each agent completes, the dispatcher runs:
1. `make test` — test suite
2. `make scan-secrets` — secret scanning
3. agent-review — Claude 1 reviews diff against DOD (PASS/FAIL)
4. ticket verify — ticket-specific verify command

### Auto-chain & Retry
- `auto_chain: true` — completed tickets automatically unlock downstream tickets
- `auto_retry: true` — on gate failure, files are rolled back and the agent retries
- Retry count is priority-based (critical: 3, high: 2, medium/low: 1)
