# Project State (SSOT)

> Highest-precedence source of truth. CLAUDE1 updates this each session.
> This file ships as a generic example — replace the (TBD) lines with your project.

## North Star
- (TBD) One sentence describing what we're building and why.

## Current Milestone
- (TBD) e.g. "M1 — first user-facing flow"
- DoD:
  - (TBD) verifiable acceptance criteria for the milestone

## What works now (demo path)
- (TBD) the shortest path that demonstrates current capability

## Agent Status
| Agent | Role | Mode | Instruction File |
|-------|------|------|------------------|
| CLAUDE1 (main) | Planner + Researcher + SSOT manager + Orchestrator | interactive | .claude/CLAUDE.md |
| builder (sub-agent) | App / product implementer | in-session (R/W) | .claude/agents/builder.md |
| reviewer (sub-agent) | Adversarial PR reviewer | in-session (READ-ONLY) | .claude/agents/reviewer.md |
| designer (sub-agent) | UI/UX first-pass review | in-session (READ-ONLY) | .claude/agents/designer.md |
| security (sub-agent) | OWASP / STRIDE auditor | in-session (READ-ONLY) | .claude/agents/security.md |
| CODEX | Platform builder + cross-model (b') | external CLI subprocess | AGENTS.md |

## In progress
- (TBD)

## Blockers / Questions
- See questions/QUEUE.md

## Decisions (latest)
- Locked decisions live in devos/CONTEXT.md § Locked Decisions; long-form ADRs under devos/docs/ADR/.

## Next dispatch hint
- When a concrete project appears: fill in PROJECT_STATE + CONTEXT, then submit the first PRD.
