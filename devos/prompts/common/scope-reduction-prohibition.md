# Scope-Reduction Prohibition

> If any of these appear in a ticket goal/dod/context, **fix it before proceeding**. Words that slip in quietly become permanent technical debt.

## Forbidden-word table

| Forbidden word / phrase | Why forbidden | Replacement action |
|--------------|---------|-----------|
| `v1`, `v2`, `v1 for now` | The promised future v2 never ships → permanent v1 debt | Implement fully in one shot, or split into explicitly dependent tickets |
| `static for now` | "for now" hardens into permanent | Implement dynamic immediately, or split tickets |
| `WIP placeholder`, `placeholder for now` | Ends up exposed in prod. Exception: legitimate UX/data naming like `fallback placeholder UI`, `data placeholder` | Decide the actual data source first, then ticket |
| `TODO`, `FIXME`, `XXX` | Accumulates in both code and tickets → no one cleans them up | Create a separate ticket instead of TODO; comments only describe *root cause* |
| `temporary`, `later`, `down the road` | "later" never comes | Handle now, or create a dependent ticket |
| `simplified version` | "simplified" has no definition | Promise a clear feature set, or split |
| `basic version` | "basic" varies by person | List concrete features in DOD |
| `minimal implementation` | "minimal" doesn't guarantee user value is met | Map user value → required features explicitly |
| `quick fix` | Avoids root cause | Invoke the systematic-debugging skill |
| `will be wired later` | Unwired code is dead code | Include wiring in the same ticket |
| `skip for now` | Skipped cases are first discovered in prod | Include explicitly in DOD or document N/A reason |
| `future enhancement` | Backlog accumulates indefinitely | Make no promise. If needed, file a separate ticket |
| `hardcoded for now` | Hardcodes become permanent | Move to config/env immediately |

## Check points

1. **At PRD decomposition** — CLAUDE1 self-checks immediately before writing the ticket
2. **Just before approval** — recommended auto-grep when saving to devos/plans/pending/:
   ```bash
   SCOPE_REDUCTION_PATTERN='(^|[^[:alnum:]_])(v1[[:space:]]*로|v1[[:space:]]*으로[[:space:]]*일단|TODO([[:space:]]*:[[:space:]]*implement)?|FIXME|XXX|WIP[[:space:]-]+placeholder|placeholder[[:space:]-]+for[[:space:]-]+now|stub[[:space:]-]+for[[:space:]-]+now|static[[:space:]-]+for[[:space:]-]+now|나중에|임시|추후|simplified([[:space:]-]+version)?|basic[[:space:]-]+version|minimal[[:space:]-]+implementation|quick[[:space:]-]+fix|wired[[:space:]-]+later|skip[[:space:]-]+for[[:space:]-]+now|future[[:space:]-]+enhancement|hardcoded[[:space:]-]+for[[:space:]-]+now)([^[:alnum:]_]|$)'
   grep -E -i "$SCOPE_REDUCTION_PATTERN" devos/plans/pending/*.yaml
   ```
   Verify the regression fixtures with `bash scripts/check-ticket-scope.sh --self-test-scope-reduction`.
3. **At PR review** — adversarial review classifies hits as BLOCKER

## Exception clauses (narrow)

Forbidden words are allowed only in these three cases:
1. **Explicit Locked-Decision split**: intentionally staged per a `D-XX` locked decision — the ticket must include a `per D-XX` reference
2. **Spike/Research ticket**: a learning-only ticket (`tdd: skip`, output = document) marked `spike` — the output is an ADR, not production code
3. **External constraint**: external API/regulation makes immediate implementation impossible — context must list the reason + the blocking ticket ID

Outside these three, fix unconditionally.

## References

- `devos/AI.md` Ticket Standard
- `devos/ETHOS.md` Boil the Lake
- `devos/prompts/claude/decompose-prd.md` — Step 0 self-checks against this file
