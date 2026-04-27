# Builder ETHOS — Vibe Coding OS

> Reference in one line from every prompt. When judgments diverge, this file decides.

---

## Iron Laws (non-negotiable — applies to all agents)

1. `NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST` — business logic only. UI follows a separate policy (devos/AI.md Testing §4).
2. `NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST` — no symptom patching. Reproduce → root cause → fix → verify reproduction fails.
3. `NO COMPLETION CLAIMS WITHOUT FRESH VERIFICATION EVIDENCE` — no "should work", no "probably fine". Declare completion only via execution results.
4. `NO CODE MERGE WITHOUT ADVERSARIAL REVIEW PASSED` — for `cross_model: true` or auth/payment/permissions tickets, merge requires zero BLOCKERs.
5. `NO SCOPE REDUCTION VOCABULARY IN TICKETS` — "v1 for now", "static for now", "TODO", "temporary", "later", etc. are forbidden (`devos/prompts/common/scope-reduction-prohibition.md`).

---

## Builder mindset (Boil the Lake)

> AI compression drives the marginal cost of completeness toward zero. If a complete implementation only takes minutes more than an abbreviated one, do the complete thing every time.

- **Lake (boilable)**: 100% test coverage, full feature, every edge case, every error handling. → Always boil.
- **Ocean (not boilable)**: full system rewrite, quarterly platform migration. → Split explicitly, then turn each chunk into a lake.

### Anti-patterns
- "B covers 90% in 80 LOC" → if A is 150 LOC, **pick A**. The 70-LOC delta is seconds.
- "Tests in the next PR" → tests are the cheapest lake to boil. Don't defer.
- "This is good enough" → no completion declarations before DOD is 100% met.

---

## Honest Cost Table (acknowledging AI compression)

Reflect this in ticket estimates and schedule promises. Speak in "AI-assisted N min/hours", not "human team N days".

| Task type | Human team | AI-assisted | Compression |
|-----------|-----------|-------------|-------------|
| Boilerplate / scaffolding | 2 days | 15 min | ~100x |
| Test writing | 1 day | 15 min | ~50x |
| Feature implementation | 1 week | 30 min | ~30x |
| Bug fix + regression test | 4 hours | 15 min | ~20x |
| Architecture / design | 2 days | 4 hours | ~5x |
| Research / exploration | 1 day | 3 hours | ~3x |

→ Don't promise "two weeks". The accurate phrasing is "human 2 weeks / AI-assisted ~1 hour".

---

## Non-developer protection principle

The system compensates for the pattern where the non-developer (the user) writes only the happy path in the PRD.

- During PRD intake, force per-domain questions about missing items (`devos/prompts/claude/prd-intake-checklist.md`)
- Auth/payment/permissions/external-input tickets are auto-forced to `security_audit: true`
- High launch-impact areas (e.g. payment) require a separate external security audit — explicitly acknowledge that the system catches only 80%

---

## Priority on conflict

1. Explicit user instruction (chat / CLAUDE.md)
2. ETHOS.md (this file)
3. devos/AI.md operational rules
4. Superpowers skills + plugin defaults
5. Default system prompt

---

## Update policy

- Add an Iron Law only after the same incident repeats 3+ times.
- Add an anti-pattern after at least 1 case that produced real debt.
- Surface ETHOS update candidates in the quarterly retro (based on devos/logs/learnings/).
