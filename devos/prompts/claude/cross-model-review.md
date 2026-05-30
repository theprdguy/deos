# Cross-Model Review

> Anthropic 계열 모델만 검토하면 모델 공통 blindspot(timing attack, race condition, 일부 architecture preference)을 통과시킬 수 있다.
> 이 prompt는 CODEX(OpenAI 계열)에게 동일 산출물의 독립 검토를 의뢰한다.

## 적용 조건

`ticket.cross_model: true`인 경우 의무. 다음 ticket은 자동 권장:
- 인증 (login/signup/session/token)
- 결제 (payment/subscription/refund)
- 권한 (RBAC/IDOR/multi-tenant)
- 데이터 무결성 (concurrent write, transaction)
- 보안 critical (crypto, signing, secret 처리)

## 의뢰 절차 (CLAUDE1)

### Step 1: 산출물 패키지
CODEX에게 보낼 컨텍스트 묶음:
1. ticket 본문 (goal, dod, constraints)
2. PR diff 또는 변경된 파일 경로 리스트
3. 핵심 파일 본문 (CODEX는 fresh session — 직접 읽도록 경로 제공)
4. CLAUDE 측 adversarial review 결과 (있으면 — 단, **결론은 가리지 않음**. 발견은 공유, 평가는 독립)

### Step 2: CODEX에게 보낼 prompt 템플릿

```markdown
# Independent Cross-Model Review — T-XXX

You are reviewing a deliverable produced by Claude. Your job is **independent second opinion**.
Do NOT defer to Claude's review. Find what Claude missed.

## Context
<ticket goal + dod + constraints 본문>

## Files changed
<git diff 또는 file list>

## Focus areas (이 ticket 도메인 기반)
<auth/payment/permissions 등 도메인별 focus>

## Specific blindspots to probe (Anthropic 계열 일관 약점)
- Timing attacks (constant-time 비교 누락)
- Race conditions (DB transaction, mutex)
- Off-by-one in pagination/offset
- TOCTOU (Time-of-check to time-of-use)
- Privilege escalation paths (IDOR, broken access control)
- Error message info leakage
- Replay attack (nonce/timestamp 검증)
- Logging that leaks PII

## Output format
1. BLOCKER (N개): <위치 + 무엇이 위험한지 + 구체 예시>
2. WARNING (M개): <follow-up 가치 있는 issue>
3. AGREE WITH CLAUDE (M개): Claude review가 잡은 것 중 동의하는 것 (참고용)
4. NEW FINDINGS (Claude가 안 잡은 것): K개
```

### Step 3: 결과 통합
CODEX 회신 후:
- BLOCKER 합산: Claude 측 BLOCKER ∪ CODEX 측 BLOCKER
- 양쪽 BLOCKER 0건이어야 머지 권장
- DISAGREEMENT (한쪽만 BLOCKER로 분류) → 사용자에게 옵션 제시:
  - A) BLOCKER로 결정 (보수적)
  - B) WARNING으로 강등 (사유 + ADR 작성)
  - C) 추가 분석 (다른 도구/사람)

### Step 4: 기록
결과를 ticket의 session log에 추가:
- `devos/logs/{date}-claude1.md` 또는
- `devos/logs/cross-model/{ticket-id}.md` (긴 경우 별도)

## 운용 주의

- **기록 분리**: CODEX의 결론을 보지 않은 상태로 Claude review 먼저 완료. 그 후 CODEX 의뢰. → 상호 영향 차단.
- **Codex unavailable**: CODEX 응답 불가 시 ticket을 BLOCKED로 마킹, `devos/questions/QUEUE.md`에 옵션 제시.
- **비용**: Cross-model review는 모든 ticket 적용 시 비용 폭증. critical path만 적용.

## Anti-patterns

- "CODEX에게 Claude review 결론 보여주고 동의 요청" → confirmation bias. 독립 의뢰 원칙 위반.
- "CODEX의 BLOCKER를 WARNING으로 임의 강등" → severity는 사실 기반. 강등은 명시적 사유 + 사용자 승인.
- "CODEX와 Claude 결과 같으니 검증된 것" → 같은 결론도 둘 다 같은 blindspot일 수 있음. 독립적 발견 N개에 가중치.

## 참조
- `devos/prompts/claude/review-adversarial.md` — Phase별 통합
- `devos/ETHOS.md` Iron Law #4
- `devos/AI.md` Ticket Standard `cross_model` 필드
