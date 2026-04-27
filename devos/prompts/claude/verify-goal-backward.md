# Goal-Backward Verification

> If DOD verification only checks input→output unit pass, broken user journeys slip through.
> This prompt **walks back from the goal** to verify "can the user actually reach this?"

## Core principle

```
Plan completeness ≠ Goal achievement
```

- Every ticket's dod can pass and the goal still not be realized.
- The verifier does not check off dods; the verifier **walks back from the goal**.

## 4-phase backward trace

### Phase 1 — State the goal explicitly
- Restate the ticket goal in one sentence (in user-observable form):
  - Bad: "implement authentication system"
  - Good: "a new user can sign up with email + password and immediately reach the protected /dashboard route"

### Phase 2 — Extract Required Truths
What facts must be simultaneously true for the goal to be true? Decompose into roughly 4–8 items.

Example (the auth goal above):
1. POST /auth/signup endpoint exists + 200 + user record created
2. The user record stores the password as a hash
3. POST /auth/login with the same credentials → 200 + JWT
4. JWT is valid within its expiration
5. Protected routes pass the JWT-verifying middleware
6. /dashboard uses the protection middleware
7. The user is not unexpectedly logged out (session stability)

### Phase 3 — Map artifacts
Map each truth to a concrete code/test artifact.

| Truth | Code artifact | Test artifact |
|-------|---------------|---------------|
| 1 | `apps/api/src/auth/signup.py:23` | `tests/auth/test_signup.py::test_signup_success` |
| 2 | `apps/api/src/auth/signup.py:31` (bcrypt call) | `tests/auth/test_signup.py::test_password_hashed` |
| 3 | `apps/api/src/auth/login.py:18` | `tests/auth/test_login.py::test_login_success` |
| ... | ... | ... |

A truth that doesn't map = **GAP**.

### Phase 4 — Verify wiring
Artifact existence is not enough. Confirm the actual call path (wiring) connects.

- Is the middleware registered on the router? (`app.use(authMiddleware)`)
- Does /dashboard *actually* go through the middleware? (verify the route definition)
- Are the env vars (JWT_SECRET, etc.) actually injected?

Disconnected wiring = **BLOCKER**.

## Output format

```markdown
## Goal-Backward Verification — T-XXX

### Goal (observable form)
<one sentence>

### Required Truths
1. <truth 1>
2. <truth 2>
...

### Coverage Matrix
| # | Truth | Code | Test | Wiring | Verdict |
|---|-------|------|------|--------|---------|
| 1 | ... | path:line | test name | ✓/✗ | VERIFIED / GAP / FAILED |
...

### GAPs
- Truth #N: <why it didn't map> → BLOCKER

### Wiring failures
- <where the connection breaks> → BLOCKER

### Verdict
- VERIFIED: M / N truths
- GAPS: K
- WIRING FAILURES: J
- Recommendation: BLOCK | MERGE OK
```

## Distrust-the-SUMMARY principle

A builder-written SUMMARY / PR description claiming "implemented" or "tests pass" is an **assumption**. Only the following count as evidence:
- Direct read of the code file + line
- Test execution result (pass/fail output)
- Actual HTTP call result (curl or integration test result)

## Anti-patterns
- "All unit tests pass, so OK" → unit pass ≠ user journey complete
- "DOD 100% met" → no guarantee that the DOD covers the full truth set
- "Similar patterns worked before" → verify *this* wiring directly

## When to apply
- `cross_model: true` tickets
- Auth/payment/permissions critical path
- Every PR judged "this is a user-facing feature"
- As Phase 2 of an adversarial review

## References
- `devos/prompts/claude/review-adversarial.md`
- `devos/ETHOS.md` Iron Law #3
