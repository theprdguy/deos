# PRD Intake Checklist (비개발자 보호)

> CLAUDE1이 PRD를 받으면 **decompose 전에** 이 파일을 따라 도메인별 누락 항목을 사용자에게 강제 질문한다. happy path만 적힌 PRD를 그대로 ticket으로 분해하지 않는다.

## 운용 원칙

1. PRD에서 도메인 키워드를 식별 → 해당 섹션의 항목을 모두 사용자에게 질문
2. "PRD에 없으니 안 만들었어요" 패턴은 **Iron Law 위반**으로 간주
3. 사용자가 "필요 없음"이라고 답한 항목은 PRD에 *명시적 N/A 사유*로 기록 (없는 게 아니라 의도적 제외)
4. 답변 후 사용자 응답을 PRD 또는 `devos/questions/QUEUE.md`에 기록 → ticket context의 근거가 됨

---

## A. Authentication / 인증 도메인

키워드: 로그인, 가입, 회원, 인증, OAuth, 비밀번호, 세션

### 강제 질문
- [ ] **Login 실패 처리**: 잘못된 credentials → 어떤 메시지? lockout 정책?
- [ ] **Lockout**: N회 실패 시 잠금? 잠금 시간? 해제 방법?
- [ ] **Password reset**: 이메일 링크? SMS? 만료 시간?
- [ ] **2FA / MFA**: 도입? optional/mandatory? backup code?
- [ ] **Session expiry**: idle timeout? absolute timeout? "remember me"?
- [ ] **Concurrent session**: 같은 계정 동시 로그인 허용? 강제 로그아웃?
- [ ] **Logout**: 단일 디바이스? all-devices? token revoke?
- [ ] **Account deletion**: 즉시 삭제? soft delete + grace period? 데이터 처리?
- [ ] **OAuth / Social login**: provider? scope? 기존 계정 merge 정책?
- [ ] **Audit log**: 로그인/실패/lockout 기록? 보존 기간?

---

## B. Payment / 결제 도메인

키워드: 결제, 청구, 환불, 구독, billing, payment, subscription

### 강제 질문
- [ ] **Success path**: 어떤 PG? 카드/계좌이체/간편결제 어디까지?
- [ ] **Failure**: 카드 거절, 잔액 부족, 네트워크 타임아웃 각각 처리?
- [ ] **Refund**: 부분/전액? 시간 제한? 자동/수동?
- [ ] **Dispute / chargeback**: 알림 흐름? 증빙 수집?
- [ ] **Duplicate prevention**: idempotency key? 중복 결제 감지?
- [ ] **Subscription**: trial → paid 전환? 갱신 실패? 다운그레이드?
- [ ] **Tax / VAT**: 국가별 세율? 인보이스?
- [ ] **PCI scope**: 카드 정보 직접 저장? PG 토큰만 저장?
- [ ] **Currency**: 다중 통화? 환율 timing?
- [ ] **Audit log**: 모든 결제/환불/실패 기록? 영구 보존?

---

## C. Data Input / 입력 검증 도메인

키워드: 폼, form, 입력, validation, 등록, 작성

### 강제 질문
- [ ] **Length**: min/max length? bytes vs characters?
- [ ] **Charset**: 한글/이모지 허용? 특수문자?
- [ ] **Format**: 이메일/전화/URL 정규식 기준?
- [ ] **SQL injection**: ORM/parameterized query 강제? raw query 금지?
- [ ] **XSS**: 출력 시 escape? markdown/HTML 허용 범위?
- [ ] **Rate limit**: 같은 사용자 N회/분?
- [ ] **Server-side**: 클라이언트 검증 외 서버 검증 강제?
- [ ] **Error message**: 사용자 친화적 vs 디버그용 분리?

---

## D. File Upload / 파일 업로드 도메인

키워드: 업로드, upload, 파일, 이미지, 첨부

### 강제 질문
- [ ] **Size limit**: 파일별/요청별/사용자별?
- [ ] **Type / MIME**: 화이트리스트? magic byte 검증?
- [ ] **Malware scan**: ClamAV? 외부 서비스? 동기/비동기?
- [ ] **Path traversal**: 사용자 입력 파일명 sanitize?
- [ ] **Storage**: 로컬/S3/Cloud? public vs presigned?
- [ ] **Image processing**: 리사이즈? EXIF strip? format 변환?
- [ ] **Quota**: 사용자당 총 용량 한도?
- [ ] **Deletion**: 사용자 요청 즉시? GDPR 30일?

---

## E. External API / 외부 API 호출 도메인

키워드: API, 연동, integration, webhook, 외부 서비스

### 강제 질문
- [ ] **Rate limit**: 외부 서비스 제한? 우리 측 backoff?
- [ ] **Timeout**: connect/read 별도?
- [ ] **Circuit breaker**: 연속 실패 시 차단? half-open 복구?
- [ ] **Retry policy**: idempotent만? exponential backoff?
- [ ] **Webhook security**: signature 검증? replay 방지?
- [ ] **Secret rotation**: API key 변경 절차?
- [ ] **Error mapping**: 외부 에러 → 우리 에러 변환?
- [ ] **Audit**: 모든 외부 호출 기록? PII 제외?

---

## F. Permissions / 권한 도메인

키워드: 권한, role, permission, admin, 관리자, 접근

### 강제 질문
- [ ] **Role 정의**: 역할 종류? 역할 간 hierarchy?
- [ ] **Permission granularity**: action 레벨? resource 레벨?
- [ ] **IDOR 방지**: 다른 사용자 데이터 접근 검증?
- [ ] **Privilege escalation**: 일반 → admin 승급 절차?
- [ ] **Multi-tenant**: tenant 격리 어떻게?
- [ ] **Audit**: 권한 변경 기록?

---

## G. 공통 (모든 PRD)

키워드와 무관하게 모든 PRD에서 확인.

### 강제 질문
- [ ] **Empty state**: 데이터 0개일 때 UI/메시지?
- [ ] **Loading state**: 로딩 중 표시?
- [ ] **Error state**: 시스템 에러 시 사용자에게 무엇을?
- [ ] **i18n**: 다국어? locale별 fallback?
- [ ] **접근성 (a11y)**: 스크린리더? 키보드 navigation? color contrast?
- [ ] **모바일**: 반응형? touch target 크기?
- [ ] **오프라인**: 네트워크 끊김 시 동작?
- [ ] **감사 로그**: 누가/언제/무엇을 변경?
- [ ] **개인정보 (PII)**: 수집/저장/삭제 정책?
- [ ] **Rate limit (전역)**: DDoS/abuse 방지?

---

## 사용 절차 (CLAUDE1)

1. PRD를 받으면 키워드 스캔 → 해당 도메인 섹션 식별
2. 각 항목을 사용자에게 한 번에 5개 이하로 묶어 질문 (피로 방지)
3. 사용자 답변을 PRD 부록 또는 `devos/questions/QUEUE.md`에 기록
4. 답변 완료 후 ticket 분해 진행
5. 각 ticket의 dod에 해당 항목이 success-case + error-case 쌍으로 들어가는지 확인

## 한계 명시

- 새로운 도메인(AI 모델 탈취, prompt injection)은 표준 OWASP/STRIDE에 없으면 누락
- "내부 도구라 보안 안 중요"라는 사용자 잘못된 판단은 못 잡음 — 답변 자체는 사용자 책임
- 출시 임팩트 큰 영역(payment 등)은 외부 보안 감사 별도 의뢰 필수

## 참조

- `devos/prompts/claude/security-audit.md` — OWASP/STRIDE 상세 (Week 2)
- `devos/prompts/claude/decompose-prd.md` — Step 0에서 이 파일 호출
- `devos/ETHOS.md` 비개발자 보호 원칙
