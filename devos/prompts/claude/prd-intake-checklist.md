# PRD Intake Checklist (non-developer protection)

> When CLAUDE1 receives a PRD, **before decomposing**, follow this file to require per-domain questions to the user about missing items. Do not decompose a happy-path-only PRD straight into tickets.

## Operating principles

1. Identify domain keywords in the PRD → ask the user every item in the relevant section
2. The "we didn't build it because the PRD didn't mention it" pattern is treated as an **Iron Law violation**
3. For items the user answers as "not needed", record them in the PRD with an *explicit N/A reason* (intentional exclusion, not absence)
4. Record user answers in the PRD or in `devos/questions/QUEUE.md` → these become the basis for the ticket context

---

## A. Authentication domain

Keywords: login, sign up, member, auth, OAuth, password, session

### Required questions
- [ ] **Login failure handling**: wrong credentials → what message? lockout policy?
- [ ] **Lockout**: lock after N failures? lock duration? unlock method?
- [ ] **Password reset**: email link? SMS? expiration time?
- [ ] **2FA / MFA**: introduce it? optional/mandatory? backup codes?
- [ ] **Session expiry**: idle timeout? absolute timeout? "remember me"?
- [ ] **Concurrent session**: allow same account to be signed in simultaneously? force logout?
- [ ] **Logout**: single device? all-devices? token revoke?
- [ ] **Account deletion**: immediate delete? soft delete + grace period? data handling?
- [ ] **OAuth / Social login**: which provider? scope? merge policy with existing accounts?
- [ ] **Audit log**: record login/failure/lockout? retention period?

---

## B. Payment domain

Keywords: payment, billing, refund, subscription

### Required questions
- [ ] **Success path**: which PG? card / bank transfer / easy-pay — how far?
- [ ] **Failure**: card declined, insufficient balance, network timeout — handle each?
- [ ] **Refund**: partial/full? time limit? automatic/manual?
- [ ] **Dispute / chargeback**: notification flow? evidence collection?
- [ ] **Duplicate prevention**: idempotency key? duplicate-charge detection?
- [ ] **Subscription**: trial → paid conversion? renewal failure? downgrade?
- [ ] **Tax / VAT**: per-country tax rate? invoice?
- [ ] **PCI scope**: storing card info directly? store only PG token?
- [ ] **Currency**: multi-currency? exchange rate timing?
- [ ] **Audit log**: record every payment/refund/failure? permanent retention?

---

## C. Data Input / input validation domain

Keywords: form, input, validation, registration, submission

### Required questions
- [ ] **Length**: min/max length? bytes vs characters?
- [ ] **Charset**: allow Korean / emoji? special characters?
- [ ] **Format**: regex baseline for email / phone / URL?
- [ ] **SQL injection**: enforce ORM/parameterized query? ban raw query?
- [ ] **XSS**: escape on output? scope of allowed markdown/HTML?
- [ ] **Rate limit**: same user N times/min?
- [ ] **Server-side**: enforce server validation in addition to client validation?
- [ ] **Error message**: separate user-friendly vs debug messages?

---

## D. File Upload domain

Keywords: upload, file, image, attachment

### Required questions
- [ ] **Size limit**: per-file / per-request / per-user?
- [ ] **Type / MIME**: whitelist? magic-byte verification?
- [ ] **Malware scan**: ClamAV? external service? sync/async?
- [ ] **Path traversal**: sanitize user-supplied filenames?
- [ ] **Storage**: local / S3 / cloud? public vs presigned?
- [ ] **Image processing**: resize? EXIF strip? format conversion?
- [ ] **Quota**: total per-user storage cap?
- [ ] **Deletion**: immediate on user request? GDPR 30 days?

---

## E. External API domain

Keywords: API, integration, webhook, external service

### Required questions
- [ ] **Rate limit**: external service limit? our-side backoff?
- [ ] **Timeout**: separate connect/read?
- [ ] **Circuit breaker**: cut off on consecutive failures? half-open recovery?
- [ ] **Retry policy**: idempotent only? exponential backoff?
- [ ] **Webhook security**: signature verification? replay protection?
- [ ] **Secret rotation**: API key rotation procedure?
- [ ] **Error mapping**: external errors → our errors?
- [ ] **Audit**: record every external call? excluding PII?

---

## F. Permissions domain

Keywords: permission, role, admin, access

### Required questions
- [ ] **Role definition**: what roles? hierarchy among roles?
- [ ] **Permission granularity**: action level? resource level?
- [ ] **IDOR prevention**: verify access to other users' data?
- [ ] **Privilege escalation**: procedure for general → admin promotion?
- [ ] **Multi-tenant**: how is tenant isolation enforced?
- [ ] **Audit**: record permission changes?

---

## G. Common (every PRD)

Verify on every PRD regardless of keywords.

### Required questions
- [ ] **Empty state**: UI/message when there are zero records?
- [ ] **Loading state**: indicator while loading?
- [ ] **Error state**: what does the user see on a system error?
- [ ] **i18n**: multi-language? per-locale fallback?
- [ ] **Accessibility (a11y)**: screen reader? keyboard navigation? color contrast?
- [ ] **Mobile**: responsive? touch target size?
- [ ] **Offline**: behavior when network drops?
- [ ] **Audit log**: who/when/what changed?
- [ ] **Personal data (PII)**: collection / storage / deletion policy?
- [ ] **Rate limit (global)**: DDoS / abuse prevention?

---

## Procedure (CLAUDE1)

1. On receiving a PRD, scan for keywords → identify the relevant domain sections
2. Ask each item to the user, batched at 5 or fewer at a time (avoid fatigue)
3. Record user answers in the PRD appendix or in `devos/questions/QUEUE.md`
4. After all answers are in, proceed to ticket decomposition
5. Confirm each ticket's dod includes the relevant items as a success-case + error-case pair

## Stated limitations

- New domains (AI model theft, prompt injection) are missed unless covered by standard OWASP/STRIDE
- A user's mistaken judgment ("internal tool, security doesn't matter") cannot be caught here — the answer itself is the user's responsibility
- High launch-impact areas (payment, etc.) require a separate external security audit

## References

- `devos/prompts/claude/security-audit.md` — OWASP/STRIDE detail (Week 2)
- `devos/prompts/claude/decompose-prd.md` — Step 0 invokes this file
- `devos/ETHOS.md` non-developer protection principles
