# OS3 — User Guide

> 사용자/LLM 모두 `bin/os3` 단일 entry point 사용. `bin/osn` 은 호환 alias. RCE 표면 0 — Make 인터페이스는 폐기됨 (T-OSN-W7-OSN-CLI-02).

---

## 빠른 시작

```bash
# ticket 리스트 확인
bin/os3 queue

# 다음 처리할 ticket 자동 선택
bin/os3 dispatch-next

# 특정 ticket 처리
bin/os3 dispatch T-OSN-W7-OSN-CLI-04

# 작업 검증
T=T-OSN-W7-OSN-CLI-04 AGENT_NAME=BUILDER bin/os3 pr-check

# 상태 확인
bin/os3 status
```

---

## Subcommand 목록

### Ticket 관리
| Command | 동작 |
|---|---|
| `bin/os3 queue` | active ticket 리스트 + tdd/owner 필드 출력 |
| `bin/os3 status` | 전체 ticket 카운트 + milestone 진행도 |
| `bin/os3 pilot-status [--strict]` | OS3 E2E pilot readiness, policy artifacts, active pilot ticket, remaining evidence 출력 |
| `bin/os3 pending` | pending plan 리스트 |
| `bin/os3 lookup <ticket-id>` | ticket YAML 본문 조회 (QUEUE + ARCHIVE 검색) |
| `bin/os3 owner <ticket-id>` | ticket owner 출력 (BUILDER/CODEX/CLAUDE1) |
| `bin/os3 archive` | done 티켓을 ARCHIVE.yaml 로 이관 |
| `bin/os3 logs` | 최근 session log 디렉토리 |

### Dispatch
| Command | 동작 |
|---|---|
| `bin/os3 dispatch <ticket-id>` | 단일 ticket dispatch (owner-aware routing) |
| `bin/os3 dispatch-all` | 모든 todo ticket dispatch |
| `bin/os3 dispatch-next` | priority/deps 따라 다음 처리 가능 ticket 자동 선택 |
| `bin/os3 dispatch-codex <ticket-id>` | CODEX-owned ticket subprocess 호출 |
| `bin/os3 cross-model-codex <ticket-id> --reason="..."` | b' adaptive trigger (reviewer.uncertainty=true 시) |

### 검증 / 게이트
| Command | 동작 |
|---|---|
| `bin/os3 verify <ticket-id>` | ticket DOD verify 명령 실행 |
| `T=<ticket-id> AGENT_NAME=<agent> bin/os3 pr-check` | 5 gate 일괄 실행 (scan-secrets / contract-sync / ticket-scope / session-log / tdd-first-commit) |
| `bin/os3 user-review <ticket-id>` | 사용자 명시적 review 마킹 |
| `bin/os3 resume <ticket-id>` | blocked → todo 재시도 |

### 상태 변경
| Command | 동작 |
|---|---|
| `bin/os3 set-status <ticket-id> <status> "<reason>"` | ticket status 전환 (todo / doing / done / blocked / parked) |
| `bin/os3 approve [plan-id]` | pending plan → approved |
| `bin/os3 reject "<reason>" [plan-id]` | pending plan → rejected |

### Gemini 시각 리뷰 (nested subcommand)
| Command | 동작 |
|---|---|
| `bin/os3 gemini pending` | 시각 리뷰 대기 ticket 리스트 |
| `bin/os3 gemini next` | 가장 오래된 pending 1 개 자동 선택 + handoff 안내 |
| `bin/os3 gemini ingest` | stdin 으로 응답 paste (e.g. `cat response.txt \| bin/os3 gemini ingest`) |
| `bin/os3 gemini status` | quota / 일일 호출 통계 |
| `bin/os3 gemini dispatch <ticket-id>` | Plan A 자동 dispatch (Gemini API 직접 호출) |
| `bin/os3 gemini smoke` | 환경 smoke test |

---

## 자주 쓰는 워크플로

### 새 ticket 처리 (LLM 자연어 → 명령)
| 자연어 | 명령 |
|---|---|
| "ticket 리스트 보여줘" | `bin/os3 queue` |
| "다음 거 처리" | `bin/os3 dispatch-next` |
| "T-XXX 검증" | `bin/os3 verify T-XXX` |
| "Gemini 대기 있어?" | `bin/os3 gemini pending` |
| "그거 처리" | `bin/os3 gemini next` |

### 일반 dispatch flow

```
1. bin/os3 dispatch-next         # 다음 ticket 선택 + dispatch
2. (builder 작업 자동 진행)
3. T=T-XXX AGENT_NAME=BUILDER bin/os3 pr-check   # 게이트 검증
4. (reviewer + security agent 호출)
5. bin/os3 set-status T-XXX done "completed"
6. bin/os3 archive               # done → ARCHIVE.yaml
```

### Plan B (수동 Gemini 시각 리뷰)

Plan A (`bin/os3 gemini dispatch`) 가 quota / network / OAuth 실패 시 자동으로 pending flag 생성. 사용자 흐름:

```
1. bin/os3 gemini pending        # 대기 확인
2. bin/os3 gemini next           # 안내 출력 — bash <script-path> 명령 받음
3. bash .cache/gemini-handoff-T-XXX.sh   # 외부 gemini CLI 실행
4. (응답 복사)
5. bin/os3 gemini ingest         # 응답 paste (stdin)
```

---

## 보안 모델

### 안전 표면 (RCE 차단 보장)
- `bin/os3 <subcommand>` — argparse 기반 sys.argv 만 평가, shell evaluation 0
- `python -m server.<documented-module> <documented-subcommand>` — server/__main__.py / server/cli.py / server/gemini_handoff.py / server/gemini_dispatcher.py 의 documented subcommand

### Internal API (사용자 책임)
- `server._function`, `server.module._private` (underscore prefix) — dispatcher / orchestrator 만 호출
- 사용자가 reflection 으로 호출 시 OS3 threat model 외

### OS/shell 영역 (OS3 책임 외)
- `bash -c '...'`, 사용자 셸 직접 입력
- `PYTHONPATH` / `PYTHONHOME` 등 env hijack — Python invocation 본질

자세한 threat model: `devos/docs/THREAT_MODEL.md` (T-OSN-W7-OSN-CLI-04 신설 예정).

---

## 환경 변수

| Variable | 용도 |
|---|---|
| `T=<ticket-id>` | pr-check / 일부 gate 의 ticket id 전달 (env channel) |
| `AGENT_NAME=<BUILDER\|CODEX\|CLAUDE1>` | session log 영역 결정 |
| `OS3_PROJECT_ROOT` | 프로젝트 root 경로 (자동 감지 — 일반적으로 미설정 OK) |

---

## Migration from Make (history)

T-OSN-W7-GEMINI-02 R1~R7 (5 라운드 Make var injection RCE 추격) 결과 Makefile 인터페이스 통째 폐기. OS3 primary CLI 는 `bin/os3`:
- T-OSN-W7-OSN-CLI-01: `bin/osn` + `server/cli.py` 신설, 이후 OS3에서 `bin/os3` primary alias 추가
- T-OSN-W7-OSN-CLI-02: Makefile 폐기 + 회귀 가드
- T-OSN-W7-OSN-CLI-03: Documentation 일괄 갱신 (이 파일 포함)
- T-OSN-W7-OSN-CLI-04: Threat model 명문화

| 옛 명령 | 신 명령 |
|---|---|
| `make queue` | `bin/os3 queue` |
| `bin/os3 dispatch T=T-XXX` | `bin/os3 dispatch T-XXX` |
| `make verify T=T-XXX` | `bin/os3 verify T-XXX` |
| `bin/os3 pr-check T=T-XXX` | `T=T-XXX bin/os3 pr-check` |
| `make archive` | `bin/os3 archive` |
| `make handoff-gemini ...` | `bin/os3 gemini next` (queue-driven) |
| `make ingest-gemini ...` | `bin/os3 gemini ingest` (stdin) |

---

## Help

각 subcommand 의 `--help`:
```bash
bin/os3 --help
bin/os3 dispatch --help
bin/os3 gemini --help
bin/os3 gemini next --help
```

문제 발생 시:
- `devos/questions/QUEUE.md` (Q-XXX 형식 질문 등록)
- `devos/logs/{date}-orchestrator-*.md` (dispatch 결과 로그)
- `devos/logs/gemini/` (Gemini 호출 로그)
