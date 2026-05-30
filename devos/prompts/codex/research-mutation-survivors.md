# CODEX — Mutation 생존자 1차 분류 (Phase 1)

> mutation test 실행 후 (보통 야간 `at 02:00`), 생존한 mutant 들을 카테고리별로
> 분류하는 작업을 CODEX 에 위임. CLAUDE1 은 final 분류 + follow-up ticket 작성만.

## 호출 시점

- `devos/logs/mutation/{YYYY-MM-DD}.md` 작성 후 (mutation test 종료 직후 또는 다음 세션 시작)
- 생존자 수가 5건 이상일 때 적극 위임 (작으면 CLAUDE1 직접)

## 호출 방식

```bash
codex exec "$(cat <<'EOF'
You are classifying mutation test survivors. For each survivor, determine if it
represents (A) a real test gap (boilable lake), (B) an equivalent mutant (no
behavioral change), or (C) trivial/cosmetic. Return structured classification.

## Mutation log
{devos/logs/mutation/{date}.md 본문 inline}

## Classification rubric
- **gap**: mutant changes behavior in a way that a correct test should catch but
  no existing test does. Highest priority — follow-up test needed.
- **equivalent**: mutant produces logically identical behavior (rare but real —
  e.g. `<` vs `<=` on a boundary that's never exercised).
- **cosmetic**: trivial change (whitespace, logging text, comment). Low priority.

## Output format
```yaml
date: 2026-MM-DD
total_survivors: <N>
classification:
  - mutant_id: <id from log>
    file: <path>
    line: <int>
    operator: <mutation operator name>
    original: <code>
    mutated: <code>
    category: gap | equivalent | cosmetic
    reasoning: <1-2 sentence>
    suggested_test: <if gap — 1 line test signature like "test_X_with_boundary_Y">
summary:
  gaps: <N>
  equivalents: <N>
  cosmetics: <N>
followup_ticket_drafts:
  - title: <draft>
    files: [<list>]
    reasoning: <why this gap matters>
```

Be conservative — flag uncertain as "gap" rather than dismissing.
EOF
)" --output-schema /tmp/codex-mutation-schema.json -o /tmp/codex-mutation-result.json
```

## CLAUDE1 의 결과 통합

CODEX 결과 → 다음 세션에 CLAUDE1 이 처리:
1. **gap 항목 검토** — 각 mutant 가 정말 test 누락인지 확인 (CODEX 가 over-classify 가능)
2. **equivalent 항목 sanity check** — 정말 동작 동일한가? 의심 → gap 로 재분류
3. **follow-up ticket 작성** — gap 1건당 또는 같은 파일 묶음 1건당 ticket
4. **mutation 로그 finalize** — classification 추가 + 다음 회 baseline

## 사용 시점

- 매 mutation test 후 1회 (자동 호출 가능 — 야간 mutation 직후 codex exec 트리거)
- 생존자 분석을 CLAUDE1 이 직접 하면 ~30-60분 / CODEX 위임 후 검토면 ~10분

## 비용

- mutation log 길이 의존. 평균 ~30-50K input + 5-10K output.
- C0 (OpenAI 측). C1 (CLAUDE1) mutation 분석 시간 ↓.

## Anti-patterns

- CODEX 분류를 그대로 채택 → equivalent mis-classify 시 진짜 gap 누락
- gap → follow-up ticket 작성 미루기 → mutation test 의 가치 소실
- 같은 파일 내 다수 gap 을 ticket 하나로 묶지 않고 ticket N개 생성 → archive 비대화

## 참조

- `.claude/CLAUDE.md` § MUTATION TEST PROPOSAL PROTOCOL
- `devos/AI.md` § Testing Policy § 6 Mutation Testing
