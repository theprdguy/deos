# Goal-Backward Verification

> DOD 검증이 input→output 단위 통과만 확인하면, 유저 journey의 끊김을 놓친다.
> 이 prompt는 **goal에서 역추적**해서 "유저가 실제로 도달 가능한가"를 검증한다.

## 핵심 원칙

```
Plan completeness ≠ Goal achievement
```

- 모든 ticket dod가 통과해도 goal이 실현 안 될 수 있다.
- 검증자는 dod 체크가 아니라 **goal에서 역으로 추적**한다.

## 4단계 역추적

### Phase 1 — Goal 명문화
- ticket goal을 한 문장으로 다시 쓴다 (사용자 관찰 가능 형태로):
  - 나쁨: "Authentication 시스템 구현"
  - 좋음: "신규 유저가 이메일+비밀번호로 가입 후 즉시 보호된 /dashboard 라우트에 도달 가능"

### Phase 2 — Required Truths 추출
goal이 참이 되려면 어떤 사실들이 동시에 참이어야 하는가? 4~8개 정도로 분해.

예 (위 auth goal):
1. POST /auth/signup 엔드포인트 존재 + 200 + 유저 레코드 생성
2. 유저 레코드가 비밀번호를 hash로 저장
3. POST /auth/login에서 동일 credentials → 200 + JWT
4. JWT가 유효 기간 내 유효
5. 보호된 라우트가 JWT 검증 미들웨어 통과
6. /dashboard 라우트가 보호 미들웨어 사용
7. 유저가 갑자기 로그아웃되지 않음 (session 안정성)

### Phase 3 — Artifacts 매핑
각 truth를 코드/테스트의 구체 artifact로 매핑.

| Truth | Code artifact | Test artifact |
|-------|---------------|---------------|
| 1 | `apps/api/src/auth/signup.py:23` | `tests/auth/test_signup.py::test_signup_success` |
| 2 | `apps/api/src/auth/signup.py:31` (bcrypt 호출) | `tests/auth/test_signup.py::test_password_hashed` |
| 3 | `apps/api/src/auth/login.py:18` | `tests/auth/test_login.py::test_login_success` |
| ... | ... | ... |

매핑 안 되는 truth = **GAP**.

### Phase 4 — Wiring 검증
artifact 존재만으로 부족. 실제 호출 경로(wiring)가 연결됐는지 확인.

- 미들웨어가 라우터에 등록됐는가? (`app.use(authMiddleware)`)
- /dashboard 라우트가 *실제로* 미들웨어를 거치는가? (라우트 정의 확인)
- 환경변수(JWT_SECRET 등)가 실제로 주입되는가?

미연결 wiring = **BLOCKER**.

## 출력 형식

```markdown
## Goal-Backward Verification — T-XXX

### Goal (관찰 가능 형태)
<한 문장>

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
- Truth #N: <왜 매핑 안 됐는지> → BLOCKER

### Wiring failures
- <어디서 끊겼는지> → BLOCKER

### Verdict
- VERIFIED: M / N truths
- GAPS: K
- WIRING FAILURES: J
- Recommendation: BLOCK | MERGE OK
```

## SUMMARY 불신 원칙

빌더가 작성한 SUMMARY/PR description의 "구현했다", "테스트 통과"는 **가정**. 다음 형태만 증거로 인정:
- 코드 파일 + 라인 직접 read
- 테스트 실행 결과 (pass/fail 출력)
- 실제 HTTP 호출 결과 (curl 또는 통합 테스트 결과)

## Anti-patterns
- "단위 테스트 다 통과했으니 OK" → unit pass ≠ user journey complete
- "DOD 100% 충족" → DOD가 truth set을 다 커버한다는 보장 없음
- "비슷한 패턴은 잘 작동했으니" → 이번 wiring을 직접 확인

## 적용 시점
- `cross_model: true` ticket
- 인증/결제/권한 critical path
- "이 PR은 user-facing 기능이다"라고 판단되는 모든 PR
- adversarial review의 Phase 2로 호출

## 참조
- `devos/prompts/claude/review-adversarial.md`
- `devos/ETHOS.md` Iron Law #3
