# 레인저 에이전트 — 프로젝트 실행 계획

동물원 AI 에이전트 팀 프로젝트의 실행 계획입니다. 이 문서 하나만으로 무엇을 만들고, 사용자가 그것을 어떻게 쓰고, 팀원 각자가 어떤 이름의 함수·API·폴더에 코드를 넣어야 하는지 확인할 수 있도록 self-contained하게 작성했습니다. 외부 폴더나 다른 자료를 찾아볼 필요 없이 이 문서만 보고 바로 작업을 시작할 수 있습니다.

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [시스템 아키텍처](#2-시스템-아키텍처)
3. [AI 에이전트 사용법](#3-ai-에이전트-사용법)
4. [공통 API 명세서](#4-공통-api-명세서)
5. [함수 / 모듈명 규약](#5-함수--모듈명-규약)
6. [디렉토리 구조](#6-디렉토리-구조)
7. [데이터 모델](#7-데이터-모델)
8. [빌드 순서](#8-빌드-순서)
9. [역할 분담](#9-역할-분담)
10. [다음 액션](#10-다음-액션)

---

## 1. 프로젝트 개요

### 문제 정의

동물사 앞에서 관람객이 스마트폰으로 궁금한 것을 물으면, **동물 생태·서식지 설명**은 근거 문서에서 찾아 답하고(RAG) **실시간 정보**(먹이시간, 임시휴장, 길찾기, 체험 예약)는 Tool을 호출해 정확한 값으로 답합니다(Tool Use). 하나의 에이전트가 두 경로를 자동으로 구분해야 하며, 예약처럼 상태를 바꾸는 요청은 사용자 확인을 거친 뒤에만 실행합니다.

### 필수 요구사항 (팀 논의 확정 사항)

| 영역 | 요구사항 |
|---|---|
| 프론트/백엔드 | 로그인, 어드민/사용자 권한 분리, SSE 스트리밍 응답, Redis, DB, LLM |
| AI Agent | 공공데이터 API 연동, Tool Use, MCP Server |
| Multimodal | 영상·사진(mov) 업로드, 음성(mp3) STT/TTS |
| System Architecture | 백엔드 / DB / MCP Server를 별도 프로세스로 분리 |
| RAG | pgvector 기반 |
| 개발 방법론 | MVP → Baseline 확보 → 추가 기능 분담 개발 |

### MVP 범위

- 로그인 없이도 조회형 질문(RAG + 조회 Tool)에 답할 수 있는 챗봇 1개 화면
- 예약처럼 상태를 바꾸는 액션 1개(`reserve_experience_program`)에 대한 사용자 확인 흐름
- RAG 문서 3종(동물 정보카드, 서식지 설명, FAQ) 인덱싱과 출처 표시
- 이후 스프린트에서 로그인/어드민, SSE, Multimodal, MCP Server 분리를 추가

---

## 2. 시스템 아키텍처

세 개의 독립 프로세스로 분리합니다. 이 저장소의 `mini_agent_03_tool` 실습에서 썼던 **Router는 정책을 갖지 않고, Service가 실행 순서와 정책을 소유하고, Tool은 하나의 동작만 한다**는 원칙을 그대로 따릅니다.

```
[Frontend: Streamlit/Next.js]
        │  HTTPS / SSE
        ▼
[Backend: FastAPI :8000]  ──────┐
   ├─ Router (HTTP 계약만)       │  DB 커넥션
   ├─ Routing Service            │
   ├─ RAG Service ── pgvector ───┘
   ├─ Reservation Service ── Redis (session, pending action TTL)
   ├─ Tool Registry / Executor
   └─ MCP Client ────────────┐
                              │ MCP (stdio/HTTP)
                              ▼
                    [MCP Server :8100]
                       ├─ 동물원 공공데이터 API 연동 Tool
                       └─ (선택) 백엔드와 동일한 Tool 재노출
```

### 요청 흐름 (핵심 1개 경로)

```
사용자 질문
  → POST /api/agent/ask
  → 경로 판단 (intent: rag | tool | both)
      ├─ rag  → RAG Service → pgvector 유사도 검색 → 근거 기반 답변
      └─ tool → Tool Registry → Tool 실행 (조회는 즉시, 상태 변경은 승인 필요)
  → 결과 검증 (근거 없음/실패 시 최대 2회 재시도)
  → 최종 응답 (출처 또는 조회 시각 포함) + SSE로 스트리밍 전송
```

예약처럼 상태를 바꾸는 Tool은 `07_human-approval-and-safety` 랩에서 배운 **Pending Action** 패턴을 그대로 씁니다: 조회 Tool로 가능 여부를 먼저 확인 → `pending_action` 발급(Redis, TTL 120초) → 사용자 확인 → 저장된 arguments로 상태 변경 Tool 실행. 확인 시 자연어를 다시 해석하지 않습니다.

---

## 3. AI 에이전트 사용법

### 3.1 관람객 사용 흐름

1. **접속** — 로그인 없이 챗봇 화면에 바로 진입합니다(관람객은 게스트 세션, `session_id`는 프론트가 발급해 로컬에 보관).
2. **질문 입력** — "판다관 어떻게 가?"처럼 자연어로 입력합니다. RAG로 갈지 Tool로 갈지는 백엔드가 자동으로 판단하며 화면에는 드러나지 않습니다.
3. **답변 수신** — 동물 지식 답변에는 출처 카드가, 실시간 정보 답변에는 조회 시각이 함께 표시됩니다. 응답은 SSE로 토큰 단위 스트리밍됩니다.
4. **승인이 필요한 요청 확인** — 체험 프로그램 예약처럼 상태를 바꾸는 요청은 에이전트가 내용을 요약해 보여주고, "확인" 버튼을 눌러야 `action_id`와 함께 `/api/agent/confirm`이 호출되어 실제로 실행됩니다.
5. **대화 유지** — 같은 세션 안에서는 이전에 물어본 동물사, 선호 동선을 Redis 세션 메모리로 기억합니다. 로그인한 사용자는 장기 선호를 DB에도 저장합니다.

### 3.2 대화 예시

```
관람객      물개 먹이 주기 다음은 언제야?
에이전트    다음 물개 먹이시간은 오늘 14:30, 해양관 2층 관람대예요.
            [TOOL · get_feeding_schedule · 조회 13:58 기준]

관람객      이 호랑이는 몇 살이고 어디서 왔어?
에이전트    이 개체는 6살 수컷으로, 2020년 서울대공원에서 이송되었어요.
            [RAG · 동물 개체 정보카드 #TG-014]

관람객      15시 사육사 체험 프로그램 예약해줘, 2명
에이전트    15:00 사육사 체험 · 2명으로 예약할까요? 확인을 누르면 진행돼요.
            [PENDING_ACTION · reserve_experience_program]
관람객      (확인 버튼 클릭)
에이전트    예약이 확정됐어요. 예약번호는 EXP-2603입니다.
```

### 3.3 운영자(어드민) 사용 흐름

1. `/admin` 경로로 로그인하면 관람객 화면과 분리된 대시보드로 진입합니다.
2. RAG 문서(동물 정보카드, 서식지 설명, FAQ)를 업로드하면 자동으로 chunk → 임베딩 → pgvector 저장까지 처리됩니다.
3. 회귀 평가 시나리오를 실행하고 통과율과 실패 사례를 확인합니다.
4. 최근 대화 Trace(경로 판단 → RAG/Tool → 검증 단계별 로그)를 조회해 오류 패턴을 점검합니다.

### 3.4 Multimodal 사용

- **사진**: 관람객이 동물 사진을 업로드하면 `/api/media/species-lookup`이 이미지를 분석해 가장 가까운 동물 개체 정보카드를 찾아 RAG 답변으로 연결합니다.
- **음성**: 마이크 입력을 mp3로 녹음해 `/api/media/stt`로 텍스트 변환 후 `/api/agent/ask`에 그대로 전달합니다. 응답은 `/api/media/tts`로 음성 파일을 받아 재생할 수 있습니다.

---

## 4. 공통 API 명세서

모든 엔드포인트는 `backend`(`:8000`)가 제공합니다. 인증이 필요한 요청은 `Authorization: Bearer <token>` 헤더를 사용합니다.

### 4.1 인증

| Method | Path | Request Body | Response | 설명 |
|---|---|---|---|---|
| POST | `/api/auth/login` | `{email, password}` | `{access_token, role}` | `role`은 `visitor` \| `admin` |
| POST | `/api/auth/logout` | — | `{ok: true}` | 토큰 무효화 |
| GET | `/api/auth/me` | — | `{user_id, role, name}` | 현재 세션 사용자 |

### 4.2 에이전트 (핵심 진입점)

| Method | Path | Request Body | Response |
|---|---|---|---|
| POST | `/api/agent/ask` | `AgentAskRequest` | `AgentAskResponse` |
| GET | `/api/agent/stream?session_id=` | — | `text/event-stream` (토큰 단위 SSE) |
| POST | `/api/agent/confirm` | `{session_id, action_id, confirmed: true}` | `AgentAskResponse` |

```jsonc
// AgentAskRequest
{
  "message": "판다관 어떻게 가?",
  "session_id": "guest-8f21",
  "arguments": {},          // 선택: Tool 인자를 프론트에서 미리 채운 경우
  "confirmed": false,
  "action_id": null
}

// AgentAskResponse
{
  "intent": "rag",                 // "rag" | "tool" | "both"
  "status": "completed",           // completed | needs_clarification | confirmation_required | rejected | error
  "final_answer": "판다관은 정문에서...",
  "sources": [{"doc_id": "HB-014", "title": "서식지 설명 PDF", "page": 3}],
  "tool_calls": [{"name": "find_habitat_route", "arguments": {...}, "result": {...}}],
  "pending_action": null,          // confirmation_required일 때만 채워짐
  "trace": [{"stage": "route_decision", "data": {...}}]
}
```

### 4.3 Tool 직접 호출 (관리자·테스트용, 내부적으로는 `/api/agent/ask`가 사용)

| Method | Path | Request | Response |
|---|---|---|---|
| GET | `/api/tools/feeding-schedule` | `?habitat=` | 다음 먹이시간, 장소 |
| GET | `/api/tools/closure-status` | `?habitat=` | 임시 휴장 여부, 사유 |
| GET | `/api/tools/habitat-route` | `?from=&to=` | 경로, 예상 소요 시간 |
| GET | `/api/tools/ticket-scope` | `?ticket_type=` | 야간개장·체험 포함 여부 |
| POST | `/api/tools/reserve-experience` | `{program, time, headcount}` | `pending_action` 발급 (승인 필요) |

### 4.4 RAG / 문서 관리 (admin)

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/admin/documents` | multipart file + `{doc_type}` | `{doc_id, chunk_count}` |
| GET | `/api/admin/documents` | — | 등록된 문서 목록 |
| DELETE | `/api/admin/documents/{doc_id}` | — | `{ok: true}` |
| POST | `/api/admin/scenarios/run` | `{scenario_id}` | 평가 통과/실패 결과 |
| GET | `/api/admin/trace?session_id=` | — | 세션별 전체 Trace |

### 4.5 Multimodal

| Method | Path | Request | Response |
|---|---|---|---|
| POST | `/api/media/stt` | multipart mp3 | `{text}` |
| POST | `/api/media/tts` | `{text}` | audio/mpeg (bytes) |
| POST | `/api/media/species-lookup` | multipart 이미지 | `{doc_id, confidence, animal_name}` |

### 4.6 헬스체크

| Method | Path | Response |
|---|---|---|
| GET | `/api/health` | `{status: "ok", db: "ok", redis: "ok", mcp: "ok"}` |

### 4.7 MCP Server (`:8100`, backend가 MCP Client로 호출)

| MCP Tool 이름 | 대응 공공데이터 / 내부 기능 |
|---|---|
| `mcp__zoo__get_feeding_schedule` | 동물원 자체 사육 스케줄 |
| `mcp__zoo__check_closure_status` | 동물원 자체 휴장 공지 |
| `mcp__zoo__find_habitat_route` | 동물원 내 경로 데이터 |
| `mcp__zoo__lookup_public_weather` | 공공데이터포털 기상 API (우천 시 대체 동선 판단용) |
| `mcp__zoo__reserve_experience_program` | 체험 프로그램 예약 시스템 (상태 변경, 승인 필요) |

---

## 5. 함수 / 모듈명 규약

레이어별로 파일과 함수 이름을 고정해, 팀원이 각자 브랜치에서 작업해도 이름이 충돌하지 않게 합니다.

### 5.1 `backend/app/agents/` — 자연어 해석만 담당 (승인·정책 결정 금지)

| 파일 | 함수 | 역할 |
|---|---|---|
| `routing_agent.py` | `classify_intent(message: str) -> IntentDecision` | rag / tool / both 판단 |
| `reservation_agent.py` | `extract_reservation_arguments(message: str) -> ReservationInput` | 예약 자연어 → 구조화 인자 |
| `rag_query_agent.py` | `rewrite_query_for_retrieval(message: str, history: list) -> str` | 검색용 질의 재작성 |

### 5.2 `backend/app/services/` — 실행 순서와 정책 소유

| 파일 | 함수 | 역할 |
|---|---|---|
| `agent_orchestration_service.py` | `handle_ask(request: AgentAskRequest) -> AgentAskResponse` | `/api/agent/ask`의 단일 진입점, 위 흐름 전체를 조립 |
| `rag_service.py` | `chunk_document(raw_text, doc_id) -> list[Chunk]` | PDF/텍스트 → chunk |
| `rag_service.py` | `embed_and_store(chunks: list[Chunk]) -> int` | 임베딩 후 pgvector 저장, 저장 개수 반환 |
| `rag_service.py` | `retrieve_chunks(query: str, top_k=5) -> list[Chunk]` | 유사도 검색 |
| `rag_service.py` | `answer_with_citations(question, chunks) -> RagAnswer` | 근거 기반 답변 생성, 근거 없으면 "모른다" |
| `reservation_service.py` | `check_capacity(program, time, headcount) -> CapacityResult` | 정원 확인 |
| `reservation_service.py` | `create_pending_action(lab_id, tool_name, arguments) -> PendingAction` | 승인 대기 발급 (Redis TTL) |
| `reservation_service.py` | `confirm_pending_action(action_id) -> ToolRunResult` | 저장된 인자로 실제 실행 |
| `eval_service.py` | `run_scenario(scenario_id) -> ScenarioResult` | 회귀 시나리오 실행 |

### 5.3 `backend/app/tools/` — 각 함수는 조회 또는 상태 변경 하나만

| 파일 | 함수 | 승인 필요 |
|---|---|---|
| `zoo_tools.py` | `get_feeding_schedule(habitat: str) -> FeedingSchedule` | 아니오 |
| `zoo_tools.py` | `check_closure_status(habitat: str \| None) -> ClosureStatus` | 아니오 |
| `zoo_tools.py` | `find_habitat_route(current: str, destination: str) -> RouteResult` | 아니오 |
| `zoo_tools.py` | `lookup_ticket_scope(ticket_type: str) -> TicketScope` | 아니오 |
| `zoo_tools.py` | `reserve_experience_program(program, time, headcount) -> ReservationResult` | **예** |
| `registry.py` | `get_tool_definitions() -> list[dict]` | Tool 이름·설명·input_schema 목록 (LLM Tool Calling에 그대로 전달) |
| `executor.py` | `execute_tool_safely(name: str, arguments: dict) -> ToolRunResult` | Allowlist 검사 + Pydantic 검증 + 표준 오류 |

### 5.4 `backend/app/repositories/` — 저장소 접근만, 업무 규칙 없음

| 파일 | 함수 | 저장소 |
|---|---|---|
| `session_repository.py` | `get_session(session_id)` / `append_message(session_id, message)` | Redis |
| `pending_action_repository.py` | `create(action) -> action_id` / `consume(action_id) -> PendingAction \| None` | Redis (TTL 120s) |
| `visitor_repository.py` | `get_profile(user_id)` / `upsert_preferences(user_id, prefs)` | PostgreSQL |
| `document_repository.py` | `insert_chunks(chunks)` / `similarity_search(embedding, top_k)` | PostgreSQL + pgvector |

### 5.5 `mcp_server/` — 독립 프로세스, 백엔드는 MCP Client로만 호출

| 파일 | 함수 | 역할 |
|---|---|---|
| `server.py` | `create_mcp_server() -> Server` | Tool 등록, stdio/HTTP 진입점 |
| `tools/public_data.py` | `lookup_public_weather(region: str) -> WeatherResult` | 공공데이터포털 API 연동 |
| `tools/zoo_bridge.py` | `reserve_experience_program(...)` | 백엔드 예약 API를 감싸 MCP Tool로 재노출 |

### 5.6 `frontend/` — 화면은 API 응답을 그대로 렌더링, 정책 판단 없음

| 파일 | 함수 | 역할 |
|---|---|---|
| `clients/agent_client.py` | `ask(message, session_id) -> AgentAskResponse` | `/api/agent/ask` 호출 |
| `clients/agent_client.py` | `confirm(session_id, action_id) -> AgentAskResponse` | `/api/agent/confirm` 호출 |
| `clients/agent_client.py` | `stream(session_id) -> Iterator[str]` | SSE 구독 |
| `clients/media_client.py` | `transcribe(audio_bytes) -> str` / `synthesize(text) -> bytes` | STT/TTS 호출 |

---

## 6. 디렉토리 구조

```
ranger-agent/
├─ plan.md                          # 본 문서
├─ docs/
│  ├─ architecture.md               # 2장 내용 상세화
│  └─ eval-scenarios.md             # 회귀 시나리오 정의
│
├─ backend/
│  ├─ app/
│  │  ├─ main.py                    # FastAPI 앱 생성 + 라우터 등록
│  │  ├─ core/
│  │  │  ├─ config.py                # 환경변수 (DB, Redis, MCP URL, LLM Provider 키)
│  │  │  └─ auth.py                  # JWT 발급/검증, role 확인 dependency
│  │  ├─ routers/
│  │  │  ├─ auth_router.py           # /api/auth/*
│  │  │  ├─ agent_router.py          # /api/agent/*
│  │  │  ├─ tools_router.py          # /api/tools/*
│  │  │  ├─ admin_router.py          # /api/admin/*
│  │  │  ├─ media_router.py          # /api/media/*
│  │  │  └─ health_router.py         # /api/health
│  │  ├─ schemas/
│  │  │  ├─ agent.py                 # AgentAskRequest/Response
│  │  │  ├─ tools.py                 # 각 Tool 입출력 모델
│  │  │  └─ common.py
│  │  ├─ agents/                     # 5.1
│  │  ├─ services/                   # 5.2
│  │  ├─ tools/                      # 5.3
│  │  ├─ repositories/               # 5.4
│  │  └─ mcp_client/
│  │     └─ client.py                # MCP Server 호출 Wrapper
│  ├─ tests/
│  └─ requirements.txt
│
├─ mcp_server/                       # 5.5, 백엔드와 별도 프로세스로 기동
│  ├─ server.py
│  ├─ tools/
│  │  ├─ public_data.py
│  │  └─ zoo_bridge.py
│  └─ requirements.txt
│
├─ ai-module/                        # (선택) 이미지 기반 동물 인식 등 무거운 추론 전용
│  ├─ api_server.py
│  ├─ species_recognition/
│  │  └─ pipeline.py                 # identify_species(image) -> SpeciesResult
│  └─ requirements.txt
│
├─ frontend/
│  ├─ app.py
│  ├─ app_pages/
│  │  ├─ 01_chat.py                  # 관람객 챗봇 화면
│  │  ├─ 02_admin_documents.py       # RAG 문서 업로드
│  │  ├─ 03_admin_trace.py           # Trace/평가 대시보드
│  │  └─ 04_voice.py                 # 음성 입출력
│  ├─ clients/
│  │  ├─ agent_client.py
│  │  └─ media_client.py
│  └─ core/
│     └─ api_client.py               # 공통 HTTP 요청 Wrapper
│
├─ data/
│  ├─ animal_cards/                  # 동물 개체 정보카드 원본
│  ├─ habitat_docs/                  # 서식지 설명 PDF
│  └─ faq/
│
└─ infra/
   ├─ docker-compose.yml             # backend, mcp_server, postgres+pgvector, redis
   └─ .env.example
```

---

## 7. 데이터 모델

### PostgreSQL (pgvector 포함)

| 테이블 | 주요 컬럼 |
|---|---|
| `users` | `id, email, password_hash, role(visitor\|admin), created_at` |
| `visitor_profiles` | `user_id, preferred_species_group, mobility_preference, updated_at` |
| `documents` | `id, doc_type, title, source_path, created_at` |
| `document_chunks` | `id, doc_id, content, embedding(vector), page, created_at` |
| `reservations` | `id, program, time_slot, headcount, status, confirmed_at` |
| `eval_scenarios` | `id, input, expected_outcome, last_result, last_run_at` |

### Redis

| Key 패턴 | 용도 | TTL |
|---|---|---|
| `session:{session_id}` | 대화 히스토리, 방문한 동물사 목록 | 관람 세션 종료까지 |
| `pending_action:{action_id}` | 승인 대기 중인 Tool 호출 인자 | 120초 |

---

## 8. 빌드 순서

| 단계 | 내용 | 담당 |
|---|---|---|
| 1 | **DB/Redis/환경 기동** — `infra/docker-compose.yml`로 postgres(pgvector 확장 포함), redis 기동. `backend/app/core/config.py` 환경변수 정리. | 최두나 |
| 2 | **RAG 파이프라인** — `document_repository.py`, `rag_service.py`(chunk → embed_and_store → retrieve_chunks → answer_with_citations) 구현 후 문서 3종으로 검증. | 최두나 |
| 3 | **Tool 함수 작성** — `zoo_tools.py`의 조회 Tool 4종을 Mock 데이터로 먼저 동작시키고 `registry.py` / `executor.py` 연결. | 손영민 |
| 4 | **에이전트 오케스트레이션** — `routing_agent.py` + `agent_orchestration_service.handle_ask()`로 rag/tool 경로 판단과 결과 검증(재시도 최대 2회) 연결. | 손영민 |
| 5 | **승인 흐름** — `reservation_service.py`의 `create_pending_action` / `confirm_pending_action`과 `/api/agent/confirm` 연결. | 손영민 |
| 6 | **인증 · 어드민** — `auth_router.py`, role 기반 접근 제어, 어드민 문서 업로드/Trace 화면. | 이원민 |
| 7 | **SSE 스트리밍** — `/api/agent/stream` 구현, 프론트 `agent_client.stream()` 연결. | 이원민 |
| 8 | **MCP Server 분리** — `mcp_server/`를 독립 프로세스로 기동하고 백엔드는 `mcp_client/client.py`로만 호출하도록 전환. | 이원민 |
| 9 | **Multimodal** — `/api/media/stt`, `/api/media/tts`, `/api/media/species-lookup` 추가. | 이원민 |
| 10 | **평가 시나리오** — `eval_service.run_scenario()`로 회귀 테스트 자동화, 3명 각자 담당 영역 시나리오 작성 후 통합. | 최두나 (취합) |

---

## 9. 역할 분담

3명이 나눠 맡되, 서로의 코드는 **6장 디렉토리 구조**의 파일 경계로만 접촉합니다 — 다른 사람 폴더의 함수를 직접 고치는 대신, 필요한 값은 정해진 함수 시그니처(5장)로 주고받습니다.

### 손영민 — 에이전트 · Tool

> 본인 희망 영역. 자연어를 어떤 Tool로 연결할지, Tool을 어떻게 안전하게 실행할지를 책임집니다.

| 구분 | 내용 |
|---|---|
| 포함 단계 | 3, 4, 5 |
| 소유 디렉토리 | `backend/app/agents/`, `backend/app/tools/`, `backend/app/services/agent_orchestration_service.py`, `backend/app/services/reservation_service.py` |
| 주요 함수 | `classify_intent()` · `extract_reservation_arguments()` · `get_feeding_schedule()` / `check_closure_status()` / `find_habitat_route()` / `lookup_ticket_scope()` / `reserve_experience_program()` · `get_tool_definitions()` · `execute_tool_safely()` · `handle_ask()` · `create_pending_action()` / `confirm_pending_action()` |
| 담당 API | `POST /api/agent/ask`, `POST /api/agent/confirm`, `GET/POST /api/tools/*` |
| 받는 입력 | 최두나가 만든 `retrieve_chunks()` / `answer_with_citations()` (RAG 결과), `document_repository`가 채운 pgvector 데이터 |
| 넘기는 출력 | `AgentAskResponse` (이원민의 SSE 스트리밍과 프론트가 그대로 사용) |

### 최두나 — RAG · 데이터 · 인프라

| 구분 | 내용 |
|---|---|
| 포함 단계 | 1, 2, 10(취합) |
| 소유 디렉토리 | `infra/`, `backend/app/repositories/`, `backend/app/services/rag_service.py`, `backend/app/services/eval_service.py`, `data/` |
| 주요 함수 | `chunk_document()` · `embed_and_store()` · `retrieve_chunks()` · `answer_with_citations()` · `insert_chunks()` / `similarity_search()` · `get_session()` / `append_message()` · `run_scenario()` |
| 담당 API | `POST/GET/DELETE /api/admin/documents`, `POST /api/admin/scenarios/run` |
| 넘기는 출력 | 손영민의 `routing_agent`가 호출하는 RAG 조회 함수, DB/Redis 커넥션(`core/config.py`) |

### 이원민 — 인증 · 어드민 · SSE · MCP · Multimodal · 프론트

| 구분 | 내용 |
|---|---|
| 포함 단계 | 6, 7, 8, 9 + 프론트 화면 전체(`frontend/`) |
| 소유 디렉토리 | `backend/app/core/auth.py`, `backend/app/routers/auth_router.py` / `admin_router.py` / `media_router.py`, `mcp_server/`, `backend/app/mcp_client/`, `frontend/` |
| 주요 함수 | `create_mcp_server()` · `lookup_public_weather()` · `reserve_experience_program()`(MCP bridge) · `ask()` / `confirm()` / `stream()`(`agent_client.py`) · `transcribe()` / `synthesize()`(`media_client.py`) |
| 담당 API | `POST /api/auth/*`, `GET /api/agent/stream`, `POST /api/media/*`, `GET /api/admin/trace` |
| 받는 입력 | 손영민의 `AgentAskResponse` 계약을 그대로 화면에 렌더링(정책 판단 없이 표시만) |

---

## 10. 다음 액션

- [ ] `infra/docker-compose.yml` 작성 (postgres+pgvector, redis, backend, mcp_server)
- [ ] 동물 정보카드·서식지 설명·FAQ 샘플 데이터 `data/`에 확보
- [ ] `backend/app/schemas/agent.py`에 `AgentAskRequest`/`AgentAskResponse` 확정 후 팀 공유
- [ ] Tool Mock 데이터 확정 (동물사 목록, 먹이 시간표, 체험 프로그램, 정원)
- [ ] `eval_scenarios` 4개 이상 작성 후 첫 회귀 테스트 실행
- [ ] MCP Server 최소 기동(`mcp_server/server.py`)과 backend `mcp_client` 연결 확인
