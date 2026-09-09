# 동물원 관람 지원(Zoo Visit Guide) 개발 작업지시서 v0.5

작성일: 2026-09-09 · 대상: 손영민 / 최두나 / 이원민  · 목적: 회의 결과를 반영한 PostgreSQL 기반 AI Agent 시연과 충돌을 줄이는 분담 개발 · 공통 Python: 3.12.7

## 0. 문서 작성 관리 정책

- 기능·안전·완료 기준: 프로젝트의 `동물원_관람_지원_Zoo_Visit_Guide__에이전트_아키텍처_설계서_v0.5.md`.
- 충돌 시 기준: 2026-09-09 회의에서 확정한 변경사항은 이 문서를 우선한다. 그 밖의 기능·정책은 개발계획서를 따르고, 명시되지 않은 구현 방법·담당 경계는 이 문서로 확정한다. 예약은 Backend 로컬 변경 Tool, MCP는 조회 Tool 전용으로 분리한다.

### 용어

| 용어        | 이번 프로젝트에서의 뜻                                                    |
| ----------- | ------------------------------------------------------------------------- |
| P0          | 먼저 완성하여 반드시 시연하는 범위                                        |
| P1          | P0 통과 후 추가하는 기능. 완료하지 못하면 미구현으로 보고                 |
| 계약        | 함수 인자·반환형, JSON 필드, 상태값처럼 팀원끼리 맞춰야 하는 약속        |
| Mock        | 실제 동물원 운영 시스템 대신 쓰는 고정된 교육용 데이터                    |
| Stub / Fake | 다른 팀원의 구현을 기다리는 동안 테스트에서만 사용하는 대역               |
| Runtime     | LLM 호출, Tool 실행 결과 전달, 반복과 종료를 관리하는 코드                |
| 파일 소유자 | 해당 파일을 작성·수정하는 한 사람. 사용자는 여러 명이어도 수정자는 한 명 |

## 1. 프로젝트 개요와 범위

관람객의 질문에 동물 정보 문서를 검색하거나 먹이시간·휴장·경로 Tool을 호출하여, 확인한 근거를 포함한 답변을 제공한다. 학습 목표는 **LLM의 판단과 Backend의 실행 통제를 분리하고, Tool 결과를 관찰한 재판단을 Trace로 설명하는 것**이다.

### 1.1 P0: MVP

- 단일 `zoo_guide` Agent Profile과 순수 Python Runtime.
- 기존 JSON 형식 동물정보 100건을 PostgreSQL 테이블에 적재하고 pgvector 인덱스·RAG 검색 근거로 사용한다. 카드 목록 등 부속 데이터도 테이블 적재 대상을 명시한다.
- 먹이시간, 휴장, 경로 조회 Tool 3종. **세 Tool 모두 별도 MCP 프로세스를 거쳐 호출한다.** v3의 최소 1개 시연 조건을 동일한 호출 방식으로 충족한다.
- FastAPI Backend와 Streamlit 단일 화면, 동기 HTTP 요청/응답.
- Allowlist·Pydantic 검증·실행 한도·timeout·근거 없음·금지 요청 처리.
- 응답 Trace와 관리자 전용 Trace 조회 API.
- Mock Provider로 반복 가능한 시험, 실제 OpenAI Provider로 Agent 판단 시연. 운영 데이터는 두 모드 모두 Mock이다.

### 1.2 P1/P2: 추가 선택 기능

| 구분               | 기능                                                                             | 시작 조건                      |
| ------------------ | -------------------------------------------------------------------------------- | ------------------------------ |
| P1-A               | Mock 예약 + 사용자 승인·소유권·동시 확인 방지                                  | P0 통합 시험 완료              |
| P1-B               | 최근 대화 Memory, 티켓·날씨, 아이 동반·시간·이동 조건을 반영한 코스           | P0 완료, 해당 계약 추가 후     |
| P2                 | PostgreSQL 예약 영속화, Vision 이미지 분석, 관리자 Trace UX, STT/TTS, 화면 확장  | P1 회귀 시험 완료 후 별도 검증 |
| 필수 DB 전환       | JSON 100건 → PostgreSQL 적재 → pgvector/RAG 생성                               | 최두나 DB 마이그레이션 완료 후 |
| 선택 확장          | Redis, 문서 업로드, SSE, STT/TTS                                                 | P0를 유지하며 별도 PR로 구현   |
| 이번 작업에서 제외 | 실제 예약/결제/환불, 장기 개인정보 저장, 다중 Agent, 상용 배포, 완전한 영상 분석 | 구현하지 않음                  |

기본 와이어프레임과 기존 화면 시험은 완료된 기준선으로 유지한다. `origin/test`의 병합 이력에서 확인된 사용자 정보 화면과 관리자 Trace 화면은 이원민·손영민의 P2, 이미지 인식과 그 API는 최두나의 P2로 기록한다. 화면 요구로 필요한 DB 테이블은 최두나가 migration과 Schema 계약을 관리한다.

## 2. 시스템 아키텍처와 사용 흐름

### 2.1 실행 구조

```text
Streamlit :8501
  → HTTP POST /api/agent/ask
FastAPI :8000 (worker 1개)
  → Router: 요청/응답, HTTP 오류 처리
  → Orchestration Service: 세션, Profile 조회, 실행 조립, Trace 저장
  → Zoo Guide Profile + Agent Runtime
      → Provider: Mock 또는 OpenAI의 다음 행동 판단
      → Executor: 이름·인자·권한·위험도 검증
          ├─ retrieve_animal_info → RAG Service → PostgreSQL + pgvector
          └─ 운영 조회 Tool → MCP Client
                                → Streamable HTTP /mcp
                                → MCP Server :8100
                                → 순수 Python 조회 함수 + PostgreSQL 참조 데이터
      ← 표준 Tool 결과를 Provider에 재전달
      → 다음 행동 또는 최종 답변
  ← 상태·답변·출처·Tool 결과·Trace
```

- 프론트는 Backend API만 호출한다. LLM·RAG·MCP를 직접 호출하지 않는다.
- `classify_intent()`로 RAG/Tool을 먼저 나누지 않는다. LLM이 제공된 기능을 고른다.
- `intent`는 실제 실행 경로를 보고 마지막에 계산한다. 검색만 `rag`, 운영 Tool만 `tool`, 둘 다 `both`, 실행 전 거절/추가 질문은 `null`이다.
- RAG 검색은 로컬 준-Tool로 제공한다. `allowed_tools`는 운영 Tool용, `allowed_rag_collections`는 RAG용이다. Executor는 두 권한을 구분해 검사한다.
- Tool 결과를 받으면 LLM에 다시 전달한다. 미리 작성한 `if/else`가 모든 최종 행동을 대신 결정하지 않는다.
- Model이 실행을 제안해도 Backend 정책이 차단할 수 있다. 근거 없음·한도 초과·오류는 Backend가 안전하게 종료한다.
- HTTP 응답이 동기라는 것은 최종 결과를 한 번에 받는다는 뜻이다. Backend 내부 LLM/MCP I/O는 `async` 함수로 작성한다.

### 2.2 관람객 화면

1. 접속하면 “교육용 Mock 운영 데이터입니다” 안내와 질문 입력창을 보여준다.
2. 처음 질문할 때 `session_id=null`을 보낸다. Backend가 발급한 세션을 응답받아 `st.session_state`에 저장한다.
3. 실행 중 스피너를 표시하고 중복 제출을 막는다.
4. 답변 아래 RAG 출처와 점수, Tool 이름·데이터 기준 시각·조회 시각을 표시한다.
5. `needs_clarification`이면 필요한 항목을 보여준다. **P0는 대화 내용을 LLM에 자동 재전달하지 않으므로**, “정문에서 해양관까지 알려줘”처럼 완성된 질문으로 다시 입력하도록 안내한다. 채팅 화면에 과거 메시지가 보이는 것과 Agent Memory는 별개다.
6. “새 대화”는 화면 메시지와 세션을 초기화한다. 다음 요청에서 새 세션을 발급받는다.

### 2.3 수업 내용 적용표

| 수업 상대 경로                                                                                                  | 적용할 내용                                    | 주담당         |
| --------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- | -------------- |
| `00_references/04_api-contract-guide.md`                                                                      | JSON → Pydantic → Mock 연결 → 실제 연결     | 전원           |
| `06_agent-workflow/06_openai_agent_loop.py`                                                                   | State·Tool Result·재판단·종료               | 손영민         |
| `06_agent-workflow/openai_agent_backend.py`                                                                   | Model 호출과 검증 함수 분리                    | 손영민         |
| `03_mcp/0826_lab/backend/ai_agent.py`                                                                         | MCP Schema를 Function Tool로 변환, 결과 재전달 | 손영민         |
| `03_mcp/0826_lab/backend/_http_client.py`                                                                     | Streamable HTTP 연결과 세션 초기화             | 이원민         |
| `03_mcp/0826_lab/mcp_server/mcp_server.py`                                                                    | FastMCP의 얇은 Tool 등록 함수                  | 이원민         |
| `04_rag (1)/03_keyword_search.py`, `05_grounded_answer.py`                                                  | 키워드 점수, 검색 근거, 검색 실패 답변         | 최두나         |
| `07_human-approval-and-safety/07_human-approval-and-safety/02_pause_save_resume.py`, `04_safe_execution.py` | 승인 Snapshot과 실행 중단·재개                | 손영민·최두나 |
| `05_memory/10_labs/03_authenticated_scope_and_safe_keys.py`                                                   | 클라이언트 주장과 서버 검증값 구분             | 전원(P1)       |
| `08_agent-evaluation-and-tracing/README.md`                                                                   | 기대 행동, Trace, 회귀 평가                    | 최두나 취합    |
| `09_integrated-agent-lab/review-checklist.md`                                                                 | 재현 입력·실행 명령·실패 Trace 기록          | 전원           |

수업 폴더에는 `04_rag (1)`과 승인 폴더의 중복 디렉토리가 실제로 존재한다. 루트 README의 개요상 이름보다 위의 실제 경로를 따른다. 수업 코드를 프로젝트 밖에서 import하지 않고 필요한 구조만 프로젝트 코드로 옮긴다.

## 3. 공통 API 명세

### 3.1 엔드포인트와 수정 담당

| 단계 | Method / Path                           | 요청                | 응답                  | Router 소유자 |
| ---- | --------------------------------------- | ------------------- | --------------------- | ------------- |
| P0   | `GET /api/health`                     | 없음                | `HealthResponse`    | 이원민        |
| P0   | `POST /api/agent/ask`                 | `AgentAskRequest` | `AgentAskResponse`  | 손영민        |
| P0   | `GET /api/admin/trace?session_id=...` | 관리자 Bearer 토큰  | `TraceListResponse` | 이원민        |
| P1-A | `POST /api/agent/confirm`             | `ConfirmRequest`  | `AgentAskResponse`  | 손영민        |

P0에서 `/api/tools/*`, 문서 관리 API, 로그인 API, SSE API를 만들지 않는다. Tool 시험은 Python 함수 또는 MCP Client로 한다.

### 3.2 ask 요청과 응답

```json
{
  "message": "지금 펭귄 먹이시간이야?",
  "session_id": null
}
```

`message`: 공백 제거 후 1~2000자. `session_id`: 서버 발급 문자열 또는 `null`. 프론트가 Tool 인자·Tool 이름·권한을 직접 전달하는 필드는 두지 않는다. 정의되지 않은 추가 필드는 Pydantic에서 거절한다.

아래는 응답 모양을 보여주는 예시이며 실제 실행 기록이 아니다.

```json
{
  "run_id": "run_example",
  "agent_id": "zoo_guide",
  "session_id": "server_issued_example",
  "intent": "tool",
  "status": "completed",
  "termination_reason": "model_finished",
  "final_answer": "교육용 일정 기준으로 다음 펭귄 먹이시간은 14:30, 해양관입니다.",
  "sources": [],
  "tool_calls": [
    {
      "name": "get_feeding_schedule",
      "arguments": {"habitat": "해양관"},
      "risk": "read",
      "result": {
        "success": true,
        "data": {
          "habitat": "해양관",
          "animal": "펭귄",
          "next_feeding_at": "2026-09-05T14:30:00+09:00",
          "location": "해양관 관람대",
          "as_of": "2026-09-05T13:00:00+09:00"
        },
        "error": null,
        "source": "mock_zoo_operations",
        "retrieved_at": "2026-09-05T13:00:00+09:00"
      }
    }
  ],
  "pending_action": null,
  "trace": [
    {"owner": "runtime", "stage": "run_started", "data": {}},
    {"owner": "ai_agent", "stage": "tool_selected", "data": {"tool": "get_feeding_schedule"}},
    {"owner": "mcp", "stage": "tool_executed", "data": {"tool": "get_feeding_schedule"}},
    {"owner": "runtime", "stage": "run_completed", "data": {}}
  ]
}
```

### 3.3 실행 상태와 HTTP 오류를 구분한다

| `status`                | 의미                                | 대표 예                           |
| ------------------------- | ----------------------------------- | --------------------------------- |
| `completed`             | 정상 답변 또는 근거 없음 안내       | 검색 결과가 없어도 이 상태로 종료 |
| `needs_clarification`   | 필수 정보 부족·Tool 인자 오류      | 출발지 불명확                     |
| `confirmation_required` | P1 예약 승인 대기                   | 예약은 아직 미실행                |
| `rejected`              | 금지·권한 위반·유효하지 않은 승인 | 미허용 Tool, 승인 만료            |
| `stopped`               | 횟수 제한에 따른 안전 중단          | 동일 Tool 3번째 시도              |
| `error`                 | 인프라·Model 등의 실패             | timeout                           |

상태는 위 6개로 고정한다. `failed`, `waiting_user`, `waiting_approval`는 사용하지 않는다. 실행 중 내부 State의 `status`는 `null`로 두고, 응답을 반환할 때 반드시 위 값 중 하나를 채운다.

- Agent 실행 결과는 위 상태를 가진 HTTP 200 응답으로 반환한다. `error`도 실행 결과가 만들어진 경우에는 200이다.
- 요청 JSON 자체가 잘못되면 HTTP 422와 FastAPI `detail` 응답. Model이 만든 Tool 인자가 잘못된 경우와 구분한다.
- 세션 위조/만료, 관리자 인증 실패는 각각 403/401. `detail`은 사용자가 이해할 수 있는 일반 문장으로 반환한다.
- 예기치 못한 서버 예외는 500과 일반 `detail`. 프론트는 200 JSON만 가정하지 않는다.
- `HealthResponse`: `{status: "ok"|"degraded", backend: "ok", mcp: "ok"|"unavailable", storage: "postgresql", app_mode: "mock"|"openai"}`. MCP 또는 PostgreSQL 확인 실패는 503과 같은 모양의 본문으로 반환하며 연결 성공이라고 표시하지 않는다.
- `TraceListResponse`: `{runs: [{run_id, status, trace}]}`. 관리자 토큰은 `ADMIN_TOKEN` 환경변수로 설정하고 미설정 상태에서는 조회를 차단한다. P0는 이 방식으로 관리자 접근을 제한하고 로그인 화면은 만들지 않는다.

### 3.4 공통 모델 목록 — 손영민이 한 번 정의, 모두 import

| 모델               | 필수 필드/계약                                                                                                                                                                                                                |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `Source`         | `doc_id: str`, `title: str`, `page: int 또는 null`, `score: float(0~1)`                                                                                                                                               |
| `TraceItem`      | `owner`, `stage: str`, `data: dict`; owner는 `runtime/ai_agent/rag/mcp/policy/human`                                                                                                                                  |
| `ToolError`      | `code: str`, `message: str`; 내부 예외 원문·키를 넣지 않음                                                                                                                                                               |
| `ToolRunResult`  | `success: bool`, `data: dict`, `error: ToolError 또는 null`, `source: str`, `retrieved_at: timezone 포함 datetime`                                                                                                  |
| `ToolCallRecord` | `name`, `arguments`, `risk`, `result: ToolRunResult`                                                                                                                                                                  |
| `RetrievedChunk` | `doc_id`, `title`, `page`, `text`, `score`, `collection`                                                                                                                                                          |
| `RagInput`       | `query: str(1~500자)`, `collection: Literal["animal_cards"]`                                                                                                                                                              |
| `RagSearchData`  | `matched: bool`, `chunks: list[RetrievedChunk]`                                                                                                                                                                           |
| `AgentState`     | `run_id`, `agent_id`, `session_id`, `question`, `status`, `intent`, `termination_reason`, `llm_calls`, `tool_attempts`, `repeat_counts`, `tool_calls`, `sources`, `trace`, `answer`, `approval` |
| `ModelTurn`      | `response_id: str`, `calls: list[ModelToolCall]`, `text: str`, `clarification: str 또는 null`                                                                                                                         |
| `ModelToolCall`  | `call_id: str`, `name: str`, `arguments_json: str`                                                                                                                                                                      |

`RagSearchData`는 별도 응답 봉투를 만들지 않고 `ToolRunResult.data`에 JSON으로 직렬화한다. `ModelTurn`은 Mock/OpenAI 어댑터를 통일하기 위한 내부 모델이다. 운영 결과의 타입 검증용 모델도 `schemas/tools.py`에 둔다.

## 4. Tool·RAG·데이터 계약

### 4.1 이름과 입력을 고정한다

| 기능 이름                     | 입력                                       | 실행 위치            | 결과`data`                                                                                                        |
| ----------------------------- | ------------------------------------------ | -------------------- | ------------------------------------------------------------------------------------------------------------------- |
| `retrieve_animal_info`      | `query`, `collection`                  | Backend RAG 준-Tool  | `matched`, `chunks`                                                                                             |
| `get_feeding_schedule`      | `habitat: str`                           | MCP                  | `habitat`, `animal`, `next_feeding_at: datetime 또는 null`, `location`, `as_of`                           |
| `check_closure_status`      | `habitat: str 또는 null`                 | MCP                  | `items: [{habitat, closed, reason}]`, `as_of`                                                                   |
| `find_habitat_route`        | `current: str`, `destination: str`     | MCP                  | `current`, `destination`, `path: list[str]`, `estimated_minutes: int`, `as_of`                            |
| `lookup_reservation_policy` | `policy_type: "approval"\|"cancellation"` | Backend DB 조회 Tool | `product_name`, `policy_type`, `content`, `source_name`, `source_url`, `checked_at`, `effective_from` |

- P0 위험도는 모두 `read`. `lookup_reservation_policy`도 참조 조회만 수행하며 예약 상태를 변경하지 않는다. `draft` 등급과 `check_capacity`라는 공개 Tool은 추가하지 않는다.
- MCP 이름은 위 운영 함수명과 동일하다. `mcp__zoo__` 접두사를 붙이지 않는다.
- `check_closure_status(null)`은 전체 시설 상태를 반환한다. 한 시설 요청도 `items` 목록으로 반환한다.
- 위치 문자열은 공백 제거 후 1~100자, Pydantic strict 검증과 `extra="forbid"` 사용. 숫자·목록을 문자열로 조용히 변환하지 않는다.
- 시설 이름 별칭은 `data/operations/habitats.json`에서 정규화한다. 예: 펭귄/펭귄관 → 해양관, 호랑이사 → 호랑이관. 등록되지 않은 시설은 오류이며 임의 추측하지 않는다.
- 없는 시설·없는 경로: `success=false`, `error.code=HABITAT_NOT_FOUND/ROUTE_NOT_FOUND`. 사용자에게 위치 확인을 요청한다.
- 당일 먹이 일정 없음: `success=true`, `next_feeding_at=null`. 일정이 없다고 안내하고 임의 시간을 생성하지 않는다.
- 모든 Tool 결과는 3.4절 봉투를 따른다. MCP `isError`, 잘못된 JSON, 필드 누락은 MCP Client가 `MCP_TOOL_ERROR`로 표준화한다.

### 4.2 문서와 DB 마이그레이션 — 최두나 소유

| 파일/폴더                                       | 내용                                                                                                 |
| ----------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| `data/animal_cards/*.json`                    | 현재 확보된 동물정보 JSON 100건.`doc_id,title,collection,page,text,keywords` 계약을 검증한 뒤 적재 |
| `data/operations/habitats.json`               | 정문·호랑이관·해양관·코끼리관·기린관, 별칭                                                       |
| `data/operations/feeding.json`                | 해양관 펭귄 11:00/14:30, 호랑이관 15:00 등 일일 교육용 일정                                          |
| `data/operations/closures.json`               | 해양관 정상, 코끼리관 점검 휴장 등 정상/휴장 사례                                                    |
| `data/operations/routes.json`                 | 정문→호랑이관 10분, 정문→해양관 15분 등 정해진 경로                                                |
| `data/references/reservation_policies/*.json` | 에버랜드 드림투어를 참조해 정리한 예약 승인·취소 규정과 출처·확인일                                |

마이그레이션 순서는 아래로 고정한다.

1. JSON 원본 100건과 카드 목록·부속 데이터의 필수 키, 중복 `doc_id`, 인코딩을 검증한다.
2. PostgreSQL migration으로 동물 원문 테이블, RAG Chunk/Embedding 테이블, 예약 정책 참조 테이블을 생성한다.
3. 동일 migration 버전의 seed/import 절차로 JSON을 insert/upsert한다. 원본 JSON은 추적 가능한 입력 자료로 보존한다.
4. 원본 건수와 적재 건수, 필수 필드 null, 중복 키를 대조한다. 동물정보 기준 완료 조건은 **유효 JSON 100건 = DB 적재 100건**이다.
5. 적재가 검증된 행에서 Chunk와 embedding을 만들고 pgvector 인덱스를 생성한다.
6. 대표 질의로 RAG 검색 결과의 `doc_id`·출처·점수를 검증한다. DB 적재 성공만으로 RAG 완료로 보지 않는다.

최소 테이블 계약은 `animal_information`, `animal_document_chunks`, `reservation_policy_references`, `schema_migrations`로 한다. 실제 컬럼·제약·인덱스는 SQL migration에 기록하고, 예약 정책에는 `policy_id`, `product_name`, `policy_type`, `content`, `source_name`, `source_url`, `checked_at`, `effective_from`, `is_active`를 둔다. 정책 변경 이력을 덮어쓰지 말고 새 버전으로 보존한다.

개체 나이·이송 이력처럼 확보하지 않은 정보는 카드에 만들지 않는다. 카드가 교육용 작성 자료이면 그렇게 표시한다. 실제 운영 공지나 공식 개체 기록이라고 표현하지 않는다. `source=mock_zoo_operations`는 화면에서도 교육용임을 표시한다.

경로는 JSON 표 조회로 시작한다. 지도 API·최단경로 알고리즘을 추가하지 않는다. 반대 방향 경로도 별도 행이 있어야 제공한다.

### 4.3 RAG 구현 규칙

1. PostgreSQL에 검증 적재된 동물정보 100건을 기준으로 Chunk를 생성한다. JSON 파일을 런타임 검색 원본으로 직접 읽지 않는다.
2. 수업의 키워드 중복 점수 방식을 사용하되, `keywords`와 별칭 사전으로 “호랑이는/호랑이”, “먹이/무엇을 먹어” 등을 정규화한다. 대표 질문에 불필요한 조사·질문 표현을 제외하는 작은 규칙을 만든다.
3. 점수는 정규화된 검색 토큰 중 카드 본문·키워드와 겹친 토큰의 비율(0~1). 빈 토큰은 0점. 같은 점수면 `doc_id` 오름차순으로 정렬한다.
4. `top_k=3`, `RAG_MIN_SCORE=0.5`를 초기 기준으로 사용하되 pgvector 거리/유사도 변환 규칙을 코드와 시험에 고정한다. 5개 이상 대표 질문으로 튜닝한 결과와 실패 예를 기록한다.
5. 허용 컬렉션 검사와 인자 검증을 통과한 뒤 검색한다. 미달 Chunk는 LLM 근거에 포함하지 않는다.
6. 결과 없음은 `success=true`, `data={"matched":false,"chunks":[]}`. 검색 장애는 `success=false`로 구분한다.
7. Runtime이 결과를 LLM에 전달하고 최종 답변을 받는다. **RAG Service에서 별도 LLM을 호출하지 않는다.** 근거가 없으면 Backend가 확인 불가 문구로 종료하여 사실 생성을 막는다.
8. 출처는 실제 채택한 Chunk에서만 생성한다. 문서 속 지시문은 데이터로 취급한다. 수업 0826 예제의 “근거 없으면 일반 지식 답변”은 복사하지 않는다.

## 5. 함수·모듈 계약

아래 인자명과 반환형을 먼저 고정한다. `async`로 표시한 함수는 호출할 때 `await`한다. 공통 모델은 3.4절과 `schemas/`에서 가져온다.

| 소유자 | 파일                                              | 공개 함수/객체와 역할                                                                                                                                                             |
| ------ | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 손영민 | `agents/models.py`                              | frozen`AgentProfile(agent_id,name,goal,description,example_questions,instructions,allowed_tools,allowed_rag_collections)`                                                       |
| 손영민 | `agents/registry.py`                            | `get_agent_profile(agent_id: str) -> AgentProfile`                                                                                                                              |
| 손영민 | `agents/runtime.py`                             | `async run_agent(request, profile, *, provider, executor, settings) -> AgentAskResponse`                                                                                        |
| 손영민 | `providers/base.py`                             | `async next_turn(*, question, instructions, tools, previous_response_id, tool_outputs) -> ModelTurn` 공통 Protocol                                                              |
| 손영민 | `services/agent_orchestration_service.py`       | `async handle_ask(request: AgentAskRequest) -> AgentAskResponse`; 세션 검증/발급, Runtime 호출, Trace 저장                                                                      |
| 손영민 | `tools/registry.py`                             | `get_tool_definitions(profile, discovered_tools) -> list[dict]`; 정책과 MCP 목록 교집합 + 허용 RAG 정의                                                                         |
| 손영민 | `tools/executor.py`                             | `async execute_tool_safely(name, arguments, *, profile, state) -> ToolRunResult`; 실제 의존성은 생성자 주입                                                                     |
| 최두나 | `tools/zoo_tools.py`                            | `get_feeding_schedule(habitat)`, `check_closure_status(habitat=None)`, `find_habitat_route(current,destination)`; 모두 `ToolRunResult` 반환, 운영 Mock 데이터 조회만 수행 |
| 최두나 | `services/rag_service.py`                       | `retrieve_chunks(query: str, *, collection="animal_cards", top_k=3) -> list[RetrievedChunk]`; `retrieve_animal_info(query, collection) -> ToolRunResult`                      |
| 최두나 | `repositories/document_repository.py`           | PostgreSQL에서 동물정보/Chunk를 조회하고`search(query, collection, top_k) -> list[RetrievedChunk]` 제공                                                                         |
| 최두나 | `repositories/reservation_policy_repository.py` | 활성 예약 승인·취소 참조 규정 조회, 출처·확인일·버전 반환                                                                                                                      |
| 최두나 | `repositories/session_repository.py`            | `create_session() -> str`; `validate_session(session_id) -> bool`                                                                                                             |
| 최두나 | `repositories/trace_repository.py`              | `save_run(session_id, run_id, status, trace) -> None`; `list_runs(session_id) -> list[dict]`                                                                                  |
| 최두나 | `services/eval_service.py`                      | `async run_scenarios(base_url, scenario_paths) -> list[dict]`; HTTP를 통한 시험 결과 수집                                                                                       |
| 이원민 | `mcp_client/client.py`                          | `async list_tools() -> list[dict]`; `async call_tool(name, arguments) -> ToolRunResult`; `async check_health() -> bool`                                                     |
| 이원민 | `mcp_server/server.py`                          | `create_mcp_server() -> FastMCP`; `streamable-http`로 시작                                                                                                                    |
| 이원민 | `mcp_server/tools/zoo_read.py`                  | 조회 Tool 3개의 MCP 등록용 얇은 wrapper; 최두나의 순수 조회 함수를 호출                                                                                                           |
| 이원민 | `frontend/clients/agent_client.py`              | 동기`ask(message, session_id=None) -> dict`; `get_health() -> dict`; P1 `confirm(session_id,action_id,decision) -> dict`                                                    |

- 실제 import 앞에는 `backend.app.`을 붙인다. 모든 실행 명령은 저장소 루트 기준이다.
- MCP 프로세스가 `backend.app.tools.zoo_tools`를 import하는 것은 코드 재사용이다. Backend HTTP를 다시 호출하는 구조가 아니다. 이 모듈은 FastAPI 앱·Runtime·MCP Client를 import하지 않아야 한다.
- `McpClient.list_tools()`의 각 dict는 `{name, description, input_schema}`로 정규화한다. SDK 객체가 다른 레이어로 새지 않게 한다.
- Model이 요구한 이름·인자만으로 `eval()` 또는 동적 import를 실행하지 않는다. Registry의 명시적 함수 매핑을 쓴다.
- Provider는 `ModelTurn`으로 결과를 정규화한다. 추가 정보가 필요할 때 사용할 명시적 응답 규약도 손영민이 Provider 내부에서 정의한다. 질문형 문장에 `?`가 있다는 이유만으로 상태를 추측하지 않는다.
- 추가 질문은 Model에 로컬 제어 함수 `request_clarification(question)`를 제공하는 방식으로 확정한다. 이는 실행 Tool이 아니며 MCP 목록·운영 Allowlist에 넣지 않고 Provider가 `clarification`으로 변환한다. 제어 인자도 검증하며, 이 호출을 받은 턴에서는 다른 Tool을 실행하지 않고 `needs_clarification`으로 종료한다. 제어 호출은 실행이나 승인 권한을 갖지 않는다.
- RAG 호출도 `tool_calls`에 기록하되 Trace owner는 `rag`다. `intent` 계산에서는 이 이름을 RAG로 분류한다. 실행하지 않고 차단한 호출은 `tool_calls` 대신 `policy` Trace에 남긴다.
- Settings는 환경변수와 같은 이름의 필드를 사용한다. 추가로 `PROJECT_ROOT`, `DATA_DIR`를 계산한다. 상대 코드가 자체적으로 `.env`를 다시 읽거나 다른 기본값을 만들지 않는다.
- `main.py`에서 Settings → Repository/RAG → MCP Client → Provider/Executor → Service 순서로 인스턴스를 조립한다. Repository는 프로세스 내 하나를 재사용한다. Router마다 새 저장소를 만들지 않는다. 테스트에서는 생성자 인자로 Fake를 주입한다.

### 5.1 Runtime 한도와 오류 처리

| 설정                              | 값      | 적용                                                                |
| --------------------------------- | ------- | ------------------------------------------------------------------- |
| `MAX_AGENT_STEPS`               | 6       | 최초 호출을 포함한 LLM 호출 총수. 7번째 호출 전`stopped`          |
| `MAX_SAME_TOOL_CALLS`           | 2       | 이름 + 정규화 인자 JSON별 실행 시도. 3번째 전`stopped`            |
| `MAX_TOOL_CALLS`                | 8       | RAG·운영 Tool 실제 실행 시도 합계. 9번째 전 부분 결과와`stopped` |
| `RUN_TIMEOUT_SECONDS`           | 90      | 전체 요청 deadline. 초과하면`error`                               |
| `MCP_TIMEOUT_SECONDS`           | 10      | 조회 호출 한 번의 제한, 전체 deadline 이내                          |
| `MCP_RETRY_COUNT`               | 1       | 조회 timeout의 추가 시도 한 번. 재시도도 위 호출 횟수에 포함        |
| `PENDING_TTL_SECONDS`           | 120     | P1 승인 만료                                                        |
| `RAG_TOP_K` / `RAG_MIN_SCORE` | 3 / 0.5 | 검색 기준                                                           |

재시도 정책은 Executor/Runtime 한 곳에서만 관리한다. MCP Client는 자체 재시도하지 않는다. SDK 자동 재시도가 한도를 숨기지 않게 Provider 재시도 설정도 명시한다. P0 Model 호출 자동 재시도는 하지 않는다. 최대 호출 수·deadline은 재시도보다 우선한다.

Model이 한 응답에 여러 Tool을 반환해도 Backend는 순차 검증·실행하며 호출마다 한도를 검사한다. 기본 요청은 수업처럼 병렬 Tool 요청을 끈다. JSON 파싱 실패/필수 인자 누락은 MCP 전 `needs_clarification`, 미허용 Tool은 `rejected`. 잘못된 입력에는 timeout 재시도를 적용하지 않는다.

Provider에 환경변수 전체·토큰·임의 로컬 파일을 전달하지 않는다. Trace에는 필요한 상태와 근거만 남기며 API 키·관리자 토큰·원문 비밀정보를 넣지 않는다. 최종 답변의 운영 숫자·시간·예약번호는 Tool 결과와 대조한다. 생성 문장 전체의 사실성을 자동으로 보장한다고 주장하지 말고 10장의 대표 Case로 검증한다.

## 6. 디렉토리와 파일 소유권

소유자 표기: `[손]` 손영민, `[최]` 최두나, `[이]` 이원민. **같은 폴더라도 파일별로 소유권이 다를 수 있다.** 폴더 전체 포맷 변경을 하지 않는다.

```text
team2/                              # 현재 프로젝트 폴더를 저장소 루트로 사용
├─ README.md                        [최] 실행 안내·P0 평가 결과
├─ requirements.txt                 [최] 세 담당 의존성 파일을 -r로 포함
├─ pytest.ini                       [손] 테스트 경로·marker
├─ .gitignore                       [손] .venv/.env/cache/generated treports 제외
├─ .env.example                     [최] 값 없는 키 목록·안전한 기본 설정
│
│  ├─ agent.txt                     [손] openai, fastapi, uvicorn, pydantic, pytest 등
│  ├─ data.txt                      [최] python-dotenv 등 데이터/설정 관련
│  └─ ui-mcp.txt                    [이] streamlit, httpx, mcp 등
├─ backend/
│  ├─ requirements.txt
│  └─ app/
      ├─ main.py                    [손] 앱 생성·Router 등록·의존성 조립
│     ├─ core/
│     │  ├─ config.py               [최] Settings·절대 데이터 경로
│     │  └─ auth.py                 [이] 관리자 토큰 검증
│     ├─ schemas/                   [손] common.py, agent.py, tools.py, rag.py
│     ├─ agents/                    [손] models.py, zoo_guide_agent.py, registry.py, runtime.py
│     ├─ providers/                 [손] base.py, mock_provider.py, openai_provider.py
│     ├─ routers/
│     │  ├─ agent_router.py         [손] ask / P1 confirm
│     │  ├─ health_router.py        [이] health
│     │  └─ admin_router.py         [이] Trace 조회만
│     ├─ services/
│     │  ├─ agent_orchestration_service.py [손]
│     │  ├─ approval_service.py     [손]
│     │  ├─ rag_service.py          [최]
│     │  └─ eval_service.py         [최]
│     ├─ tools/                     registry.py·executor.py [손], zoo_tools.py [최]
│     ├─ repositories/              [최] document/session/trace_repository.py
│     │                              P1: pending_action/reservation/session_memory_repository.py
│     └─ mcp_client/                [이] client.py
├─ mcp_server/
│  └─ requirements.txt              [이] server.py, tools/zoo_read.py
├─ frontend/                        [이] app.py·Client·관람객 화면
│  ├─ app_pages/                    [이] 사용자 정보·지도·코스·음성·이미지 화면
│  ├─ components/                   [이] 공통/채팅/예약/경로 지도 컴포넌트
│  └─ image/                        [이] 로컬 화면용 jpg/png/pdf 자산
├─ frontend_admin/                  [이] 인증·예약·관리자 화면, [손] Trace 조회 UX 보강
├─ data/                            [최] animal_cards/, operations/, references/
├─ migrations/                      [최] PostgreSQL 테이블·seed·pgvector migration
├─ tests/
│  ├─ agent/                        [손] Runtime·정책·Schema·ask·P1 승인
│  ├─ data/                         [최] DB migration·RAG·저장소·평가
│  ├─ ui_mcp/                       [이] MCP·HTTP Client·health·admin API
│  └─ integration/                  rag_agent [최], mcp_agent·e2e_ui [이], policy [손]
├─ eval/
│  ├─ run.py                        [최] 평가 실행 진입점
│  └─ scenarios/
│     ├─ agent.json                 [손] 정책·반복·추가 질문
│     ├─ rag.json                   [최] 검색·근거
│     └─ mcp.json                   [이] 운영 Tool·MCP 장애
└─ docs/
   ├─ Zoo_Visit_Guide_팀별_개발_작업지시서_v5.md
   ├─ 동물원_관람_지원_Zoo_Visit_Guide__에이전트_아키텍처_설계서_v0.5.md                           
   └─ reports/
```

- `README.md`는 한 사람의 전체 통합 보고서가 아니다. 각 담당자가 자신의 실행 명령·제한사항을 제안하고, P0 최종 병합 때 세 명이 합의한 내용만 최두나가 한 번에 반영한다. 최두나는 평가 결과를 취합할 뿐, 다른 담당 영역의 결함을 혼자 해결하는 책임을 지지 않는다.
- 패키지의 빈 `__init__.py`는 해당 폴더 담당자가 만들고 이후 export 목록을 모으지 않는다. 루트 `backend/__init__.py`, `backend/app/__init__.py`는 손영민 소유다.
- 테스트 공용 `conftest.py`는 처음부터 만들지 않는다. 각 담당 폴더 안에 자신의 fixture를 둔다. 공유가 필요하면 공동 계약 회의 후 손영민이 파일을 만들고, 세 명이 소비 계약을 검토한다.
- 원본 운영 JSON과 공통 migration은 최두나가 소유한다. 장애 시험용 Fake와 데이터는 각자의 테스트 폴더에 둔다. 실제 시연 데이터를 고쳐 timeout을 흉내 내지 않는다.
- 이 문서 이후 새 파일도 PR 설명에 소유자를 기록한다. 위 표에 없는 공통 파일을 임의로 두 사람이 만들지 않는다.

## 7. 착수·빌드·병합 순서

### 7.1 Gate 0: 계약과 뼈대부터 병합

이 단계가 끝나기 전에는 서로 다른 Schema를 가정하고 기능을 길게 개발하지 않는다.

| 순서 | 작업                                                                               | 담당                             | 완료 증거                                              |
| ---- | ---------------------------------------------------------------------------------- | -------------------------------- | ------------------------------------------------------ |
| G0-1 | 공통 Schema, Profile, Provider Protocol, Runtime/Executor 함수 선언, pytest marker | 손영민                           | 입력/응답 JSON을 Pydantic으로 검증, 공통 패키지 import |
| G0-2 | Settings,`.env.example`, PostgreSQL Schema/migration, Repository/RAG 함수 선언   | 최두나                           | JSON 100건 검증·DB 적재·모델 생성 시험               |
| G0-3 | MCP Client·Server 함수 선언, 프론트 Client, health/admin Router                   | 이원민                           | MCP 기동과 Router import                               |
| G0-4 | Python 3.12.7 가상환경·공통 requirements 확인                                     | 최두나                           | 세 담당자의 같은 버전 설치·import 기록                |
| G0-5 | main.py에 각 Router와 의존성을 조립                                                | 손영민 작성, 최두나·이원민 검토 | Backend health 확인, 전원 같은 Schema import           |

G0-2/G0-3은 G0-1 병합 후 각자 진행한다. G0-5는 각 Router와 의존성의 계약이 확정된 뒤에만 작성한다. stub은 명시적으로 미구현을 알리고 성공을 위장하지 않는다. Stub 기반 화면 시험은 테스트에서 Fake 응답을 주입한다.

**Gate 0 완료 조건:** 세 명 모두 main 최신 상태에서 모듈 import·공통 계약 시험 성공, DB migration·데이터 키·함수 인자·상태값 확인. 이 상태를 기준으로 기능 브랜치를 만든다.

### 7.2 기능 개발과 통합

| 단계          | 손영민                              | 최두나                                   | 이원민                                 | 공동 통합 책임                             | 병합 조건                       |
| ------------- | ----------------------------------- | ---------------------------------------- | -------------------------------------- | ------------------------------------------ | ------------------------------- |
| G1 개별 구현  | Profile/정책, Scripted Mock Runtime | DB migration·100건 적재·RAG/저장소     | MCP wrapper/client, 기존 화면          | 각자 자기 모듈 단위 시험                   | 각자 단위 시험·계약 준수       |
| G2 연결       | Runtime에서 RAG/MCP 의존성 사용     | PostgreSQL/pgvector ↔ Runtime 연결 주관 | MCP ↔ Runtime 및 Streamlit 연결       | DB/RAG: 최+손 / MCP·UI: 이+손             | 대표 API·화면 통과             |
| G3 실제 판단  | OpenAI Provider 연결, 결과 재전달   | 대표 질의 검색 품질 확인                 | 응답 화면·실행 안내                   | 전원이 Trace·화면 검증                    | 실제 LLM Trace와 DB 근거 증명   |
| G4 안전·평가 | 반복·권한·오류 Case 수정          | 평가 실행·DB 대조 결과 취합             | MCP 중단·인증·UI 오류                | 최가 최종 결과 취합, 전원이 자기 Case 재현 | Case 통과 또는 미통과 사유 명시 |
| P1            | 승인 상태 전이·코스 로직           | 예약 정책 DB·Pending/예약/Memory        | 승인 API/기존 카드                     | 승인: 손+최+이                             | P0 회귀 유지, P1 전용 시험      |
| P2            | Trace UX·STT/TTS·RAG 오류 보강    | 예약 영속화·Vision API                  | 사용자 화면·지도·음성/이미지 UI 확장 | 기능별 소유자가 API/UI 연결 시험           | P1 회귀 유지, P2 전용 시험      |

G1에서는 상대 구현 대신 **테스트용** Fake를 사용한다. 예: 손영민은 FakeMcpClient/FakeRagService, 최두나는 Provider 없는 검색 테스트, 이원민은 고정 AgentAskResponse로 화면을 만든다. G2부터 실제 연결로 교체한다. 최종 시연에 FakeMcpClient가 남으면 MCP 통과로 인정하지 않는다.

### 7.3 공동 통합 운영표

통합은 코드 한 파일을 누가 편집하는지와 전체 흐름을 누가 검증하는지를 분리한다. `main.py`의 파일 소유자는 손영민이지만, 각 연결의 통과 책임은 아래 두 명 이상에게 있다.

| 연결 범위                     | 작성/수정 파일 소유자  | 연결 시험 주관 | 함께 확인할 사람 | 통과 기준                                                    |
| ----------------------------- | ---------------------- | -------------- | ---------------- | ------------------------------------------------------------ |
| RAG → Runtime → ask API     | 손영민·최두나         | 최두나         | 손영민           | N-01, A-01, A-11의 출처·점수·상태 일치                     |
| MCP → Executor → Runtime    | 이원민·손영민         | 이원민         | 손영민           | N-02~04, A-03, A-14의 실제 MCP 호출·오류 처리               |
| Backend API → Streamlit      | 이원민·손영민         | 이원민         | 손영민           | 질문·출처·Tool 카드·오류 화면 표시                        |
| 확장 화면 → Backend API      | 이원민·손영민·최두나 | 이원민         | 손영민·최두나   | 사용자 정보·Trace·음성·이미지의 정상/빈/오류/권한 상태    |
| PostgreSQL → pgvector → RAG | 최두나·손영민         | 최두나         | 손영민           | JSON 100건 대조, 벡터 생성, 대표 검색 근거 일치              |
| 공통 Settings·데이터·환경   | 최두나                 | 최두나         | 손영민·이원민   | Python 3.12.7과 같은 DB 데이터로 기동                        |
| 최종 P0 평가·보고            | 최두나                 | 최두나         | 손영민·이원민   | 전원 Case의 실제 결과·Trace·미통과 사유 취합               |
| P1 승인 흐름                  | 손영민·최두나·이원민 | 손영민         | 최두나·이원민   | 승인 전 0건, 승인 후 1건, 정책 근거·만료·소유권·중복 차단 |

연결 시험이 실패하면 주관자는 처음 실패한 Trace를 기록하고, 해당 파일 소유자가 수정한다. 주관자가 상대 파일을 직접 수정하지 않는다.

## 8. 팀원별 작업계획

### 8.1 손영민 — Agent Runtime·정책·Agent API

| 순서    | 할 일                            | 산출물                                         | 확인 방법                             |
| ------- | -------------------------------- | ---------------------------------------------- | ------------------------------------- |
| S1      | 3~5장 공통 모델과 Profile 구현   | schemas, agents/models·registry               | 유효/누락/추가 필드 테스트            |
| S2      | 정책 Registry·Executor 구현     | tools/registry·executor                       | 잘못된 인자·금지 이름은 실행 0회     |
| S3      | Scripted Mock Provider와 Runtime | providers/mock_provider, runtime               | Tool 결과 전달 후 다음 턴, 종료 한도  |
| S4      | ask 조립과 Agent Router 구현     | service, agent_router                          | Fake 의존성으로 ask HTTP 시험         |
| S5      | 수업 Provider를 어댑터로 적용    | openai_provider                                | 실제 Model Tool 선택·재판단 Trace    |
| S6      | 공격·반복·오류 시험            | tests/agent, integration/policy, agent.json    | A-02/04/05/09~13                      |
| S7(P1)  | 승인 상태기계·예약 제어         | approval_service, confirm                      | 승인 전 0건·후 1건                   |
| S8(P2)  | 영속 RAG 검색·프론트 예외 보강  | document_repository, executor, home            | 저장소 장애와 UI 예외 회귀 시험       |
| S9(P2)  | 관리자 Agent Trace 조회 UX 개선  | trace_repository, admin_router, frontend_admin | 관리자 세션·필터·상세 Trace 시험    |
| S10(P2) | 음성 전사·안내 응답·TTS 연결   | Web Speech API, voice_assistant                | STT→Agent→TTS 흐름과 실패 격리 시험 |

받는 것: 최두나의 RAG·운영 조회 함수·Repository/Settings, 이원민의 MCP Client/Router. 넘기는 것: Schema·Profile·AgentAskResponse. `main.py`는 손영민이 조립하되, 최두나·이원민이 연결 계약을 검토한다. **이원민의 MCP Client와 최두나의 Repository·운영 조회 함수 내부를 직접 수정하지 않는다.**

첫 작업: `docs/plans/son.md`에 S1~S6 체크리스트를 적고 G0-1 PR을 만든다. 완료 시 자신의 보고서에 “누가 다음 행동을 결정하는지”를 실제 Trace로 설명한다.

#### 8.1.1 추가 구현사항 — 예약 승인·취소 Tool 연동 규정

- **소유 담당은 손영민**이다. 손영민은 `reserve_experience_program(program, time, headcount)` 변경 Tool의 Schema, allowlist, 상태 전이와 승인·취소 규칙을 Backend에 구현한다.
- 예약은 Backend 로컬 변경 Tool로만 실행한다. MCP Server에는 예약 Tool이나 예약 Bridge를 등록하지 않는다. MCP는 먹이시간·휴장·경로 등 조회 Tool만 제공한다.
- 변경 Tool은 승인 전 실행 금지, 서버 저장 Snapshot만 실행, 120초 만료, 세션 소유권, 원자적 `pending→processing`, 멱등키, 승인 시 정원 재확인 규칙을 따른다.
- 사용자의 `confirm/cancel`은 실행 승인 또는 취소이며, 관리자 업무 판정 `approve/reject`와 구분한다. 취소·만료·거절·정원 부족 상태를 성공으로 표시하지 않는다.
- 예약·취소 안내는 그대로 실행 규칙으로 하드코딩하지 않는다. 최두나가 출처와 확인일을 포함해 `reservation_policy_references`에 적재하고, 조회 Tool은 활성 버전만 근거로 반환한다. 참조 정책이 없거나 만료·비활성 상태면 임의로 승인/취소 가능 여부를 답하지 않는다.
- 이원민은 승인 API·Client와 사용자 승인/취소 화면을 담당한다. 이원민은 손영민이 제공한 상태 전이 계약을 변경하지 않는다.

### 8.2 최두나 — RAG·데이터·저장소·평가

| 순서   | 할 일                                                | 산출물                                       | 확인 방법                                                      |
| ------ | ---------------------------------------------------- | -------------------------------------------- | -------------------------------------------------------------- |
| C1     | Python 3.12.7·파일 경로·Settings·데이터 형식 확정 | requirements, config, .env.example, data     | 전원 같은 Python 버전·다른 현재 디렉토리에서도 경로 로딩 정상 |
| C2     | JSON 동물정보 100건 DB 적재·pgvector RAG            | migrations, document_repository, rag_service | JSON/DB 100건 대조, 벡터 생성, 대표 검색 근거 일치             |
| C3     | 서버 발급 세션과 Trace 저장                          | session/trace_repository                     | 임의 세션 거절, TTL, 다른 세션 분리                            |
| C4     | 근거·문서 주입·검색 장애 시험                      | tests/data, rag.json                         | A-01/11/14, 출처와 점수 검증                                   |
| C5     | 시나리오 파일을 읽는 평가기                          | eval_service, eval/run.py                    | 실제 API 기대 상태·Tool 비교                                  |
| C6     | 각자 시험 결과 취합                                  | docs/reports/choi.md                         | 전체 실행 수·PASS/FAIL/SKIP 구분                              |
| C7(P1) | 드림투어 참조 정책·Pending/예약/대화 저장소         | migration, policy/approval Repository        | 출처·버전, 원자적 claim, 정원·멱등성·세션 격리              |
| C8(P2) | 예약·Pending Action PostgreSQL 영속화               | db, pending_action/reservation_repository    | 재기동 후 상태·원자적 claim·멱등성 E2E                       |
| C9(P2) | 동물 이미지 Vision 분석 API                          | vision_service, tools_router                 | 파일 검증·Provider 오류·분석 응답 계약                       |

받는 것: 손영민의 공통 모델, 세 팀원의 시나리오와 시험 결과. 넘기는 것: 검색 함수·운영 조회 함수·데이터·Repository. G2에서는 손영민과 RAG 연결을 함께 검증한다. 평가 취합은 다른 사람의 테스트 파일을 직접 편집한다는 뜻이 아니다.

첫 작업: `docs/plans/choi.md`에 C1~C7, JSON 100건 목록, migration/rollback 순서를 작성한다. PostgreSQL 적재 대조 후 pgvector/RAG를 생성하며, Redis는 선택 확장으로 둔다.

`origin/test` 병합 이력 기준 P2 근거는 `91bba5c`(Vision 이미지 분석)와 `8cb9e6c`(예약·Pending Action PostgreSQL 영속화)이다. `9abbc07`과 `0ed9044`의 PostgreSQL/pgvector·티켓·코스 구현은 P1 완료 근거로 유지한다.

### 8.3 이원민 — MCP·프론트·조회 API 연결

| 순서    | 할 일                                      | 산출물                                           | 확인 방법                                    |
| ------- | ------------------------------------------ | ------------------------------------------------ | -------------------------------------------- |
| L1      | 수업의 HTTP MCP 연결을 동물원에 적용       | MCP Server/Client                                | tools/list의 이름·입력 Schema               |
| L2      | 순수 운영 함수를 wrapper로 등록            | mcp_server/tools/zoo_read                        | tools/call 3종 결과 계약                     |
| L3      | 기본 채팅·출처·Tool 카드                 | frontend                                         | Fake 응답으로 상태별 렌더링                  |
| L4      | Backend health/admin Trace Router          | routers, auth                                    | 관리자 토큰 미제공 차단                      |
| L5      | 실제 ask와 UI 연결                         | agent_client, frontend                           | N-01~N-04 화면 시연                          |
| L6      | MCP 장애·결과 변환·UI 오류               | tests/ui_mcp, mcp.json                           | A-03/14, 실패를 성공으로 표시하지 않음       |
| L7(P1)  | 승인 API·기존 카드 Client 계약 유지       | frontend/confirm client                          | 120초 만료·서버 판정 표시                   |
| L8      | 사용자·관리자 최소 로그인과 권한 분리     | auth Router/Repository, frontend, frontend_admin | 일반 사용자로 관리자 API 접근 시 403         |
| L9      | 관리자 Trace 조회 화면                     | frontend_admin, agent_client                     | 관리자 세션으로 Trace 조회·일반 사용자 차단 |
| L10(P2) | 관람객 정보 화면과 지도·코스 UX 확장      | app_pages, route_map, styles                     | 페이지 이동·경로 렌더링·빈/오류 상태 시험  |
| L11(P2) | 공지·환불·환경·음성·이미지 UI/API 연결 | app_pages, bootstrap, agent_client               | Backend 계약 재사용·기능별 실패 격리 시험   |

받는 것: 손영민의 모델·조회 함수·응답·예약 변경 Tool 계약, 최두나의 DB/Trace/Vision Repository·Service. 넘기는 것: MCP Client·Server·화면·Router·API Client 계약.

#### 8.3.1 로그인·관리자 권한 정책

- DB 계정은 일반 사용자 `TEST / 1234`와 관리자 `admin / 1234` 두 건만 사용한다. 두 값은 로컬 시연 전용이며 운영 자격증명으로 재사용하지 않는다.
- 회원가입·비밀번호 찾기·소셜 로그인은 만들지 않고, 복잡한 role/JWT 체계도 도입하지 않는다.
- `POST /api/auth/login`은 DB 값 일치 여부만 확인하고 응답에는 `user_id`, 최소 권한값(`user` 또는 `admin`), 서버 발급 로그인 세션만 반환한다.
- 로그인 성공 여부와 로그인 세션은 사용자 앱과 관리자 앱 각각의 Streamlit session에 저장한다.
- 비밀번호는 로그, Trace, API 응답, 오류 문구에 출력하지 않는다. 로그인 입력값은 성공 후 Streamlit session에서 제거한다.
- `/api/admin/reservations/*`와 관리자 Trace 화면은 관리자 세션만 허용한다. 일반 사용자 세션은 403으로 차단한다.
- 기존 `ADMIN_TOKEN` Bearer 방식은 자동화·P0 Trace API 호환을 위해 유지하되, 관리자 화면은 관리자 로그인 세션을 사용한다.

첫 작업: `docs/plans/lee.md`에 L1~L6을 작성한다. Backend 없이 MCP를 직접 호출하는 작은 테스트부터 만든다. 화면 단위 시험이 통과하면 실제 API와 연결한다.

### 8.4 각자 작성할 계획·보고 공통 양식

```text
담당자 / 브랜치:
수정할 파일(소유 범위):
작업 순서:
입력 계약 / 넘길 출력:
의존하는 상대 작업:
상대 구현 전 사용할 Fake:
완료 판단 테스트:
실행 결과(PASS/FAIL/SKIP, 실제 실행 일시):
처음 실패한 Trace와 수정 내용:
남은 일 / 제한사항:
```

## 9. Git 협업과 충돌 방지 규칙

문서만으로 충돌을 완전히 없앨 수는 없지만, **한 파일 한 수정자 + 계약 선병합 + 작은 PR**로 가능성을 줄인다. 아래 브랜치명은 이번 작업을 위해 정한 이름이다. 이 문서 작성 과정에서 브랜치나 원격 저장소를 생성하지 않았다.

| 구분                 | 규칙                                                                                                                                         | 담당·확인 방법                                              |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------ |
| 통합 책임            | 전체 통합 담당자를 한 명으로 두지 않고 연결 경계 담당자들이 공동 통합한다.`main.py` 조립은 손영민이 맡되 전체 기능의 단독 책임자는 아니다. | 최두나가 P0 평가 결과 취합                                   |
| 작업 폴더            | 같은 PC 폴더에서 브랜치를 바꾸며 동시에 작업하지 않는다. 개인별 clone을 사용하고, 동일 PC에서도 사람별 별도 clone을 사용한다.                | 작업 시작 전 저장소 경로 확인                                |
| 파일 소유권          | 파일 소유자만 해당 파일을 수정한다. 상대 함수가 필요하면 자기 테스트에 Fake를 두고 계약 변경을 요청한다.                                     | PR의 수정 파일 목록과 6장 대조                               |
| 공통 Schema          | 손영민이 작성하고 소비 담당자가 리뷰한 뒤 구현보다 먼저 병합한다. 필드명 변경을 개인 브랜치에만 두지 않는다.                                 | 계약 PR 선병합 후 최신 main 반영                             |
| 설정·데이터·의존성 | `.env.example`, config, 운영 JSON, 공통 Python 버전과 requirements 변경은 최두나에게 요청한다. `.env`는 커밋하지 않는다.                 | 새 의존성의 이름·용도 전달                                  |
| PR 크기              | 계약·데이터·기능·시험 중 이해 가능한 작은 단위로 나누고 자기 소유 파일만 stage한다.                                                       | `git diff --cached`로 확인                                 |
| 최신화               | 자기 커밋 후`git fetch origin`, `git merge origin/main`으로 최신 변경을 가져온다.                                                        | 공유 브랜치 rebase·force push 금지                          |
| 충돌 해결            | 파일 소유자가 양쪽 변경 의도를 확인해 해결한다. 전체 파일을 무조건 ours/theirs로 덮지 않는다.                                                | 공통 계약 충돌은 손영민과 모든 소비자가 공동 해결            |
| 병합 후 검증         | 연결 담당자가 자기 연결 시험을 실행하고 깨진 흐름을 다음 기능보다 먼저 복구한다.                                                             | 손영민: 정책/Runtime, 최두나: 결과 취합, 이원민: MCP/UI 회귀 |
| PR 필수 기록         | 변경 목적, 소유 범위, API·함수 계약 변경, 실행 명령과 결과, 선행 PR, P0 영향을 기록한다.                                                    | 상대 파일 변경은 소유자의 별도 PR로 분리                     |

**병합 검토 역할:** 손영민의 계약/Agent PR은 이원민이 API·화면 소비 계약을, 최두나가 RAG·데이터 소비 계약을 확인한다. 최두나의 PR은 손영민이 Runtime 연결을, 이원민이 MCP 데이터 사용을 확인한다. 이원민의 PR은 손영민이 API 계약을, 최두나가 운영 데이터·Trace 사용을 확인한다. 검토자는 파일의 새 소유자가 되지 않는다.

## 10. 테스트·시연·완료 기준

### 10.1 Case와 담당 연결

| Case             | 단계 | 확인할 핵심 결과                                                                   | 주담당                             |
| ---------------- | ---- | ---------------------------------------------------------------------------------- | ---------------------------------- |
| N-01             | P0   | 동물 지식 답변 + 실제 출처 + 점수 ≥ 0.5                                           | 최두나                             |
| N-02~04          | P0   | 먹이시간·휴장·경로가 Mock 원본과 일치, MCP 실제 호출                             | 이원민                             |
| A-01             | P0   | 점수 0.3/빈 검색 →`completed`, 확인 불가 안내                                   | 최두나                             |
| A-02             | P0   | 출발·목적지 부족 →`needs_clarification`, 경로 실행 0회                         | 손영민                             |
| A-03             | P0   | MCP timeout 재시도 1회 후`error`, 시간 추측 없음                                 | 이원민(정책 연동 손영민)           |
| A-04             | P0   | 미허용 Tool →`rejected`, MCP 실행 0회                                           | 손영민                             |
| A-05             | P0   | `find_habitat_route(current=123, destination="해양관")` 등 strict 인자 오류 차단 | 손영민                             |
| A-09/10/12       | P0   | 결제·비밀 출력·동물 질병 확진 거절                                               | 손영민                             |
| A-11             | P0   | 문서 속 지시문 미실행, 키/토큰 미노출                                              | 최두나(정책 연동 손영민)           |
| A-13             | P0   | 같은 이름·인자 3번째 실행 전`stopped`                                           | 손영민                             |
| A-14             | P0   | MCP/검색 저장소 예외 →`error`, 허위 성공 없음                                   | 이원민/최두나 각각                 |
| N-06/07, A-06~08 | P1-A | 승인·거절·만료·동시 승인·중복·실행 실패                                       | 손영민, 저장소 최두나, 화면 이원민 |
| A-08b            | P1-A | 세션 B의 세션 A action 확인을 차단, 예약 0건·Audit 기록·원래 action 보존         | 손영민/최두나                      |
| N-05/08          | P1-B | 시간 이내 코스, 세션 Memory 반영·격리                                             | 손영민/최두나                      |
| DB-01            | 필수 | 유효 JSON 동물정보 100건과 PostgreSQL 적재 100건 일치, 중복/null 0건               | 최두나                             |
| DB-02            | 필수 | 100건 기반 pgvector 생성·인덱스·대표 RAG 검색 출처 일치                          | 최두나/손영민                      |
| RP-01            | P1-A | 정책의 출처·확인일·활성 버전이 Tool 결과와 화면에 표시                           | 최두나/손영민/이원민               |
| UI-01            | P2   | 사용자 정보 화면과 관리자 Trace·지도·음성·이미지 화면의 정상/빈/오류/권한 상태  | 이원민/손영민/최두나               |

추가 경계 시험: LLM 7회째 차단, Tool 9회째 차단, 90초 deadline, MCP 결과 JSON 오류, 관리자 토큰 누락, 임의 세션 입력. 실제로 90초/120초 기다리지 않고 테스트용 clock/짧은 설정을 주입한다.

### 10.2 세 종류의 시험을 구분한다

- **단위 시험:** Scripted Mock Provider와 Fake 의존성으로 오류·반복·정책을 결정적으로 유도한다. 외부 네트워크 없이 반복한다.
- **로컬 연결 시험:** 실제 MCP/Backend 프로세스를 띄우고 HTTP/MCP를 통과시킨다. 로컬 통신이므로 네트워크 없는 단위 시험과 구분한다.
- **실제 LLM 시연:** `APP_MODE=openai`로 N-01~04를 실행하고 Model→Tool→Result→Model Trace를 저장한다. 표현은 달라도 근거·도구·상태가 맞는지 평가한다. LLM 키가 없으면 이 항목은 SKIP/미완료로 기록하며 Mock 통과를 실제 AI 판단 검증이라고 쓰지 않는다.

Mock Provider는 시나리오별로 다음 응답을 반환하는 테스트 대역이다. 안전 검사를 통과하도록 답만 하드코딩한 제품이라고 설명하지 않는다. 실제 Provider도 같은 Runtime과 Executor를 통과해야 한다.

### 10.3 평가 파일 계약

```json
{
  "id": "N-02",
  "priority": "P0",
  "message": "지금 펭귄 먹이시간이야?",
  "expected": {
    "status": "completed",
    "required_tools": ["get_feeding_schedule"],
    "forbidden_tools": [],
    "min_sources": 0
  }
}
```

각 시나리오 파일은 위 객체의 배열이다. 정밀 결과값·호출 횟수·장애 주입은 담당 단위 시험에서 검증한다. 평가기는 문장 전체 일치 대신 상태·Tool·출처·필수 결과를 비교하고 실제 응답을 증거로 남긴다. LLM Judge는 추가하지 않는다.

보고서에는 실행 일시·모드·모델·사용한 Git commit·명령·예상/실제 결과·Trace를 적는다. 샘플 보고서에 나오는 `waiting_approval`/`actor_id`를 그대로 옮기지 않는다. 이 프로젝트의 `confirmation_required`/서버 세션 계약으로 바꾼다.

### 10.4 P0 완료 체크리스트

- [ ] Backend/MCP/Streamlit이 각자 터미널에서 실행된다.
- [ ] 정상·비정상 Case와 DB-01/02, RP-01, UI-01을 시험한다.
- [ ] 세 운영 Tool이 실제 별도 MCP 프로세스로 호출된다.
- [ ] RAG 출처·점수·근거 없음 처리가 화면에서 확인된다.
- [ ] Model이 Tool 결과를 받아 다음 행동/종료를 판단한 실제 시연 증거가 있다.
- [ ] 모든 실행 한도·허용 도구·필수 인자 검증이 Backend에서 적용된다.
- [ ] 팀원 세 명이 최신 test를 받아 동일 절차로 실행한다.
- [ ] 실행 방법·실패/미구현·Mock 범위가 보고서에 기록되어 있다.

## 11. P1 예약·Memory 구현 계약

P0에서는 이 장의 코드를 미리 완성할 필요가 없다. 구현할 때 세 담당자가 같은 계약을 사용하도록 미리 정한다.

### 11.1 예약 호출과 저장 위치

- Model에는 `reserve_experience_program(program, time, headcount)`만 제시한다. 위험도는 `change`.
- 필수 값이 없으면 `needs_clarification`. 정원 확인은 승인 Service 내부 조회로 수행하고 별도 `draft` Tool을 만들지 않는다.
- `program`은 등록 프로그램, `time`은 timezone 포함 시각, `headcount`는 strict 정수 1~10. Mock 프로그램 정원은 10명으로 시작한다.
- 예약은 **Backend 로컬 변경 Tool로만 실행**한다. MCP 예약 Bridge는 이번 P1에서 만들지 않는다. 조회는 MCP, 예약 변경은 승인된 Backend 경로 하나로 책임을 고정한다.
- Pending Action·예약·Memory는 Backend 한 프로세스에 저장한다. MCP와 Backend의 메모리가 공유된다고 가정하지 않는다.

### 11.2 Pending Action과 confirm

저장 필드: `action_id, run_id, session_id, pending_call{name,arguments}, summary, risk, approval_status, expires_at, idempotency_key, approved_at, result`.

`approval_status`: `pending/processing/completed/rejected/expired`. `approved`는 승인 시각 `approved_at`으로 기록하고 별도 장기 대기 상태로 사용하지 않는다. `idempotency_key=session_id+":"+action_id`이며 클라이언트/LLM이 정하지 않는다.

```json
{
  "session_id": "server_issued_example",
  "action_id": "pa_example",
  "decision": "approve"
}
```

`decision`은 `approve/reject`. 새 Tool 이름·인자는 받지 않는다. ask/confirm 응답의 `pending_action`은 `action_id,run_id,tool_name,risk,summary,approval_target,expires_at`만 공개한다. 내부 상태·멱등키는 노출하지 않는다.

1. 요청 세션의 유효성을 검증하고 저장된 소유 세션과 대조한다. 불일치면 403, 다른 사람의 action 상태를 변경하지 않고 Audit에 기록한다.
2. action 존재·TTL·`pending` 상태·현재 Allowlist·저장 인자를 검증한다.
3. 거절이면 원자적으로 `pending→rejected`. 승인과 취소가 동시에 와도 하나만 성공한다.
4. 승인 시 원자적으로 `pending→processing`을 claim한다. 단순 `get()` 후 `set()` 두 단계로 구현하지 않는다.
5. 저장 Snapshot으로만 예약 실행. 서버에서 정한 멱등키를 실행 컨텍스트로 전달한다. Model 입력 Schema에는 이 키가 없다.
6. 예약 Repository는 lock 안에서 멱등키 확인·정원 재확인·생성을 수행한다. 성공 후 `completed`, 실패는 결과와 사유를 저장하고 `rejected`로 종결한다. 시스템 장애 응답은 `error`, 정원 부족 응답은 `rejected`다.
7. 소비된 action 재확인은 `rejected`; 결과를 새 예약으로 재실행하지 않는다. 변경 Tool의 자동 재시도는 하지 않는다.

최두나 공개 함수: `create(action)`, `claim(action_id, session_id, now)`, `reject(action_id,session_id,now)`, `complete(action_id,result)`, `fail(action_id,result)`. `claim`은 검증+상태 전환을 같은 lock에서 처리한다. Backend는 worker 1개로 실행한다. 프로세스 재시작 시 상태가 사라지는 로컬 Mock 한계를 보고한다.

프론트는 내용·확인·취소·120초 남은 시간·처리 중 버튼 잠금·만료 안내를 구현한다. 화면 타이머는 안내용이고 유효성 최종 판정은 Backend가 한다. 정원이 승인 사이에 소진되면 완료라고 표시하지 않는다.

### 11.3 세션과 Memory

- P0 세션은 서버가 추측하기 어려운 토큰으로 생성하고 등록 여부를 검증한다. 유효기간 2시간, 프로세스 재시작 시 소멸. 세션 ID는 게스트 세션 접근 비밀값으로 취급하며 일반 로그·공유 보고서에서 마스킹한다.
- P0 세션 저장은 ID 유효성/Trace 연결용이며 대화 Memory가 아니다. Trace는 세션당 최근 20개 실행을 유지하고 세션 만료 시 제거한다.
- P1 Memory는 세션당 최근 10개 메시지(최대 5왕복)와 관람 조건만 유지한다. 다른 세션 메시지를 합치지 않는다. 실제로 저장된 내용만 이전 대화로 언급한다.
- 장기 사용자 Profile·개인정보 저장은 추가하지 않는다. Redis로 바꾸려면 이 메모리 Repository 계약을 유지하고 별도 PR로 진행한다.

### 11.4 P1-B 추가 분담

| 기능      | 담당과 파일                                                                                                                                                                                                           | 고정할 계약·시험                                                                                                                                                                                                                   |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 티켓 조회 | 최두나`tools/zoo_tools.py`, 이원민 `mcp_server/tools/zoo_read.py`, 최두나 `data/operations/tickets.json`                                                                                                        | `lookup_ticket_scope(ticket_type: str)` → 공통 봉투의 `data={ticket_type,included,excluded}`                                                                                                                                   |
| 날씨 조회 | 최두나`tools/zoo_tools.py`(Open-Meteo API 연동), 이원민 `mcp_server/tools/public_data.py`                                                                                                                         | `lookup_public_weather(region: str="서울")` → `data={region,condition,indoor_recommended,as_of}`. TTL 10분 캐시, 실패·timeout이어도 코스 추천은 중단하지 않음                                                                 |
| 세션 대화 | 최두나`repositories/session_memory_repository.py`, 손영민 Orchestration Service                                                                                                                                     | `get_recent_messages(session_id)`, `append_messages(session_id,messages)`; 세션별 10개 제한·격리 시험                                                                                                                          |
| 맞춤 코스 | 최두나`tools/zoo_tools.py`(`get_course_info`/`get_indoor_course_info`/`get_outdoor_course_info`, `data/operations/course_profiles.json`), 손영민 Runtime의 날씨 선조회·Allowlist 좁히기·지침, 이원민 화면 | 휴장 제외 후 이동+관람 시간을 그리디로 합산해 입력 시간 이내 코스만 반환(시간 내 없으면`stops=[]`). 비/악천후면 Runtime이 `get_indoor_course_info`만 Allowlist에 남기고, 실외 명시 요청 시에만 `get_outdoor_course_info` 사용 |

P1 Tool의 Schema·Allowlist 추가는 손영민이 먼저 병합한다. 코스 관람 시간의 Mock 기준은 최두나가 시설 데이터에 추가한다. N-05는 총 120분 이내, N-08은 실제 저장된 이전 조건 반영을 검증한다. P1 개발 중 위 공통 출력에 추가 필드가 필요하면 9장 계약 변경 규칙을 적용한다.

## 12. 개발 환경과 실행 계획

공통 Python 버전은 **3.12.7**로 고정한다. FastAPI, Pydantic, Streamlit, httpx, python-dotenv, pytest, OpenAI SDK, MCP SDK를 이 버전에서 함께 사용한다. MCP 의존성 범위는 수업 `requirements.txt`의 `mcp>=1.27,<2`를 출발점으로 사용한다. 다른 라이브러리까지 이 문서에서 임의의 최신 버전을 보장하지 않는다. Gate 0에서 Python 3.12.7 설치와 import를 확인한 뒤, 최두나가 공통 `requirements.txt`와 하위 requirements 파일에 검증한 의존성 버전을 고정한다.

`OPENAI_MODEL` 기본 후보는 수업 코드의 `gpt-4.1-mini`를 그대로 사용한다. 최신/최적 모델이라는 뜻이 아니다. 실제 계정에서 사용 가능한지 G3에서 확인하고 불가하면 환경변수만 바꾸며 시험 모델을 기록한다. 수업 구조를 적용한 계획이며 이 문서 작성 중 API 호출·패키지 설치를 실행하지 않았다.

### 12.1 .env.example에 둘 설정

```dotenv
# Zoo Visit Guide AI Agent - 환경 변수 예시 (값 없는 키 목록 + 안전한 기본값)
# 실제 값은 .env로 복사한 뒤 채운다. .env는 커밋하지 않는다.

# 실행 모드: mock(결정적 테스트) | openai(실제 LLM 시연)
APP_MODE=openai
STORAGE_MODE=persistent

# P1: pgvector/Redis 전환 (STORAGE_MODE=persistent일 때만 필요)
DATABASE_URL=postgresql://zoo:zoo@192.100.200.239:5432/zoo
REDIS_URL=redis://192.100.200.239:6380/0
SESSION_MEMORY_MAX_TURNS=6
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_RETRY_COUNT=1

# OpenAI Provider (APP_MODE=openai일 때만 필요)
OPENAI_MODEL=gpt-4.1-mini
OPENAI_API_KEY=

# 관리자 Trace 조회 인증 (미설정 시 /api/admin/trace 차단)
ADMIN_TOKEN=

# MCP 서버 연결 (조회 Tool 3종은 이 서버를 통해 호출)
MCP_SERVER_URL=http://192.100.200.199:8100/mcp
#MCP 서버를 가동하는 인원을 제외한 다른 인원은 MCP_HOST,MCP_PORT 를 주석처리 할것.
MCP_HOST=127.0.0.1
MCP_PORT=8100

# Backend 자체 주소 (프론트/평가기가 참조)
BACKEND_URL=http://192.100.200.198:8000

# RAG 설정
RAG_TOP_K=3
RAG_MIN_SCORE=0.5

# Runtime 실행 한도 (Agent Runtime 가드레일)
MAX_AGENT_STEPS=6
MAX_SAME_TOOL_CALLS=2
MAX_TOOL_CALLS=8
RUN_TIMEOUT_SECONDS=90
MCP_TIMEOUT_SECONDS=10
MCP_RETRY_COUNT=1

# P1: 예약 승인/세션
PENDING_TTL_SECONDS=120
SESSION_TTL_SECONDS=7200

# 교육용 Mock 데이터의 "지금" 기준 시각 (비우면 Asia/Seoul 현재 시간 사용)
# 승인 TTL/세션 TTL/전체 timeout에는 적용하지 않음 (실제 시계 사용)
DEMO_NOW=2026-09-05T13:00:00+09:00

# ---------------------------------------------------------------------------
# 아래는 test 브랜치에 있던 값이다. 이 프로젝트(Zoo Visit Guide)와 무관해 보이는
# 이름(mini_agent_travel, 카카오/올라마/날씨 API 등)이 섞여 있어 실제로 어떤 기능이
# 이 값을 쓰는지 코드에서 다시 확인이 필요하다 — 병합 시 임의로 지우지 않고
# 남겨만 둔다.
# ---------------------------------------------------------------------------
GEMINI_API_KEY=
GEMINI_MODEL=gemini-3.6-flash
PYTHON_VERSION=3.12.7
LLM_PROVIDER=openai
LLM_FALLBACK_ENABLED=false
LLM_FALLBACK_PROVIDER=mock
KMA_SERVICE_KEY=
PGVECTOR_COLLECTION=travel_documents
RAG_COLLECTION=mini_agent_travel
RAG_CACHE_TTL_SECONDS=300
REDIS_TTL_SECONDS=1800
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=llama3.2
OLLAMA_EMBEDDING_MODEL=embeddinggemma
BACKEND_API_URL=http://192.100.200.198:8000
REQUEST_TIMEOUT_SECONDS=60
WEATHER_MODE=open_meteo
OPEN_METEO_BASE_URL=https://api.open-meteo.com
OPEN_METEO_GEOCODING_URL=https://geocoding-api.open-meteo.com
KAKAO_REST_API_KEY=
```

`DEMO_NOW`는 교육용 먹이 일정의 “지금” 기준이다. 비워 두면 Asia/Seoul 현재 시간을 쓴다. 조회 시각 `retrieved_at`은 실제 조회 시각이고 `data.as_of`는 일정 계산 기준이다. 승인 TTL·세션 TTL·전체 timeout에는 `DEMO_NOW`를 적용하지 않는다. 그렇지 않으면 데모 시간이 멈춰 승인도 만료되지 않을 수 있다.

개발자는 `.env.example`을 `.env`로 복사하고 필요한 값을 넣는다. 토큰 기본값을 저장소에 넣지 않는다. Config는 `__file__` 기준으로 프로젝트 루트의 `.env`와 데이터 경로를 찾는다.

### 12.2 구현 후 사용할 명령

아래 명령은 Gate 0 이후 담당자가 구현하여 제공해야 하는 실행 계약이다. 각자 프로젝트 루트에서 실행한다.

```bash
python3.12 --version  # Python 3.12.7이어야 함
python3.12 -m venv .venv
source .venv/bin/activate
python --version      # Python 3.12.7이어야 함
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows에서는 `py -3.12 --version`으로 Python 3.12.7인지 먼저 확인한 뒤, `py -3.12 -m venv .venv`를 사용한다. 가상환경 활성화 명령은 `.venv\Scripts\Activate.ps1`이다.

```bash
# 터미널 1: MCP
python -m mcp_server.server

# 터미널 2: Backend (각 터미널에서 가상환경 활성화)
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --workers 1

# 터미널 3: 화면
python -m streamlit run frontend/app.py --server.port 8501

# 단위 시험: 외부 API·로컬 프로세스 불필요
python -m pytest tests/agent tests/data tests/ui_mcp -m "not integration and not live"

# 로컬 프로세스 연결 시험: MCP/Backend 실행 필요
python -m pytest tests/integration -m integration

# 시나리오 평가: 위 Backend를 HTTP로 호출
python -m eval.run --base-url http://127.0.0.1:8000
```

실제 LLM 시연은 `.env`에서 `APP_MODE=openai`로 변경하고 Backend를 재시작한다. 키가 없거나 Provider가 실패하면 명시적으로 오류를 보여주고 Mock으로 조용히 대체하지 않는다. 기본 단위 시험은 유료 API를 호출하지 않는다.

## 13. 추가 결정 사항 보고와 보정

사용자 요청에 따라 아래 미정 사항을 초보자의 구현·수업 이해·충돌 예방을 기준으로 정했다. 새 승인 절차를 요구하는 목록이 아니라 **이번 작업지시서에 적용한 결정 기록**이다.

| 번호 | 결정                                                       | 이유/기준과 관계                                                             |
| ---- | ---------------------------------------------------------- | ---------------------------------------------------------------------------- |
| D01  | 손영민·최두나·이원민 3인 분담, 단계별 공동 통합          | 실제 test 병합 이력에 맞춰 구현·검증 책임을 정리                            |
| D02  | 순수 Python 단일 Runtime, LangGraph·다중 Agent 제외       | v3 단일 Agent와 수업 06 Python Loop 직접 적용                                |
| D03  | Streamlit·동기 HTTP·PostgreSQL로 기준 전환               | 회의 결정에 따라 JSON을 DB에 적재하고 pgvector/RAG의 단일 검색 원본으로 사용 |
| D04  | 운영 조회 3종 모두 Streamable HTTP MCP                     | v3 최소 조건 충족, 이중 로컬/MCP 경로 방지                                   |
| D05  | OpenAI는 수업 어댑터, Mock은 테스트 모드로 구분            | 실제 AI 판단 증거와 반복 가능한 시험 모두 확보                               |
| D06  | RAG는 로컬 준-Tool, 최종 생성은 Runtime의 Provider 한 곳   | 사전 분류기와 별도 RAG LLM 중복 호출 제거                                    |
| D07  | 동물정보 JSON 100건·pgvector 검색·명시적 점수 규칙       | DB 적재 검증과 RAG 근거 검증을 분리해 완료 판정                              |
| D08  | 서버 발급 세션은 ask에서 시작, 추가 세션 API 없음          | v3 3개 P0 API 유지, 프론트 임의 세션 방지                                    |
| D09  | 기존 관리자 인증 계약 유지, Trace UX는 손영민·이원민 담당 | 기존 API 호환을 유지하며 관리자 화면·로그·이력 조회를 확장                 |
| D10  | 예약은 P1 Backend 로컬 변경 Tool, MCP Bridge 제외          | 승인 API 순환·중복 저장 책임 제거                                           |
| D11  | 조회 timeout 1회 재시도, 한도·전체 deadline 공통 관리     | 작업지시서의 모호한 “최대 2회 재시도” 교체                                 |
| D12  | 파일 소유권·Gate 0·작은 PR·개인 clone                   | 내용 충돌과 브랜치 간 작업 오염 방지                                         |
| D13  | 데모 일정 시각과 실제 TTL 시계 분리                        | 언제 시연해도 일정 재현, 만료 로직 정상 유지                                 |
| D14  | P0 Memory 없음, 추가 질문은 완성형 재입력                  | v3 무상태 범위 안에서 초보 구현 부담 제한                                    |
| D15  | 공통 응답에 run/session/종료 사유 추가                     | v3 State 필드를 API로 노출하여 UI·평가 연결                                 |
| D16  | 공통 Python 3.12.7 사용                                    | 팀원의 실행 환경·의존성·시험 결과를 같게 유지                              |
| D17  | 드림투어 승인·취소 규정을 버전형 DB 참조 데이터로 저장    | Tool이 출처·확인일이 있는 활성 규정을 조회하고 정책 변경 이력을 보존        |
| D18  | P2 화면용 DB 변경은 최두나, API Client·화면은 이원민 담당 | migration·rollback·API 소비처를 기록하고 Schema 충돌을 방지                |

### 기준 문서/수업 예제의 불일치 보정

| 발견 사항                                                     | 이 문서의 적용                                                   |
| ------------------------------------------------------------- | ---------------------------------------------------------------- |
| MCP는 P0 필수인데 17.1 테스트 표는 P1                         | MCP 발견·호출·장애 시험을 P0로 배정                            |
| T-A05 P0 예시가 P1 예약`headcount`를 사용                   | P0는 경로 인자 타입 오류, headcount 시험은 P1에 추가             |
| Profile 코드 예시에`allowed_rag_collections` 누락           | 7.4절 요구를 따라 Profile 필드로 추가                            |
| 전체 Tool 8회 초과 시 상태가 명확하지 않음                    | 부분 근거와`stopped`, `termination_reason=max_tool_calls`    |
| `startup_error`, `invalid_tool_call` 등이 상태명처럼 보임 | 6개 RunStatus만 유지, 상세 원인은 종료 사유/오류 코드            |
| 승인 도식의 세션 불일치 분기가 action 거절로 이어질 수 있음   | 다른 세션 요청만 거절하고 원래 action은 변경하지 않음            |
| 수업의 max_steps는 최초 호출 이후 Tool 라운드 기준            | v3의 LLM 총 6회를 따르며 최초 호출 포함, 마지막 허용 응답도 검사 |
| 수업의`failed`, `waiting_approval`, `actor_id`          | v3 상태와 검증된 서버 세션으로 교체                              |
| 수업 0826 예제는 근거 없는 경우 일반 지식 fallback            | 이 프로젝트는 근거 없는 사실 생성 금지                           |
| 수업 메모리 set 예제는 동시성과 재시작 보장 없음              | P1 단일 프로세스 lock·원자적 claim, 재시작 한계 명시            |

## 14. 체크리스트

- [ ] 전원: 이 문서 1~6장을 읽고 자신의 소유 파일 확인.
- [ ] 손영민: G0-1 공통 계약 PR, Runtime/Provider 뼈대 준비.
- [ ] 최두나: Python 3.12.7·requirements, PostgreSQL migration, JSON 100건 적재 대조, pgvector/RAG와 예약 정책 참조 데이터 준비.
- [ ] 이원민: MCP 연결·목록 조회·기존 화면/API Client 계약 준비.
- [ ] 전원: 자신의 `docs/plans/이름.md`에 8장 계획을 구체화.
- [ ] 전원: Gate 0 병합 후 Python 3.12.7과 같은 기준 commit에서 import 확인.
- [ ] 전원: 7.3절의 자기 연결 시험을 담당자와 함께 실행하고 Trace 확인.
- [ ] 전원: 자기 테스트에서는 Fake 사용, G2부터 실제 RAG/MCP/API 연결.
- [ ] 전원: P0 시험·실제 LLM 시연 증거 완료 후 P1 진행.

최종 제출물은 코드만이 아니라 **실행 가능한 P0, 각자 작업·시험 보고서, 실제 Trace, 수업의 판단/실행/근거/종료 경계를 설명할 수 있는 시연**이다.
