# pgvector·Redis 전환 — 설계 문서

- 작성일: 2026-09-08
- 작성자: 최두나
- 상태: 승인됨 (구현 대기)

## 0. 배경 — 전체 로드맵 중 이 문서의 위치

`plan.md`에서 팀이 P1에도 "완전 제외"로 명시한 SSE·STT/TTS·이미지 인식과, 다른 팀원(손영민) 담당인 예약/환불을 제외하고, 최두나 개인 확장 범위로 아래 5개 서브프로젝트를 순서대로 진행하기로 했다.

1. **pgvector·Redis 전환** ← 본 문서
2. 문서 업로드 + PDF RAG 변환 (1번의 저장소 위에 구현)
3. SSE 실시간 스트리밍
4. STT/TTS 음성 기능
5. 이미지 인식 분석

각 서브프로젝트는 별도 설계 문서 → 구현 계획 → 구현 사이클을 갖는다. 이 문서는 1번만 다룬다.

## 1. 목표

- RAG 검색을 현재의 순수 키워드 매칭(`document_repository.search`)에서 **OpenAI Embeddings + pgvector 코사인 유사도 검색**으로 전환한다.
- 게스트 세션(`session_repository`)과 실행 Trace(`trace_repository`)의 In-Memory 저장소를 **Redis**로 교체한다 (동작 계약은 동일하게 유지).
- 세션 대화 기억(`session_memory_repository`, 신규)을 Redis에 구현하고, `agent_orchestration_service`/`runtime`이 실제로 이를 읽어 후속 질문에 이전 대화를 반영하도록 연결한다.

## 2. 범위

### In-Scope
- `document_repository`, `session_repository`, `trace_repository`의 구현 교체 (인터페이스 유지)
- `session_memory_repository` 신규 구현 + Agent 응답 흐름 연결
- Postgres(pgvector)/Redis 연결 헬퍼, 시딩 스크립트, docker-compose, 환경변수, 헬스체크 확장
- `STORAGE_MODE=memory|persistent` 스위치로 기존 In-Memory 경로와 병행 유지 (회귀 테스트 보존)

### Out-of-Scope (다음 서브프로젝트 이후로 이동)
- PDF 파싱, 문서 업로드 API (서브프로젝트 2)
- `reserve_experience_program`, 예약/환불, `pending_action_repository` (손영민 담당, 이번 로드맵에서 다루지 않음)
- N-05 "개인화 코스 추천"처럼 세션 기억을 넘어선 새로운 Tool 조합 (범위는 "이전 대화 반영"까지만)
- SSE/STT-TTS/이미지 인식 (서브프로젝트 3~5)

## 3. 아키텍처

```
STORAGE_MODE=memory (기존, 기본값)      STORAGE_MODE=persistent (신규)
──────────────────────────────────    ──────────────────────────────────
document_repository → JSON 키워드      document_repository → Postgres+pgvector
session_repository   → dict(in-proc)   session_repository   → Redis
trace_repository     → dict(in-proc)   trace_repository     → Redis
session_memory_repo  → (미구현)         session_memory_repo   → Redis (신규)
```

`backend/app/main.py`가 `settings.STORAGE_MODE`를 보고 위 두 구현 모듈 중 하나를 골라 기존 Protocol(`SessionRepositoryProtocol`, `TraceRepositoryProtocol`, 신규 `SessionMemoryRepositoryProtocol`)에 주입한다. Router/Service의 호출 코드는 변경하지 않는다 — "인터페이스는 유지하고 구현체만 교체한다"는 `plan.md` 8.2절 원칙을 그대로 따른다.

## 4. 컴포넌트별 설계

### 4.1 `backend/app/core/db.py` (신규)
- `psycopg[binary]` 기반 커넥션 헬퍼. `DATABASE_URL` 환경변수로 연결.
- 앱 시작 시(`main.py` lifespan) `CREATE EXTENSION IF NOT EXISTS vector;`와 `document_chunks` 테이블·인덱스를 준비하는 `ensure_schema()` 제공 (없으면 생성, 있으면 무시).
- 커넥션은 프로세스당 단순 커넥션 풀(예: `psycopg_pool.ConnectionPool`)로 관리해 요청마다 재연결하지 않는다.

### 4.2 `backend/app/core/redis_client.py` (신규)
- `redis` 패키지의 동기 클라이언트. `REDIS_URL` 환경변수로 연결.
- 지연 초기화 싱글턴 (`get_redis_client()`), `try_get_settings()`와 동일한 실패-허용 패턴.

### 4.3 `document_repository.py` (구현 교체, 인터페이스 유지)

테이블 스키마:
```sql
CREATE TABLE document_chunks (
    id BIGSERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL,
    collection TEXT NOT NULL,
    title TEXT NOT NULL,
    page INTEGER,
    text TEXT NOT NULL,
    keywords TEXT[] DEFAULT '{}',
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ON document_chunks USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX ON document_chunks (collection);
```

- `search(query: str, collection: str, top_k: int) -> list[RetrievedChunk]`
  - OpenAI Embeddings API(`text-embedding-3-small`)로 `query`를 임베딩
  - `SELECT ... WHERE collection = %s ORDER BY embedding <=> %s LIMIT %s`
  - `score = round(1 - cosine_distance, 4)`로 변환 (기존 0~1, 높을수록 유사 계약 유지)
  - 동점 시 `doc_id` 오름차순 (기존 계약과 동일하게 애플리케이션 레벨에서 재정렬)
- `insert_chunks(chunks: list[ChunkInput]) -> None` (신규)
  - 각 chunk의 `text`를 임베딩해 upsert (`doc_id` 기준 `ON CONFLICT` 갱신)
  - 서브프로젝트 2(문서 업로드)의 진입점. 이번 문서에서는 시딩 스크립트만 이 함수를 사용한다.
- `scripts/seed_animal_cards.py` (신규): `data/animal_cards/*.json`을 읽어 `insert_chunks`로 최초 적재. 카드 파일이 바뀌면 재실행.

### 4.4 `session_repository.py` / `trace_repository.py` (구현 교체)

- Redis 키: `session:{session_id}` → `EX=SESSION_TTL_SECONDS`로 생성 시각 저장. `validate_session`은 키 존재 여부만 확인(만료는 Redis TTL이 자동 처리하므로 "만료됨"과 "존재한 적 없음"을 구분하지 않는다 — 기존과 달리 `trace_repository.clear_session()`을 세션 만료 시점에 명시적으로 호출할 필요가 없어진다).
- Redis 키: `trace:{session_id}` → List, `save_run`이 `RPUSH` + 최근 20개만 유지(`LTRIM`) + `EXPIRE`를 세션과 동일 TTL로 갱신.
- 함수 시그니처(`create_session`, `validate_session`, `save_run`, `list_runs`, `clear_session`)는 기존과 동일하게 유지 (`clear_session`은 persistent 모드에서는 사실상 no-op이거나 명시적 삭제로 구현 — 인터페이스 계약 유지 목적).

### 4.5 `session_memory_repository.py` (신규)

- Redis 키: `session_memory:{session_id}` → List, 각 원소는 `{"role": "user"|"agent", "text": str}` JSON.
- `append_message(session_id: str, role: str, text: str) -> None`: `RPUSH` 후 최근 `SESSION_MEMORY_MAX_TURNS`(기본 6개, 즉 user+agent 3턴)만 유지(`LTRIM`), `EXPIRE`를 세션과 동일 TTL로 갱신.
- `get_recent(session_id: str) -> list[dict]`: 저장된 순서(오래된 것→최신) 그대로 반환.

### 4.6 Agent 연결 (`agent_orchestration_service.py`, `runtime.py`)

- `SessionMemoryRepositoryProtocol`(신규): `get_recent(session_id) -> list[dict]`, `append_message(session_id, role, text) -> None`. 기존 Protocol들과 같은 방식으로 생성자 주입.
- `handle_ask()`:
  1. 세션 확정 후 `history = self._session_memory_repository.get_recent(session_id)` 조회
  2. `run_agent(..., conversation_history=history)` 호출
  3. 실행 후 `append_message(session_id, "user", request.message)`와 `append_message(session_id, "agent", response.final_answer)` 저장
- `run_agent`/`_run_loop` (`runtime.py`):
  - `run_agent(..., conversation_history: list[dict] | None = None)` 파라미터 추가 (기본값 `None` → 기존 호출부/테스트는 그대로 통과)
  - history가 있으면 `"최근 대화:\n사용자: ...\n에이전트: ...\n"` 형태로 **그대로 이어붙여**(별도 LLM 요약 호출 없이 단순 텍스트 포맷팅) `profile.instructions` 뒤에 덧붙인 뒤 `provider.next_turn(instructions=...)`에 전달
  - `ModelProvider` 인터페이스 자체는 변경하지 않는다 — `MockProvider`는 `instructions`를 무시하므로 기존 스크립트 기반 테스트는 영향받지 않는다.

## 5. 에러 처리

- Postgres/Redis 연결 실패 → 기존 `ToolError` 계약(`RAG_SEARCH_ERROR` 등 코드)으로 감싸 `success=false` 반환. 내부 예외 원문은 노출하지 않는다 (기존 `rag_service.retrieve_animal_info`와 동일 원칙).
- `GET /api/health` 응답에 `postgres`/`redis` 연결 상태 필드를 추가한다.
- OpenAI Embeddings API 실패(rate limit/네트워크) 시 1회 재시도 후 실패 처리 — 기존 `MCP_RETRY_COUNT` 패턴과 일관되게 `EMBEDDING_RETRY_COUNT` 설정값 추가.

## 6. 인프라 / 설정 변경

- `infra/docker-compose.yml` (신규): `pgvector/pgvector:pg16`, `redis:7` 컨테이너.
- `.env.example` 추가 항목: `DATABASE_URL`, `REDIS_URL`, `STORAGE_MODE=memory`(기본값), `SESSION_MEMORY_MAX_TURNS=6`, `EMBEDDING_MODEL=text-embedding-3-small`, `EMBEDDING_RETRY_COUNT=1`
- `backend/requirements.txt` 추가: `psycopg[binary]`, `psycopg_pool`, `pgvector`, `redis`
- `backend/app/core/config.py`의 `STORAGE_MODE` 타입을 `Literal["memory"]` → `Literal["memory", "persistent"]`로 확장.

## 7. 테스트 전략

- 기존 `tests/data/test_rag_service*.py`, `tests/data/test_session_and_trace_repository.py`는 `STORAGE_MODE=memory` 경로(기존 구현)로 그대로 통과해야 한다 — 회귀 없음이 목표.
- 신규 Postgres/Redis 테스트는 `@pytest.mark.integration` 마커로 분리하고 로컬 docker-compose 기동을 전제로 한다. 일반 `pytest` 실행(마커 미지정)에서는 스킵되어 기존 CI 흐름을 막지 않는다.
- `session_memory_repository`용 Fake(In-Memory dict 기반)를 만들어 `agent_orchestration_service`/`runtime` 단위 테스트에서는 실제 Redis 없이 검증한다 (기존 Fake Repository 패턴과 동일).

## 8. 마이그레이션 순서 (구현 계획에서 상세화 예정)

1. `core/db.py`, `core/redis_client.py`, docker-compose, 환경변수 추가
2. `document_repository`를 pgvector 구현으로 교체 + `insert_chunks` 추가 + 시딩 스크립트로 `data/animal_cards` 적재 확인
3. `session_repository`/`trace_repository`를 Redis 구현으로 교체
4. `session_memory_repository` 신규 구현 + Fake 버전 작성
5. `agent_orchestration_service`/`runtime`에 대화 기억 연결
6. `/api/health`에 연결 상태 노출, `STORAGE_MODE=persistent` 통합 테스트

## 9. 다음 서브프로젝트와의 연결점

- 서브프로젝트 2(문서 업로드 + PDF RAG 변환)는 본 문서의 `insert_chunks(chunks)` 함수를 그대로 재사용해, PDF에서 추출한 텍스트를 청킹한 뒤 적재하는 방식으로 설계될 예정이다.
