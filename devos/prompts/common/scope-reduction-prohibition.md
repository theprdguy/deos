# Scope-Reduction Prohibition

> ticket goal/dod/context에 등장하면 **반드시 수정** 후 진입. 슬그머니 들어가는 어휘가 영구 기술부채로 굳는다.

## 금지어 표

| 금지어 / 표현 | 왜 금지 | 대체 행동 |
|--------------|---------|-----------|
| `v1`, `v2`, `v1으로 일단` | 미래 v2 약속이 지켜지지 않음 → 영구 v1 부채 | 한 번에 완전한 구현 또는 명시적 의존 ticket으로 분할 |
| `static for now`, `정적으로 일단` | "for now"는 영구로 굳음 | dynamic 구현 즉시 또는 ticket 분할 |
| `WIP placeholder`, `placeholder for now`, `자리표시자` | 결국 prod에 노출됨. 단, `fallback placeholder UI`, `데이터 placeholder`처럼 UX/데이터 명칭을 설명하는 정상 표현은 예외 | 실제 데이터 source 결정 후 ticket |
| `TODO`, `FIXME`, `XXX` | 코드/ticket 모두에서 누적 → 누구도 정리 안 함 | TODO 대신 별도 ticket 생성, comment에는 *근본 원인* 주석만 |
| `임시`, `나중에`, `추후` | 추후는 오지 않음 | 즉시 처리 또는 의존 ticket |
| `simplified version`, `간소화 버전` | "simplified"는 정의 없음 | 명확한 기능 set 약속 또는 분할 |
| `basic version`, `기본 버전` | "basic"의 기준이 사람마다 다름 | DOD에 구체 기능 항목 나열 |
| `minimal implementation`, `최소 구현` | "최소"가 사용자 가치를 만족하는지 미보장 | 사용자 가치 → 필수 기능 매핑 명시 |
| `quick fix`, `급한 대로` | 근본 원인 회피 | systematic-debugging skill 호출 |
| `will be wired later`, `나중에 연결` | wiring 안 된 코드는 dead code | wiring까지 한 ticket에 |
| `skip for now`, `생략` | 생략된 케이스가 prod에서 첫 발견됨 | DOD에 명시적 포함 또는 N/A 사유 |
| `future enhancement`, `향후 개선` | 백로그 무한 누적 | 약속하지 않음. 필요 시 별도 ticket |
| `hardcoded for now` | hardcode가 영구로 남음 | config/env 즉시 분리 |

## 검사 시점

1. **PRD 분해 시** — CLAUDE1이 ticket 작성 직전 자가 검사
2. **Approval 직전** — devos/plans/pending/ 저장 시 자동 grep 권장:
   ```bash
   SCOPE_REDUCTION_PATTERN='(^|[^[:alnum:]_])(v1[[:space:]]*로|v1[[:space:]]*으로[[:space:]]*일단|TODO([[:space:]]*:[[:space:]]*implement)?|FIXME|XXX|WIP[[:space:]-]+placeholder|placeholder[[:space:]-]+for[[:space:]-]+now|stub[[:space:]-]+for[[:space:]-]+now|static[[:space:]-]+for[[:space:]-]+now|나중에|임시|추후|simplified([[:space:]-]+version)?|basic[[:space:]-]+version|minimal[[:space:]-]+implementation|quick[[:space:]-]+fix|wired[[:space:]-]+later|skip[[:space:]-]+for[[:space:]-]+now|future[[:space:]-]+enhancement|hardcoded[[:space:]-]+for[[:space:]-]+now)([^[:alnum:]_]|$)'
   grep -E -i "$SCOPE_REDUCTION_PATTERN" devos/plans/pending/*.yaml
   ```
   회귀 fixture는 `bash scripts/check-ticket-scope.sh --self-test-scope-reduction`으로 검증한다.
3. **PR review 시** — adversarial review에서 BLOCKER 분류

## 예외 조항 (좁게)

다음 3가지에 한해 금지어 사용 허용:
1. **Locked Decision 명시적 분할**: `D-XX`로 잠긴 결정에 따라 의도적으로 단계 분할 — ticket에 `per D-XX` 참조 필수
2. **Spike/Research ticket**: 학습 목적 ticket(`tdd: skip`, 결과물=문서)에서 `spike` 표기 — 결과는 production code 아닌 ADR
3. **External constraint**: 외부 API/규제로 즉시 구현 불가 — context에 사유 + 차단 ticket ID 명시

이 3가지 외엔 무조건 수정.

## 참조

- `devos/AI.md` Ticket Standard
- `devos/ETHOS.md` Boil the Lake
- `devos/prompts/claude/decompose-prd.md` — Step 0에서 이 파일 자가 검사
