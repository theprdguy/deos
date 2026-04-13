# Project State (SSOT)

## North Star
- (TBD) One sentence describing what we're building and why.

## Current Milestone
- Bootstrap / Operating System v3.1
- DoD:
  - SSOT files exist and are kept updated
  - `make install && make start` works
  - Approval workflow operational (`make approve`, `make reject`)
  - Dispatch working (`make dispatch T=T-XXX`, `make dispatch-all`)
  - Gate pipeline wired (make test, make scan-secrets)
  - 3-agent registry configured (devos/agents/registry.yaml)
  - Session log system operational (devos/logs/)

## What works now (demo path)
- (TBD)

## Agent Status
| Agent | Role | Status | Instruction File |
|-------|------|--------|------------------|
| claude1-planner | Planner + Researcher | active | .claude/CLAUDE.md |
| claude2-app | App Builder (Account B) | active | .claude-b/CLAUDE.md |
| codex-platform | Platform Builder | active | AGENTS.md |

## In progress
- (TBD)

## Blockers / Questions
- See questions/QUEUE.md

## Decisions (latest)
- ADRs live under docs/ADR/
- v3.1: Automated gate pipeline (tests → secrets → agent-review → verify)
- v3.1: Auto-chain dispatch — completed tickets unlock downstream automatically
- v3.1: Priority-based retry with rollback on gate failure
- v3.1: Claude 2 (Account B) replaces Gemini for app/GUI work

## Next dispatch hint
- When a concrete project appears: fill in PROJECT_STATE, CONTEXT, submit first PRD
