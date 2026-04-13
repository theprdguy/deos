# AI Operating Rules (os2 v3.1)

## Purpose
Run continuous parallel work across 3 AI agents from a single laptop.
Claude 1 plans and researches. Claude 2 and Codex implement.

## SSOT Priority
1) PROJECT_STATE.md
2) docs/API_CONTRACT.md + docs/UI_CONTRACT.md
3) docs/ADR/*
4) tasks/QUEUE.yaml
5) Code
6) Session logs (devos/logs/)
7) Chat logs (least reliable)

## Roles

| Agent | Role | Can Modify | Cannot Modify |
|-------|------|-----------|---------------|
| **CLAUDE1** | Planner + Researcher + SSOT manager | devos/**, config files, AGENTS.md | apps/**, packages/**, tests/** |
| **CLAUDE2** | App builder (backend + GUI design/impl) | apps/api/src/**, apps/web/** | devos/ |
| **CODEX** | Platform builder (infra + data + tests + mechanical) | apps/web/**, apps/api/**, packages/**, infra/**, scripts/**, tests/**, styles/** | devos/ |

## Role Boundaries
- CLAUDE1 MUST NOT write implementation code
- CLAUDE1 creates tickets with WHAT + CONTEXT; builders decide HOW
- Builders MUST NOT modify files outside their ticket scope
- Builders MUST NOT make architectural decisions — queue questions instead

## Ticket Standard
- `status`: Must be `todo` for new tickets — dispatcher only picks up `todo`
- `goal`: What to build (behavioral requirement)
- `context`: Why + technical research from Claude 1
- `constraints`: Technical constraints
- `dod`: Acceptance criteria — each item must be verifiable (input + expected output)
- `files`: Files to modify (ownership scope)
- `verify`: How to check completion
- `deps`: Prerequisite tickets
- `gates`: Verification steps run after completion (tests, secrets scan, review)

## Non-negotiables
- 1 PR = 1 Ticket
- Ownership: only the ticket owner may modify files in ticket.files
- Contract-first: if API/UI behavior changes, update contract docs first
- Done = all gates pass
- Session log written before ending

## Builder Principles

### 1. Root Cause First
Before patching a bug: reproduce, identify root cause, fix, verify reproduction fails.
Record the cause in session log.

### 2. Search Before Build
Check the project for existing utilities and libraries before writing new code.
Duplicate implementations create maintenance debt.

### 3. Completeness
Fulfill every DOD item. Do not skip edge cases, error handling, or empty states.

## Question Queue
- If blocked, add to devos/questions/QUEUE.md (Options + Recommendation + Default)
- Non-blocking: proceed with Default
- Blocking: mark that ticket as blocked
