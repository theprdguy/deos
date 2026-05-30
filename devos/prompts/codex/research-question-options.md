# CODEX — Question Queue 옵션 사전조사 (Phase 1)

> builder / CODEX subprocess 가 막혀 `devos/questions/QUEUE.md` 에 질문 등록 시,
> CLAUDE1 main 이 옵션 사전조사를 CODEX 에 위임하는 protocol.

## 호출 시점

- `devos/questions/QUEUE.md` 에 신규 Q-XXX 추가됨
- 옵션이 명확하지 않음 (Options 섹션이 빈 칸 또는 1-2개만)
- CLAUDE1 이 답변 작성 전에 추가 옵션 / 트레이드오프 / 외부 사례 필요

## 호출 방식

```bash
codex exec "$(cat <<'EOF'
You are researching options for a development decision. Return facts and known
patterns — do NOT recommend a final choice; the human user decides.

## Question context
{Q-XXX 본문 — 배경 + 현재 막힘 + 후보 옵션}

## Research scope
1. 다른 OSS 프로젝트에서 같은 문제를 어떻게 해결했나? (GitHub search, web search)
2. 각 옵션의 trade-off — 명시적 비교표 (성능/유지보수/이전 비용/벤더 락인 등)
3. 알려진 안티 패턴 / pitfalls
4. 관련 RFC / spec / 공식 권장 (있다면)

## Output format
```yaml
question_id: Q-XXX
research_date: 2026-MM-DD
options:
  - name: <option 1>
    description: <text>
    pros: [<list>]
    cons: [<list>]
    real_world_users: [<project/library names>]
    references: [<url>]
  - name: <option 2>
    ...
common_pitfalls: [<text>]
spec_or_rfc: <text or "none">
unknown: [<list of unanswered sub-questions>]
```

Quote sources; flag speculation explicitly.
EOF
)" --output-schema /tmp/codex-options-schema.json -o /tmp/codex-options-result.json
```

## CLAUDE1 의 결과 통합

CODEX 결과 → Q-XXX 의 Options 섹션 보강:
- 기존 옵션과 중복 제거
- Recommendation 은 CLAUDE1 이 직접 작성 (CODEX 못 함)
- Default 는 사용자 또는 CLAUDE1 결정

## 사용 시점

- Q-XXX 가 **blocking** 일 때만 적극 — non-blocking 은 builder/CODEX 가 Default 로 진행
- Q-XXX 가 architectural / 비개발자 보호 영역일 때 (ETHOS 관련) → 의무

## 비용

- CODEX 호출 1회 ~10-30K input + 1-3K output. C0 (OpenAI 측 청구).
- 절감: CLAUDE1 (Opus xhigh) 의 web search + 비교 시간 ↓.

## Anti-patterns

- CODEX 가 옵션 추천하는 것 그대로 채택 → 결정 위임 (CLAUDE1 역할 위반)
- 옵션 사전조사 없이 CLAUDE1 가 답변 작성 → 누락 옵션 위험
