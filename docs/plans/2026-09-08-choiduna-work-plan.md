# 최두나 담당 작업 수행 및 후속 계획서

- 작성 기준일: 2026-09-08 (KST)
- 담당자: 최두나 (`ensk712@gmail.com`)
- 작업 브랜치: `choiduna`
- 통합 대상: `test`
- 관련 PR: #13 `티켓조회,저장소,다른 tool추가`, #14 `코스추가 머지`

## 1. 문서 목적

2026년 9월 8일에 수행한 조회 Tool, 저장소, MCP 연동, 추천 코스 기능과
PR 충돌 해결 작업을 하나의 실행 계획으로 정리한다. 완료된 범위와 후속 조치가 필요한
범위를 구분하여, 팀원이 현재 상태와 다음 작업 순서를 바로 확인할 수 있게 하는 것이
목적이다.

## 2. 작업 목표 및 현재 결과

### 목표

1. 관람권 종류에 따라 이용 가능한 전시관과 제외 항목을 조회한다.
2. 관람객 유형에 맞는 추천 관람 코스를 조회한다.
3. Zoo 조회 함수를 Backend와 MCP Server에서 동일한 계약으로 제공한다.
4. 메모리 기반 저장소를 PostgreSQL/pgvector와 Redis 기반으로 확장한다.
5. `choiduna`의 변경을 `test`에 충돌 없이 통합하고 회귀 테스트로 확인한다.

### 현재 결과

- [x] 티켓 범위 조회 Tool 구현
- [x] 추천 코스 조회 Tool 및 데이터 구현
- [x] MCP Tool wrapper와 Server 등록
- [x] Agent 허용 Tool 정책과 입력 Schema 연결
- [x] PostgreSQL/pgvector 및 Redis 저장 기반 추가
- [x] 단위 테스트와 MCP 직접 연결 테스트 보강
- [x] `choiduna` → `test` 충돌 해결
- [x] PR #13, PR #14를 통한 `test` 반영
- [ ] 전체 테스트의 기존 실패 4건 정리
- [ ] 런타임 SQLite DB와 pytest 임시 산출물의 Git 추적 정책 정리

## 3. 구현 범위

### 3.1 티켓 범위 조회

`lookup_ticket_scope(ticket_type)`은 사용자가 입력한 티켓 이름 또는 별칭을 표준 티켓
종류로 정규화한 뒤, 관람 가능한 항목과 제외 항목을 반환한다.

- 입력: `ticket_type: str`
- 데이터: `data/operations/tickets.json`
- 정상 출력: `ticket_type`, `included`, `excluded`
- 오류: 빈 문자열, 잘못된 타입, 등록되지 않은 티켓 종류
- 사용 위치: Backend Tool Executor, MCP Server

### 3.2 추천 관람 코스 조회

`get_course_info(name=None)`은 전체 추천 코스 목록 또는 이름으로 지정한 코스 하나를
조회한다.

- 입력: `name: str | None`
- 데이터: `data/operations/courses.json`
- 전체 조회: `name=None`
- 개별 조회: 코스 이름 지정
- 정상 출력: 코스명, 순서가 있는 시설 목록, 예상 총 관람 시간
- 오류: 잘못된 타입, 존재하지 않는 코스명
- 사용 위치: Zoo Guide Agent, Backend Tool, MCP Server

### 3.3 MCP 연동

순수 Python 조회 함수는 `backend/app/tools/zoo_tools.py`에 유지하고, MCP 계층은 해당
함수를 얇게 감싸 JSON 호환 결과를 반환한다.

```text
MCP Client
  → mcp_server/server.py
  → mcp_server/tools/zoo_read.py 또는 public_data.py
  → backend/app/tools/zoo_tools.py
  → data/operations/*.json
  → ToolRunResult
```

이 구조를 통해 Backend와 MCP가 동일한 조회 로직을 재사용하며, Runtime 또는 FastAPI를
Tool 모듈에서 역으로 import하여 순환 의존이 생기는 것을 방지한다.

### 3.4 PostgreSQL/pgvector 저장 기반

- `STORAGE_MODE=persistent`에서 PostgreSQL 연결 풀을 사용한다.
- pgvector 확장과 `document_chunks` 저장 구조를 준비한다.
- 임베딩 생성과 동물 카드 seed 경로를 제공한다.
- 문서 검색 Repository가 메모리 검색과 영속 검색을 설정에 따라 선택한다.
- PostgreSQL 또는 임베딩 API 장애 시 내부 예외를 그대로 사용자에게 노출하지 않는다.

### 3.5 Redis 저장 기반

- 세션 생성 및 TTL 검증
- 최근 대화 Memory 저장
- Agent 실행 Trace 저장 및 조회
- 테스트 모드에서는 기존 메모리 저장소를 사용할 수 있도록 이중 경로 유지
- 상태 점검에서 PostgreSQL과 Redis 연결 결과를 구분하여 반환

## 4. 주요 데이터 흐름

### 티켓 및 코스 조회 흐름

```text
사용자 질문
  → Zoo Guide Agent가 의도 판별
  → Agent Tool Policy에서 호출 가능 여부 확인
  → Tool Executor 또는 MCP Client
  → lookup_ticket_scope / get_course_info
  → JSON 데이터 조회 및 입력 검증
  → ToolRunResult
  → Agent 최종 답변
```

### RAG 및 세션 저장 흐름

```text
사용자 질문
  → 인증 세션 검증
  → Redis 최근 대화 조회
  → PostgreSQL/pgvector 문서 검색
  → Agent Runtime 실행
  → 응답과 Tool Trace 생성
  → Redis에 세션 Memory 및 Trace 저장
```

## 5. 주요 변경 파일

| 영역 | 주요 파일 | 역할 |
|---|---|---|
| Agent | `backend/app/agents/zoo_guide_agent.py` | 조회 Tool 허용 정책 |
| Schema | `backend/app/schemas/tools.py` | 티켓·코스 입력 계약 |
| Tool | `backend/app/tools/zoo_tools.py` | 티켓·코스 조회 로직 |
| 데이터 | `data/operations/tickets.json` | 티켓 범위 원본 데이터 |
| 데이터 | `data/operations/courses.json` | 추천 코스 원본 데이터 |
| PostgreSQL | `backend/app/core/db.py` | 연결 풀 및 pgvector Schema |
| Redis | `backend/app/core/redis_client.py` | Redis 연결 및 상태 확인 |
| Repository | `backend/app/repositories/` | 문서·세션·Memory·Trace 저장 |
| MCP | `mcp_server/server.py` | MCP Tool 등록 |
| MCP | `mcp_server/tools/zoo_read.py` | Zoo 조회 wrapper |
| MCP | `mcp_server/tools/public_data.py` | 티켓 조회 wrapper |
| 테스트 | `tests/data/test_zoo_tools.py` | 티켓·코스 Tool 계약 검증 |
| 테스트 | `tests/agent/test_agent_profile.py` | Agent 허용 Tool 검증 |
| 테스트 | `tests/ui_mcp/test_mcp_direct.py` | MCP 공개 Tool 검증 |

## 6. 커밋 및 PR 반영 이력

| 시각(KST) | 커밋 | 내용 | 반영 위치 |
|---|---|---|---|
| 09:24 | `6d2d538` | 목데이터 추가 | `origin/choiduna` |
| 11:24 | `2fd5b7d` | 티켓 조회, 저장소, DB/MCP 기반 | `origin/choiduna` |
| 11:25 | `f85de96` | 관련 구현·설정·테스트 보강 | `origin/choiduna` |
| 12:04 | `5e73b26` | `test` 변경 통합 | `origin/choiduna` |
| 12:06 | `9abbc07` | PR #13 반영 커밋 | `origin/test` |
| 12:19 | `e275e0a` | 추천 코스 기능 추가 | `origin/choiduna` |
| 12:42 | `cf4be2e` | `test` 충돌 해결 merge | `origin/choiduna` |
| 12:42 | `2f34449` | PR #14 코스 기능 반영 | `origin/test` |

## 7. 검증 결과

### 충돌 해결 후 관련 테스트

```text
34 passed
```

검증 범위:

- `tests/data/test_zoo_tools.py`
- `tests/agent/test_agent_profile.py`
- `tests/ui_mcp/test_mcp_direct.py`

### 전체 테스트

```text
209 passed, 4 failed
```

실패 4건은 이번 충돌 해결 코드와 직접 관련되지 않는다.

1. `tests/data/test_embedding_service.py` 3건
   - 원인: 현재 `backend/.venv`에 `pytest-asyncio`가 없어 async 테스트를 실행하지 못함
2. `tests/integration/rag_agent/test_rag_agent_integration.py` 1건
   - 원인: 검색된 문서 원문에 포함된 `OPENAI_API_KEY` 문자열까지 전체 응답 JSON에서
     금지하는 기존 테스트 기대 조건과 Tool 결과 전달 방식이 충돌함

## 8. 위험 요소 및 기술 부채

### 8.1 비동기 테스트 실행 환경

`pytest.ini`에 `asyncio_mode`가 선언되어 있지만 실행 환경에 관련 플러그인이 없어 경고와
실패가 발생한다. 테스트 의존성에 `pytest-asyncio`를 명시하고 같은 가상환경에서 전체
테스트를 다시 실행해야 한다.

### 8.2 RAG 문서 지시문 보안 테스트

문서 안의 악성 지시문을 실행하지 않는 것과, 검색 근거 원문을 Tool 결과에 포함하는 것은
구분해야 한다. 최종 답변·Tool Trace·API 응답 중 어느 경계에서 민감 문자열을 제거할지
팀 계약을 확정한 뒤 테스트 또는 직렬화 정책을 수정해야 한다.

### 8.3 런타임 생성 파일의 Git 추적

`data/zoo_auth.db`는 바이너리 파일이라 브랜치 간 자동 병합이 불가능하다. 또한 pytest
임시 산출물이 커밋에 포함되면 불필요한 변경과 권한 문제가 반복될 수 있다. DB 초기화
방식을 확인한 뒤 런타임 DB와 테스트 임시 경로를 Git 추적 대상에서 제외하는 작업이
필요하다.

## 9. 후속 작업 계획

### 우선순위 P0 — 테스트 기준 복구

- [ ] 테스트 의존성에 `pytest-asyncio` 추가
- [ ] 임베딩 비동기 테스트 3건 재실행
- [ ] RAG A-11 보안 계약 확정
- [ ] RAG 통합 테스트 수정 또는 응답 직렬화 정책 보완
- [ ] 전체 테스트 `0 failed` 확인

### 우선순위 P1 — 저장 데이터 정리

- [ ] `data/zoo_auth.db`가 저장소에 반드시 필요한 seed DB인지 확인
- [ ] 필요하지 않으면 Git 추적 해제 및 실행 시 자동 생성 방식으로 전환
- [ ] `.claude/.pytest_tmp_ui_mcp/` 등 pytest 임시 경로 ignore 처리
- [ ] PostgreSQL과 Redis를 실제로 기동한 상태에서 dependency health 확인

### 우선순위 P2 — 통합 동작 확인

- [ ] MCP `list_tools`에서 티켓·코스 Tool 노출 확인
- [ ] MCP Client로 두 Tool을 실제 호출하는 smoke test 수행
- [ ] Agent 질문에서 티켓 조회와 코스 조회 의도가 올바르게 분리되는지 확인
- [ ] Redis 세션 Memory가 후속 질문에 적용되는지 확인
- [ ] pgvector 검색 결과가 Agent 응답의 근거와 Trace에 연결되는지 확인

## 10. 최종 완료 조건

다음 조건을 모두 만족하면 2026-09-08 작업 범위를 완료로 판단한다.

1. `test` 브랜치에서 티켓 및 코스 조회가 정상 동작한다.
2. Backend와 MCP가 동일한 Tool 결과 계약을 반환한다.
3. PostgreSQL/pgvector와 Redis 상태를 각각 확인할 수 있다.
4. 세션, 최근 대화, Trace가 설정된 TTL 기준으로 저장된다.
5. 전체 pytest가 환경 누락 없이 실행되고 실패가 0건이다.
6. 런타임 DB와 테스트 임시 파일이 이후 PR 충돌을 만들지 않는다.

