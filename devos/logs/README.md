# Session Logs — Format Specification

## Purpose
Session logs enable cross-agent visibility. Each builder writes a log at session end.
Claude 1 reads these at session start to understand builder context.

## File Naming
`{YYYY-MM-DD}-{agent}-{ticket-ids}.md`

Examples:
- `2026-03-15-codex-T-001.md`
- `2026-03-15-claude2-T-002-T-003.md`
- `2026-03-15-claude1.md`

## Required Sections

```
# Session Log: {AGENT} — {date}
Tickets: {ticket IDs worked on}

## Summary
- What was accomplished (2-3 bullets)

## Decisions Made
- Implementation choices and reasoning

## Files Modified
- List of files changed

## Handoff
Done: {ticket ID} — {what} — files: {list}
Next: {next ticket or "waiting"}
Block: {Q-xxx or "none"}
Log: devos/logs/{filename} written
```

## Guidelines
- **Max 50 lines** per log (token-efficient)
- Focus on decisions and context, not code details
- Always include the Handoff section
