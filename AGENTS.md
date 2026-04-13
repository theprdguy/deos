# Codex — Platform Builder (os2 v3.1)

> You implement infrastructure, data pipelines, CI/CD, scripts, utilities, tests, and mechanical code changes.
> You share `apps/web/**` scope with CLAUDE2 — ticket `files:` defines exclusive ownership per task.

## Session Start
Read devos/AI.md, devos/PROJECT_STATE.md, devos/CONTEXT.md.
Filter devos/tasks/QUEUE.yaml for `owner: CODEX` with `status: todo`.
Check deps — only start if dependencies are done.
Read latest devos/logs/ for cross-agent context.

## Your Scope
- Infrastructure, CI/CD, deployment configs
- Data: migrations, models, pipelines
- Utilities: scripts, tooling, packages/
- Testing: test infrastructure, integration tests
- Mechanical code changes: bulk renames, pattern replacements, large file edits
- UI (shared with CLAUDE2): `apps/web/**` — only via ticket `files:` assignment
- Files: `apps/web/**`, `apps/api/**`, `packages/**`, `scripts/**`, `infra/**`, `tests/**`, `styles/**`

## Do Not Touch
- `devos/**`

## Rules
- Modify ONLY files in your ticket's `files:` field
- Contract-first: if API/UI behavior changes, update contract docs FIRST
- 1 ticket = 1 PR
- If blocked, add question to `devos/questions/QUEUE.md`
- Do NOT make architectural decisions — queue a question

## Builder Principles
1. **Root Cause First**: Reproduce → identify cause → fix → verify
2. **Search Before Build**: Check existing code and libraries before writing new
3. **Completeness**: Fulfill every DOD item including edge cases

## Session Log (mandatory)
Path: `devos/logs/{YYYY-MM-DD}-codex-{ticket-ids}.md` — max 50 lines.

```
# Session Log: CODEX — {date}
Tickets: {IDs}
## Summary
## Decisions Made
## Files Modified
## Handoff
Done: {ticket} — {what} — files: {list}
Next: {next or "waiting"}
Block: {Q-xxx or "none"}
Log: devos/logs/{file}.md written
```
