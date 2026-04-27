# Security Audit (OWASP A01–A10 + STRIDE)

> Auto-applied to tickets with `ticket.security_audit: true` or auth/payment/permissions/external-input tickets.
> A secrets scan (gitleaks) only catches embedded keys. Auth-flow and authorization defects need a separate review.

## Stated limitations (be honest)

This prompt borrows only the *prompt portion* of GStack's `/cso`. The original's 22MB ML classifier, Haiku voting, canary tokens — none of that infrastructure is borrowed. Effectiveness ~70–80%. **High launch-impact areas (e.g. payment processing) require a separate external security audit.**

## Procedure (CLAUDE1)

1. Identify the ticket's domain
2. Review that domain plus the common items
3. Classify findings as BLOCKER/WARNING (same severity scheme as adversarial review)
4. Either fold the result into PR review, or use it as justification to strengthen the ticket dod

---

## OWASP Top 10 (2021)

### A01: Broken Access Control
- [ ] **IDOR**: call an endpoint with another user's ID → returns 401/403?
- [ ] **Privilege escalation**: a regular user calls an admin endpoint → blocked?
- [ ] **Forced browsing**: any route that bypasses the auth middleware?
- [ ] **CORS misconfiguration**: `Access-Control-Allow-Origin: *` + credentials?
- [ ] **JWT verification**: `alg: none` allowed? signature check missing?
- [ ] **Default deny**: every route blocked by default, allow explicitly?

### A02: Cryptographic Failures
- [ ] **Password hash**: bcrypt/scrypt/argon2 used? cost factor sufficient?
- [ ] **Transport encryption**: HTTPS enforced? HSTS header?
- [ ] **At-rest encryption**: PII stored in plaintext in the DB?
- [ ] **Weak algorithm**: MD5/SHA1 used? DES?
- [ ] **Hardcoded secret**: API key / JWT secret in code?
- [ ] **CSRF token**: if removed, replaced by SameSite=Strict cookie?

### A03: Injection
- [ ] **SQL injection**: parameterized query enforced? string concat?
- [ ] **NoSQL injection**: MongoDB query taking user input directly?
- [ ] **Command injection**: shell call with user input?
- [ ] **LDAP injection**: search filter with user input?
- [ ] **XSS**: escape on output? if markdown/HTML allowed, sanitize library used?
- [ ] **HTML/XML injection**: feed/RSS output?

### A04: Insecure Design
- [ ] **Threat model**: was a threat model written for this feature? (see STRIDE section)
- [ ] **Rate limiting**: brute-force prevention?
- [ ] **Lockout**: account lockout policy?
- [ ] **Idempotency**: payments and other critical operations have idempotency key?
- [ ] **Business logic abuse**: negative quantity, refund-then-refund-again, etc.?

### A05: Security Misconfiguration
- [ ] **Default credentials**: admin/admin enabled? force change at first setup?
- [ ] **Error messages**: stack traces exposed? raw DB error?
- [ ] **Unneeded features**: debug endpoints still present?
- [ ] **Headers**: X-Frame-Options, CSP, X-Content-Type-Options set?
- [ ] **Version disclosure**: Server header, X-Powered-By exposed?
- [ ] **Dev tools**: GraphQL playground, /admin access restricted?

### A06: Vulnerable and Outdated Components
- [ ] **Dependency audit**: `npm audit`, `pip-audit`, `cargo audit` running in CI?
- [ ] **EOL libraries**: versions no longer receiving security patches?
- [ ] **Pinning**: lockfile committed?
- [ ] **CVE monitoring**: dependabot/renovate enabled?

### A07: Identification and Authentication Failures
- [ ] **Brute force**: rate limit + lockout?
- [ ] **Credential stuffing**: known-leaked passwords blocked? (haveibeenpwned API)
- [ ] **Session fixation**: session ID reissued after login?
- [ ] **Weak password policy**: min length, charset?
- [ ] **2FA backup code**: single-use? stored hashed?
- [ ] **Password reset**: token single-use? time limit?

### A08: Software and Data Integrity Failures
- [ ] **CI/CD pipeline**: pulling deps from untrusted sources?
- [ ] **Auto-update**: signature verification?
- [ ] **Deserialization**: `pickle` / `yaml.load()` on user input?
- [ ] **CSP**: script-src restricted? eval/inline blocked?

### A09: Security Logging and Monitoring Failures
- [ ] **Auth event logs**: login/logout/lockout/password-reset all recorded?
- [ ] **PII masking**: are passwords/tokens/card numbers in logs?
- [ ] **Timestamps**: UTC + ISO 8601?
- [ ] **Log integrity**: append-only? external storage?
- [ ] **Alerts**: notify on consecutive failures, privilege escalation?

### A10: Server-Side Request Forgery (SSRF)
- [ ] **External URL fetch**: user-supplied URL → block internal metadata endpoint (169.254.169.254)?
- [ ] **URL allowlist**: whitelist of callable domains?
- [ ] **Redirect chasing**: external redirect → block internal IP?
- [ ] **Webhook**: validated for both directions (us → external configured URL, external → us)?

---

## STRIDE Threat Modeling

For the ticket's feature, identify threats across all six categories.

### S — Spoofing
- [ ] Possible to impersonate another user? (session theft, JWT forgery)
- [ ] Possible to impersonate a system/service? (DNS spoofing, MITM)
- [ ] Can an anonymous call appear authenticated?

### T — Tampering
- [ ] Can the client tamper with server-decided values? (price, permission)
- [ ] Tampering in transit? (HTTPS enforced, signatures)
- [ ] Verification when a DB row is tampered with directly? (audit log, checksum)

### R — Repudiation
- [ ] Evidence preserved for user actions? (audit log, signed receipt)
- [ ] Log tampering prevented? (append-only, external storage)

### I — Information Disclosure
- [ ] PII in error messages?
- [ ] User enumeration via response differences? (signup "already exists" vs "success")
- [ ] Debug info exposed? (stack trace, version)
- [ ] Information extractable via timing attack? (string comparison)

### D — Denial of Service
- [ ] Rate limit?
- [ ] Heavy queries blocked? (timeout, complexity limit)
- [ ] File upload size limit?
- [ ] regex DoS (ReDoS) possible?

### E — Elevation of Privilege
- [ ] Path from regular → admin?
- [ ] Access to another tenant's data?
- [ ] OS-level command execution possible?

---

## Output format

```markdown
## Security Audit — T-XXX

### Applicable domains
- OWASP: A01, A02, A07 (e.g. an auth ticket)
- STRIDE: S, I, E

### Findings
#### BLOCKER 1
- **OWASP**: A01 (Broken Access Control)
- **STRIDE**: E (Elevation of Privilege)
- **Location**: `apps/api/src/auth/middleware.py:45`
- **Issue**: the JWT `role` claim is mutable by the client (signature verification missing)
- **Evidence**: <code excerpt or PoC>
- **Required Action**: <concrete fix direction>

### WARNING 1 ...

### External-audit recommendation
- [ ] High launch impact (payment, PII at scale, multi-tenant) → separate external security audit required
```

## Anti-patterns

- "Internal tool, security doesn't matter" → applies to everything. Internal tools are the most often breached.
- "I heard this library is safe" → verify directly. Check CVEs.
- "Test environment, hardcoded is OK" → secrets always live in env. Someone always commits to prod.
- "All OWASP items pass" → STRIDE applies too. New threats are not in the standard.

## References
- `devos/prompts/claude/prd-intake-checklist.md` — required per-domain questions
- `devos/prompts/claude/review-adversarial.md` — shared severity format
- `devos/AI.md` Ticket Standard, `security_audit` field
- OWASP Top 10 (2021): https://owasp.org/Top10/
