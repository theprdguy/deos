# Cross-Model Review

> Reviewing only with Anthropic-family models lets shared blindspots through (timing attack, race condition, certain architecture preferences).
> This prompt requests an independent review of the same deliverable from CODEX (OpenAI family).

## When this applies

Mandatory when `ticket.cross_model: true`. The following ticket types are auto-recommended:
- Authentication (login/signup/session/token)
- Payment (payment/subscription/refund)
- Permissions (RBAC/IDOR/multi-tenant)
- Data integrity (concurrent write, transaction)
- Security-critical (crypto, signing, secret handling)

## Request procedure (CLAUDE1)

### Step 1: Deliverable package
The context bundle to send to CODEX:
1. Ticket body (goal, dod, constraints)
2. PR diff or list of changed file paths
3. Bodies of the key files (CODEX is in a fresh session — provide the paths so it can read them directly)
4. The Claude-side adversarial review result if it exists — share findings, but **do not show the conclusion**. Findings are shared, evaluation stays independent.

### Step 2: Prompt template to send to CODEX

```markdown
# Independent Cross-Model Review — T-XXX

You are reviewing a deliverable produced by Claude. Your job is **independent second opinion**.
Do NOT defer to Claude's review. Find what Claude missed.

## Context
<ticket goal + dod + constraints body>

## Files changed
<git diff or file list>

## Focus areas (based on this ticket's domain)
<per-domain focus, e.g. auth/payment/permissions>

## Specific blindspots to probe (consistent weaknesses of the Anthropic family)
- Timing attacks (missing constant-time comparison)
- Race conditions (DB transaction, mutex)
- Off-by-one in pagination/offset
- TOCTOU (Time-of-check to time-of-use)
- Privilege escalation paths (IDOR, broken access control)
- Error message info leakage
- Replay attack (nonce/timestamp validation)
- Logging that leaks PII

## Output format
1. BLOCKER (N items): <location + why it's risky + concrete example>
2. WARNING (M items): <issues worth a follow-up>
3. AGREE WITH CLAUDE (M items): items from Claude's review you agree with (for reference)
4. NEW FINDINGS (items Claude missed): K items
```

### Step 3: Integrating results
After CODEX replies:
- Sum the BLOCKERs: Claude-side BLOCKERs ∪ CODEX-side BLOCKERs
- Both sides at zero BLOCKERs is the bar for a merge recommendation
- DISAGREEMENT (only one side classifies as BLOCKER) → present options to the user:
  - A) Decide BLOCKER (conservative)
  - B) Downgrade to WARNING (with reason + ADR)
  - C) Further analysis (other tools/people)

### Step 4: Record
Append the result to the ticket's session log:
- `devos/logs/{date}-claude1.md`, or
- `devos/logs/cross-model/{ticket-id}.md` (if long, separate file)

## Operational notes

- **Separate inputs**: complete Claude's review *without* seeing CODEX's conclusion. Then request CODEX. → Blocks mutual influence.
- **Codex unavailable**: if CODEX cannot respond, mark the ticket BLOCKED and surface options in `devos/questions/QUEUE.md`.
- **Cost**: applying cross-model review to every ticket explodes cost. Apply to critical path only.

## Anti-patterns

- "Show CODEX Claude's review conclusion and ask for agreement" → confirmation bias. Violates the independent-request principle.
- "Arbitrarily downgrade a CODEX BLOCKER to WARNING" → severity is fact-based. Downgrading requires an explicit reason + user approval.
- "CODEX and Claude reached the same conclusion, so it's verified" → both can share the same blindspot. Weight independent findings.

## References
- `devos/prompts/claude/review-adversarial.md` — phase integration
- `devos/ETHOS.md` Iron Law #4
- `devos/AI.md` Ticket Standard, `cross_model` field
