# OS3 Operation Guide

## System Shape

OS3 runs as a file-based product-building operating system:

```text
PM / Claude 1 main
  -> plan, clarify, decompose, route
  -> Builder sub-agent for scoped product/app implementation
  -> Codex subprocess for platform, tests, infra, backend/data, and hardening
  -> Reviewer/Security/Designer read-only review chain
  -> Gemini visual reviewer for material UI outcomes
```

`bin/os3` is the primary CLI. `bin/osn` remains a compatibility alias for older
automation. `osn.yaml` remains the compatibility config filename.

## Daily Flow

### Start

```bash
git pull
bin/os3 status
claude
```

Claude 1 should read the session-start SSOT files once, then work from the
current ticket/plan context.

### End

```bash
bin/os3 archive
git status --short
git push
```

Archive only moves `done` tickets out of QUEUE. Historical ticket IDs are kept.

## PRD To Implementation

1. PM describes desired product outcome.
2. Claude 1 clarifies product intent and decomposes into tickets.
3. Plan is saved to `devos/plans/pending/` and waits for approval.
4. Approval dispatches scoped tickets by owner:
   - BUILDER: in-session app/product implementation.
   - CODEX: subprocess for platform, tests, infra, backend/data, and hardening.
   - CLAUDE1: policy/SSOT work only.
5. Gates run through `bin/os3 pr-check` and ticket-specific `verify`.
6. Reviewer is independent and read-only.
7. Security runs for risk-bearing work.
8. Gemini visual review runs for Production UI or material visual output.
9. PM decides only product judgment, visual taste, final acceptance, or waiver.

## Agent Responsibilities

| Agent | Responsibility |
| --- | --- |
| Claude 1 main | Product clarification, planning, ticket writing, routing, orchestration, SSOT updates |
| Builder | Scoped implementation where product feel or app UX matters |
| Codex | Tests, infra, backend/API/data/shared packages, policy enforcement, mechanical changes, objective UI fixes |
| Reviewer | Independent quality review; no writes |
| Security | OWASP/STRIDE risk review; no writes |
| Designer | UI/UX review and PRD intake design critique; no writes |
| Gemini | Rendered visual outcome review |

## SSOT Priority

1. `devos/PROJECT_STATE.md`
2. Contract docs under `devos/docs/`
3. ADRs under `devos/docs/ADR/`
4. `devos/tasks/QUEUE.yaml`
5. Code
6. Session logs under `devos/logs/`
7. Chat history

## Ticket Lifecycle

Valid statuses:

```text
todo -> doing -> code_ready -> done
              -> needs_pm
              -> blocked
              -> parked
```

- `todo`: dispatchable.
- `doing`: implementation in progress.
- `code_ready`: implementation finished, gates/reviews/PM decisions may remain.
- `needs_pm`: PM product judgment, visual taste, acceptance, or waiver needed.
- `done`: required gates, reviews, PM decisions, waivers, and records are closed.
- `blocked`: cannot proceed without fix or decision.
- `parked`: intentionally out of active flow.

Do not use `ready`, `pending`, or `queued` as ticket statuses.

## Common Commands

```bash
bin/os3 status
bin/os3 queue
bin/os3 pending
bin/os3 approve
bin/os3 reject "reason"
bin/os3 dispatch T-XXX
bin/os3 dispatch-codex T-XXX
bin/os3 dispatch-all
bin/os3 verify T-XXX
T=T-XXX AGENT_NAME=CODEX bin/os3 pr-check
bin/os3 user-review T-XXX
bin/os3 archive
```

## Launchd Server

Use `com.os3.server.plist` if a background server is needed. Update its
`WorkingDirectory` to the local OS3 path first.

```bash
cp com.os3.server.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.os3.server.plist
launchctl kickstart -k gui/$(id -u)/com.os3.server
```

## Troubleshooting

- Queue or status looks stale: run `bin/os3 status` and inspect `devos/PROJECT_STATE.md`.
- A ticket is blocked: inspect the latest relevant `devos/logs/` entry.
- A UI result needs product judgment: use `bin/os3 user-review T-XXX` after PM review.
- Gemini API path fails: use `bin/os3 gemini pending` then `bin/os3 gemini next`.
- Historical `T-OS2-*` or `T-OSN-*` IDs are expected; do not rename them without a dedicated migration ticket.
