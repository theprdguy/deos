# Builder Guide

## Session Start
1. Read devos/ SSOT files (AI.md, PROJECT_STATE.md, CONTEXT.md)
2. Find your tickets in devos/tasks/QUEUE.yaml (filter by your owner name, status: todo)
3. Check deps — only start if dependencies are done
4. Read latest devos/logs/ for cross-agent context
5. Read relevant contract docs (API_CONTRACT.md or UI_CONTRACT.md)

## Ticket Reading
Claude 1 writes WHAT and CONTEXT. You decide HOW.
- `goal`: What to build
- `context`: Technical context from Claude 1's research
- `dod`: Acceptance criteria (verifiable — input + expected output)
- `files`: Your file scope — ONLY modify these
- `verify`: How to check completion
- `gates`: Verification steps that run after you finish

## Rules
- Modify ONLY files in your ticket's `files:` field
- Contract-first: update contract docs BEFORE code changes
- 1 ticket = 1 PR
- If blocked, add question to devos/questions/QUEUE.md
- Do NOT make architectural decisions — queue a question

## Session Log (mandatory)
Path: `devos/logs/{YYYY-MM-DD}-{agent}-{ticket-ids}.md` — max 50 lines.

```
# Session Log: {AGENT} — {date}
Tickets: {IDs}

## Summary
- 2-3 bullets

## Decisions Made
- Implementation choices and reasoning

## Files Modified
- List of changed files

## Handoff
Done: {ticket} — {what} — files: {list}
Next: {next or "waiting"}
Block: {Q-xxx or "none"}
Log: devos/logs/{file}.md written
```
