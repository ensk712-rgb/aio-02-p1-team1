# 레인저 에이전트 — 프로젝트 실행 계획 (v2, based on 개발계획서 v0.3.1)

동물원 AI 에이전트 팀 프로젝트의 실행 계획입니다. `동물원_관람_지원(Zoo_Visit_Guide)_AI_에이전트_개발_계획서_v03.md`(이하 "설계서 v0.3.1")의 재검토 결과를 반영해 범위와 역할을 다시 정리했습니다. 이 문서 하나만으로 무엇을 만들고, 사용자가 그것을 어떻게 쓰고, 팀원 각자가 어떤 이름의 함수·API·폴더에 코드를 넣어야 하는지 확인할 수 있도록 self-contained하게 작성했습니다.

> **v1 대비 주요 변경**: 로그인/권한 분리, SSE 스트리밍, Redis/pgvector, Multimodal(STT/TTS, 이미지)을 Day-1(P0/MVP) 범위에서 전부 제외했습니다. Day-1은 **단일 Agent(`zoo_guide`) + RAG + 조회 Tool 3종 + MCP 분리 + In-Memory 저장소**만으로 구성됩니다. 이 항목들은 P1(여유 시)로 미뤘고, 그마저도 SSE·STT/TTS는 P1에서도 "선택 사항"입니다. 이 변경 때문에 **9장 역할 분담이 P0가 아니라 P1 확장 작업 중심으로 다시 짜였습니다.**

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [설계 범위 (In/Out-of-Scope)](#2-설계-범위-inout-of-scope)
3. [시스템 아키텍처](#3-시스템-아키텍처)
4. [AI 에이전트 사용법](#4-ai-에이전트-사용법)
5. [공통 API 명세서](#5-공통-api-명세서)
6. [함수 / 모듈명 규약](#6-함수--모듈명-규약)
7. [디렉토리 구조](#7-디렉토리-구조)
8. [데이터 모델 · State · Trace](#8-데이터-모델--state--trace)
9. [빌드 순서 (Phase)](#9-빌드-순서-phase)
10. [역할 분담](#10-역할-분담)
11. [다음 액션](#11-다음-액션)

---

## 1. 프로젝트 개요

| 항목                 | 내용                                                                                                              |
| -------------------- | ----------------------------------------------------------------------------------------------------------------- |
| 프로젝트명           | 동물원 관람 지원 AI 에이전트(Zoo Visit Guide AI Agent)                                                            |
| Agent ID             | `zoo_guide` (단일 Agent, Multi-Agent/Handoff 없음)                                                              |
| 목적                 | 관람객 질문을 판단해 공식 문서를 검색하거나(RAG) 동물원 운영 Tool을 호출하고, 근거가 포함된 관람 안내를 제공한다. |
| 핵심 기능 (P0 = MVP) | 동물 정보 RAG, 먹이시간·휴장·경로 조회 Tool 3종                                                                 |
| 확장 기능 (P1)       | 티켓·날씨 조회, 맞춤 코스 안내, 예약 승인, 세션 Memory                                                           |
| Backend / Frontend   | FastAPI / Streamlit                                                                                               |
| Tool 연결            | Streamable HTTP MCP Server (별도 프로세스)                                                                        |
| 저장소 (Day-1)       | In-Memory. Redis/pgvector 전환은 P1                                                                               |
| 개발 방법론          | MVP(P0) → Baseline 확보 → P1 추가 기능 분담 개발                                                                |

### MVP(P0) 범위 — 이미 완료 대상, 아래 항목은 역할 분담에서 제외됨

- `zoo_guide` Agent Profile 1개 등록·실행
- RAG: 동물 정보카드 검색 (`RAG_MIN_SCORE=0.5`, `top_k=3`, 근거 없으면 "확인 불가" 안내)
- 조회 Tool 3종: `get_feeding_schedule`, `check_closure_status`, `find_habitat_route`
- MCP Server를 별도 프로세스로 분리해 최소 1개 이상 Tool 호출
- Trace(판단→검색/Tool→종료) 기록 및 응답 포함
- Streamlit 단일 화면(채팅, 출처, Tool 결과 표시), 동기 HTTP (SSE 아님)
- 반복/시간 제한 가드레일 (`MAX_AGENT_STEPS=6`, 동일 Tool·인자 반복 2회 제한, 전체 8회, 90초 timeout)
- 비정상 케이스 방어: Allowlist 위반 차단, 잘못된 arguments 차단, 결제/탈옥/의료진단 요청 거절 (A-01~A-05, A-09~A-14)
- `GET /api/health`, `POST /api/agent/ask`, `GET /api/admin/trace` 3개 API로 P0 시나리오 전량(N-01~N-04, A-01~A-05, A-09~A-14) 시연 가능

### 대표 요청

- `호랑이는 어디에서 살고 무엇을 먹어?` (P0)
- `지금 펭귄 먹이 주기 시간이야?` (P0)
- `정문에서 해양관까지 어떻게 가?` (P0)
- `5살 아이와 2시간 볼 수 있는 코스를 추천해 줘.` (P1)
- `오후 3시 사육사 체험을 2명 예약해 줘.` (P1)

---

## 2. 설계 범위 (In/Out-of-Scope)

### 2.1 P1 확장 대상 (여유 시, 역할 분담 대상)

| 영역           | 내용                                                                                                                      | 비고                                 |
| -------------- | ------------------------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| 조회 Tool 확장 | `lookup_ticket_scope`, `lookup_public_weather`                                                                        | MCP`tools/public_data.py`          |
| 개인화         | 아이 동반, 관람 시간, 이동 조건을 질문에 반영 (N-05)                                                                      | RAG + 복수 Tool 조합                 |
| 예약           | `reserve_experience_program` — 확인 후 실행, `session_id` 소유권 검증, TTL 120초, `pending→processing→completed` | Human Approval 흐름 (4.2절/12장)     |
| Memory         | 같은 세션의 최근 대화·관람 조건 유지 (N-08)                                                                              | In-Memory dict 우선, Redis는 그 다음 |

### 2.2 완전 제외 (Out-of-Scope, P1에도 원칙적으로 안 함)

| 제외 항목                                                             | 사유                                                                                                                                                |
| --------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- |
| 실제 결제, 최종 법률 판단, 동물 질병 진단, 시설 폐쇄·대피 명령       | 위험/권한 밖 — Tool 자체를 만들지 않음                                                                                                             |
| **SSE 실시간 스트리밍**                                         | Day-1 제외, P1에서도 선택 사항. 동기 HTTP로 대체                                                                                                    |
| **STT/TTS(음성), 이미지 기반 동물 인식**                        | 별도 Provider 연동 필요 — Day-1 제외, P1에서도 선택 사항                                                                                           |
| 로그인/회원 인증, 사용자·어드민 권한 분리                            | v0.2까지의 요구사항이었으나 v0.3.1에서 범위 축소. 관람객은 게스트 세션만 사용.`/api/admin/trace` 접근 통제는 최소 수준(토큰 등)으로만 P1에서 고려 |
| 실제 운영 예약 시스템, 장기 개인정보 저장, 다중 Agent 협업, 상용 배포 | 로컬 시연 범위 초과                                                                                                                                 |

---

## 3. 시스템 아키텍처

```
Streamlit Frontend
        ↓ HTTP (동기, P0)
FastAPI Agent Router
        ↓
Agent Service (agent_orchestration_service.handle_ask)
        ↓
Zoo Guide Agent Profile (agents/zoo_guide_agent.py)
        ↓
공통 Python Agent Runtime (agents/runtime.py)
   ├─ LLM Provider 호출
   ├─ 실행 State와 Trace
   └─ Tool Allowlist 검사
        ↓ Streamable HTTP
MCP Server (mcp_server/, 별도 프로세스)
        ↓
Mock 운영 데이터 (Day-1: In-Memory)
        ↘ (P1) PostgreSQL/pgvector, Redis
```

Router는 HTTP 계약만 갖고, Service가 실행 순서와 정책을 소유하며, Tool은 조회 또는 상태 변경 중 하나만 수행한다는 원칙은 유지합니다(`mini_agent_03_tool` 실습과 동일).

### 요청 흐름 (P0 핵심 경로)

```
사용자 질문
  → POST /api/agent/ask
  → Agent Runtime이 MCP tools/list → Allowlist 교집합만 LLM에 노출
  → LLM이 RAG 검색 또는 Tool 호출 제안
      ├─ 정적 지식  → RAG Service → 유사도 검색(RAG_MIN_SCORE 이상만 채택)
      └─ 실시간 정보 → Tool Allowlist·arguments 검증 → MCP tools/call
  → Tool Result를 LLM에 재전달 → 최종 답변 판단
  → RunStatus(completed/needs_clarification/rejected/stopped/error)로 종료
  → 응답 (출처 또는 Tool 조회 시각 + Trace 포함)
```

### 예약 승인 흐름 (P1)

조회 Tool로 가능 여부 확인 → `reserve_experience_program` 제안 감지 → 위험도 `change` 판정 → Pending Action 저장(`action_id`, **`session_id`**, arguments, TTL 120초) → `status=confirmation_required` → 사용자 확인 → `POST /api/agent/confirm`에 **`session_id`를 함께 전달** → 저장된 `session_id`와 일치 + `approval_status==pending` + TTL 이내일 때만 `processing`으로 전환 후 실행 → `completed`. `actor_id`는 게스트 환경에서 위조 가능하므로 소유권 판정에 쓰지 않고 `session_id` 하나로 통일합니다.

---

## 4. AI 에이전트 사용법

### 4.1 관람객 사용 흐름 (P0)

1. **접속** — 로그인 없이 챗봇 화면에 바로 진입. `session_id`는 프론트가 발급해 로컬에 보관(게스트 세션).
2. **질문 입력** — 자연어로 입력. RAG로 갈지 Tool로 갈지는 LLM+Runtime이 판단하며, 사전 분류 단계는 따로 두지 않고 `intent`는 사후 라벨링됩니다.
3. **답변 수신** — 동물 지식 답변에는 출처 카드(`doc_id`, `title`, `page`, `score`)가, 실시간 정보 답변에는 Tool 이름과 조회 시각이 함께 표시됩니다. 응답은 동기 HTTP(P0)로 한 번에 옵니다(SSE 아님).
4. **근거 부족 시** — RAG 유사도가 `RAG_MIN_SCORE` 미만이면 추측하지 않고 "공식 문서에서 확인할 수 없습니다"로 안내합니다.

### 4.2 승인이 필요한 요청 (P1)

체험 프로그램 예약처럼 상태를 바꾸는 요청은 에이전트가 내용을 요약해 카드로 보여주고, TTL(120초) 카운트다운 중 "확인" 버튼을 눌러야 같은 `session_id`로 `/api/agent/confirm`이 호출되어 실행됩니다. 타이머가 끝나면 백엔드 재요청 없이 화면이 스스로 "만료" 상태로 전환되어야 합니다.

### 4.3 대화 예시

```
관람객      물개 먹이 주기 다음은 언제야?
에이전트    다음 물개 먹이시간은 오늘 14:30, 해양관 2층 관람대예요.
            [TOOL · get_feeding_schedule · 조회 13:58 기준]

관람객      이 호랑이는 몇 살이고 어디서 왔어?
에이전트    이 개체는 6살 수컷으로, 2020년 서울대공원에서 이송되었어요.
            [RAG · 동물 정보카드 ANIMAL-TIGER · score 0.82]

관람객(P1)  15시 사육사 체험 프로그램 예약해줘, 2명
에이전트    15:00 사육사 체험 · 2명으로 예약할까요? (120초 이내 확인)
            [PENDING_ACTION · reserve_experience_program]
관람객      (확인 버튼 클릭)
에이전트    예약이 확정됐어요. 예약번호는 EXP-2603입니다.
```

### 4.4 운영자(어드민) 사용 흐름 (P0는 조회만)

- P0: `/api/admin/trace?session_id=`로 세션별 Trace(판단→RAG/Tool→종료)를 조회할 수 있습니다. 별도 로그인 화면은 만들지 않습니다.
- 문서 업로드·회귀 평가 대시보드는 이번 범위에서 만들지 않습니다(설계서 v0.3.1에 해당 API 없음). 동물 정보카드는 `data/`의 샘플 파일을 기동 시 인덱싱합니다.

---

## 5. 공통 API 명세서

모든 엔드포인트는 `backend`(`:8000`)가 제공합니다.

### 5.1 P0 API (MVP)

| Method | Path                             | Request             | Response             | 인증                                 |
| ------ | -------------------------------- | ------------------- | -------------------- | ------------------------------------ |
| GET    | `/api/health`                  | —                  | `{status, mcp}`    | 없음                                 |
| POST   | `/api/agent/ask`               | `AgentAskRequest` | `AgentAskResponse` | 게스트 세션 허용                     |
| GET    | `/api/admin/trace?session_id=` | —                  | 세션 Trace 목록      | 최소 수준(토큰 등, P1에서 강화 검토) |

```jsonc
// AgentAskRequest
{
  "message": "지금 펭귄 먹이시간이야?",
  "session_id": "guest-8f21"
}

// AgentAskResponse
{
  "intent": "tool",                // "rag" | "tool" | "both" | null
  "status": "completed",           // RunStatus: completed | needs_clarification | confirmation_required | rejected | stopped | error
  "final_answer": "다음 펭귄 먹이시간은...",
  "sources": [],
  "tool_calls": [{"name": "get_feeding_schedule", "arguments": {...}, "result": {...}}],
  "pending_action": null,
  "trace": [{"owner": "runtime", "stage": "run_started"}, {"owner": "ai_agent", "stage": "route_decision"}]
}
```

### 5.2 P1 확장 API

| Method | Path                   | Request                     | Response             | 인증/승인                                               |
| ------ | ---------------------- | --------------------------- | -------------------- | ------------------------------------------------------- |
| POST   | `/api/agent/confirm` | `{session_id, action_id}` | `AgentAskResponse` | `session_id`가 Pending Action 저장 시점과 일치해야 함 |

> SSE(`/api/agent/stream`), `/api/media/stt`, `/api/media/tts`는 설계서 v0.3.1에서 Out-of-Scope로 확정되어 이 실행 계획에도 넣지 않습니다. 필요해지면 별도 스프린트로 다룹니다.

### 5.3 Tool 직접 호출은 만들지 않음

v1 계획에는 `/api/tools/*` 직접 호출 엔드포인트가 있었지만, 설계서 v0.3.1은 모든 Tool 실행을 `/api/agent/ask` 내부에서만 수행하도록 정리했습니다. 관리자·테스트 목적의 직접 호출이 필요하면 MCP `tools/call`을 테스트 코드에서 직접 쓰고, 별도 REST 엔드포인트는 만들지 않습니다.

---

## 6. 함수 / 모듈명 규약

레이어별로 파일과 함수 이름을 고정해, 팀원이 각자 브랜치에서 작업해도 이름이 충돌하지 않게 합니다.

### 6.1 `backend/app/agents/` — Profile 정의 + Runtime (P0)

| 파일                   | 함수/클래스                                           | 역할                                                                                  |
| ---------------------- | ----------------------------------------------------- | ------------------------------------------------------------------------------------- |
| `models.py`          | `AgentProfile` (frozen dataclass)                   | `agent_id, name, goal, description, example_questions, instructions, allowed_tools` |
| `zoo_guide_agent.py` | `ZOO_GUIDE_PROFILE`, `ZOO_GUIDE_ALLOWED_TOOLS_P0` | Goal/Instructions/Allowed Tools 정의 (5.5절 참조)                                     |
| `registry.py`        | `get_agent_profile(agent_id) -> AgentProfile`       | Profile 조회                                                                          |
| `runtime.py`         | `run_agent(state: AgentState) -> AgentState`        | LLM 호출·Tool Call 추출·재시도·`MAX_AGENT_STEPS` 가드                            |

### 6.2 `backend/app/services/` — 실행 순서와 정책 소유 (P0)

| 파일                               | 함수                                                                                                                                                   | 역할                                                                                 |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| `agent_orchestration_service.py` | `handle_ask(request) -> AgentAskResponse`                                                                                                            | `/api/agent/ask` 단일 진입점                                                       |
| `rag_service.py`                 | `chunk_document(raw_text, doc_id)` / `embed_and_store(chunks)` / `retrieve_chunks(query, top_k=3)` / `answer_with_citations(question, chunks)` | RAG를 "준-Tool"로 취급(7.4절 계약),`RAG_MIN_SCORE` 미만이면 `data.matched=false` |

### 6.3 `backend/app/tools/` — 각 함수는 조회 또는 상태 변경 하나만

| 파일             | 함수                                                      | 위험도                    | 우선순위     |
| ---------------- | --------------------------------------------------------- | ------------------------- | ------------ |
| `zoo_tools.py` | `get_feeding_schedule(habitat)`                         | read                      | **P0** |
| `zoo_tools.py` | `check_closure_status(habitat=None)`                    | read                      | **P0** |
| `zoo_tools.py` | `find_habitat_route(current, destination)`              | read                      | **P0** |
| `zoo_tools.py` | `lookup_ticket_scope(ticket_type)`                      | read                      | P1           |
| `zoo_tools.py` | `lookup_public_weather(region)`                         | read                      | P1           |
| `zoo_tools.py` | `reserve_experience_program(program, time, headcount)`  | **change**          | P1           |
| `registry.py`  | `get_tool_definitions() -> list[dict]`                  | —                        | P0           |
| `executor.py`  | `execute_tool_safely(name, arguments) -> ToolRunResult` | Allowlist + Pydantic 검증 | P0           |

### 6.4 `backend/app/repositories/` — 저장소 접근만, 업무 규칙 없음

| 파일                             | 함수                                                                                                           | 저장소                                | 우선순위     |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------- | ------------------------------------- | ------------ |
| `document_repository.py`       | `insert_chunks(chunks)` / `similarity_search(embedding, top_k)`                                            | In-Memory(P0) → pgvector(P1)         | P0           |
| `session_memory_repository.py` | `get_recent(session_id)` / `append_message(session_id, message)`                                           | In-Memory dict(P1) → Redis(P1 이후)  | **P1** |
| `pending_action_repository.py` | `create(action) -> action_id` / `get(action_id)` / `mark_processing(action_id)` / `consume(action_id)` | In-Memory dict, TTL 120s(P1) → Redis | **P1** |

### 6.5 `backend/app/services/approval_service.py` — 승인 판정, 소유권 검증 (P1)

| 함수                                                                         | 역할                                                                                                                            |
| ---------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------- |
| `create_pending_action(tool_name, arguments, session_id) -> PendingAction` | Pending Action 발급                                                                                                             |
| `confirm_pending_action(action_id, session_id) -> ToolRunResult`           | `session_id` 일치 + `pending` 상태 + TTL 검증 → `processing` → 실행 → `completed`. 불일치/만료/중복이면 `rejected` |

### 6.6 `mcp_server/` — 독립 프로세스, 백엔드는 MCP Client로만 호출

| 파일                        | 함수                                    | 역할                                 | 우선순위     |
| --------------------------- | --------------------------------------- | ------------------------------------ | ------------ |
| `server.py`               | `create_mcp_server() -> Server`       | Tool 등록, Streamable HTTP 진입점    | P0           |
| `tools/zoo_operations.py` | `get_feeding_schedule` 등 P0 Tool 3종 | Mock 데이터 연결                     | P0           |
| `tools/public_data.py`    | `lookup_public_weather(region)`       | 공공데이터포털/Mock 연동             | **P1** |
| `tools/zoo_bridge.py`     | `reserve_experience_program(...)`     | 백엔드 예약 로직을 MCP Tool로 재노출 | **P1** |

### 6.7 `backend/app/mcp_client/client.py` (P0)

| 함수                                            | 역할                                    |
| ----------------------------------------------- | --------------------------------------- |
| `discover_tools() -> list[ToolSchema]`        | `tools/list` 호출                     |
| `call_tool(name, arguments) -> ToolRunResult` | `tools/call` 호출, timeout 1회 재시도 |

### 6.8 `frontend/` — 화면은 API 응답을 그대로 렌더링, 정책 판단 없음

| 파일                                 | 함수                                                   | 역할                                                         | 우선순위     |
| ------------------------------------ | ------------------------------------------------------ | ------------------------------------------------------------ | ------------ |
| `app.py`                           | —                                                     | Streamlit 관람객 채팅 화면(질문/출처/Tool 결과)              | P0           |
| `clients/agent_client.py`          | `ask(message, session_id) -> AgentAskResponse`       | `/api/agent/ask` 호출                                      | P0           |
| `clients/agent_client.py`          | `confirm(session_id, action_id) -> AgentAskResponse` | `/api/agent/confirm` 호출                                  | **P1** |
| `app_pages/02_reservation_card.py` | 예약 확인 카드 UI (4.4절 R1~R12 화면 상태)             | TTL 카운트다운, 스피너, 소유권 오류/만료/성공 상태 분리 표시 | **P1** |

---

## 7. 디렉토리 구조

```
ranger-agent/
├─ plan.md                          # 본 문서
├─ docs/
│  └─ eval-scenarios.md             # 회귀 시나리오 정의 (N-01~N-08, A-01~A-14)
│
├─ backend/
│  ├─ app/
│  │  ├─ main.py                    # FastAPI 앱 생성 + 라우터 등록
│  │  ├─ core/
│  │  │  └─ config.py                # MAX_AGENT_STEPS, RAG_MIN_SCORE 등 3.1절 임계값 (하드코딩 금지)
│  │  ├─ routers/
│  │  │  ├─ agent_router.py          # /api/agent/ask (P0), /api/agent/confirm (P1)
│  │  │  ├─ admin_router.py          # /api/admin/trace (P0)
│  │  │  └─ health_router.py         # /api/health (P0)
│  │  ├─ schemas/
│  │  │  ├─ agent.py                 # AgentAskRequest/Response, RunStatus
│  │  │  └─ tools.py                 # 각 Tool 입출력 모델
│  │  ├─ agents/                     # 6.1
│  │  ├─ services/                   # 6.2, 6.5(P1)
│  │  ├─ tools/                      # 6.3
│  │  ├─ repositories/               # 6.4
│  │  └─ mcp_client/                 # 6.7
│  ├─ tests/
│  └─ requirements.txt
│
├─ mcp_server/                       # 6.6, 백엔드와 별도 프로세스로 기동
│  ├─ server.py
│  ├─ tools/
│  │  ├─ zoo_operations.py           # P0
│  │  ├─ public_data.py              # P1
│  │  └─ zoo_bridge.py               # P1
│  └─ requirements.txt
│
├─ frontend/
│  ├─ app.py                         # P0 채팅 화면
│  ├─ app_pages/
│  │  └─ 02_reservation_card.py      # P1 예약 확인 카드
│  ├─ clients/
│  │  └─ agent_client.py
│  └─ core/
│     └─ api_client.py               # 공통 HTTP 요청 Wrapper
│
├─ data/
│  └─ animal_cards/                  # 동물 정보카드 원본 (기동 시 인덱싱)
│
└─ infra/
   ├─ docker-compose.yml             # backend, mcp_server (postgres+redis는 P1에서 추가)
   └─ .env.example
```

> v1 계획에 있던 `backend/app/core/auth.py`, `routers/auth_router.py`, `routers/media_router.py`, `ai-module/`(이미지 인식)는 설계서 v0.3.1의 Out-of-Scope 결정에 따라 이번 실행 계획에서 제외했습니다.

---

## 8. 데이터 모델 · State · Trace

### 8.1 In-Memory 저장 (P0)

| 저장 대상            | 구현                                                                                                |
| -------------------- | --------------------------------------------------------------------------------------------------- |
| 동물 정보카드 임베딩 | In-Memory list/dict (P1에서 pgvector로 교체 가능하도록`document_repository.py` 인터페이스로 분리) |
| Trace                | 응답 State에 포함, 별도 저장소 없음                                                                 |

### 8.2 P1 확장 저장

| 저장 대상                                      | Day-1 | P1                                                              |
| ---------------------------------------------- | ----- | --------------------------------------------------------------- |
| 세션 대화(`session:{session_id}`)            | 없음  | In-Memory dict → Redis                                         |
| Pending Action(`pending_action:{action_id}`) | 없음  | In-Memory dict, TTL 120초(애플리케이션 레벨 만료 비교) → Redis |
| `idempotency_key`                            | 없음  | `session_id + ":" + action_id` 집합으로 중복 실행 방지        |

### 8.3 AgentState 핵심 필드 (`backend/app/schemas/agent.py`)

`run_id, agent_id, session_id, question, intent, status(RunStatus), termination_reason, llm_calls, tool_calls, sources, trace, answer, approval(P1)`

### 8.4 RunStatus

`completed | needs_clarification | confirmation_required | rejected | stopped | error` — `failed`라는 별도 상태는 두지 않고 원인이 정책 쪽이면 `rejected`, 인프라 쪽이면 `error`로 통일합니다.

### 8.5 Trace owner

`runtime`(시작/종료/반복제한/모델오류), `ai_agent`(의도판단/Tool선택/최종답변), `rag`(검색질의/문서ID/유사도), `mcp`(Tool 발견·실행), `policy`(Allowlist/검증/승인대기/소유권 검증 실패), `human`(확인/취소, P1)

---

## 9. 빌드 순서 (Phase)

| Phase    | 목표                     | 작업 내용                                                                                                                       | 검증                              | 우선순위     |
| -------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------- | --------------------------------- | ------------ |
| 1        | 기준선 확보              | Backend/MCP 기동, API Schema 정리, In-Memory 저장소 뼈대,`config.py`에 임계값 정리                                            | `/api/health` 확인              | **P0** |
| 2        | Agent Profile·판단 흐름 | `zoo_guide` Profile, RAG + 조회 Tool 3종 연결                                                                                 | N-01~N-04, A-01~A-05 실행        | **P0** |
| 3        | 안전장치 검증            | Allowlist 차단, 반복 한도(A-13), timeout(A-03), 금지 영역(A-09~A-12)                                                            | A-09~A-14 실행                    | **P0** |
| 4        | Streamlit 통합           | 질문·출처·Tool 정보 표시                                                                                                      | 브라우저에서 P0 흐름 시연         | **P0** |
| 마감(P0) | 통합 테스트·문서화      | 실패 Case 수정, 실행 명령·제한사항 기록                                                                                        | P0 체크리스트 완료 후 데모 재실행 | **P0** |
| 5        | 예약 승인 흐름           | `approval_service`, `pending_action_repository`, `reserve_experience_program`, `/api/agent/confirm`, 소유권 검증(4.2절) | N-06, N-07, A-06~A-08b 실행       | P1           |
| 6        | 조회 Tool 확장           | `lookup_ticket_scope`, `lookup_public_weather`, `mcp_server/tools/public_data.py`                                         | 티켓/날씨 질문 정상 응답          | P1           |
| 7        | 개인화 · Memory         | `session_memory_repository`, N-05(코스 추천), N-08(후속 질문)                                                                 | N-05, N-08 실행                   | P1           |
| 8        | 예약 카드 프론트         | `02_reservation_card.py` (TTL 카운트다운, 스피너, 오류 상태 분리)                                                             | 4.4절 화면 상태 전체 재현         | P1           |
| 9        | P1 회귀 테스트 취합      | 각자 담당 시나리오 통합                                                                                                         | N-05~N-08, A-06~A-08b 전체 통과  | P1           |

Phase 1~4 + 마감(P0)은 이미 완료해야 할 MVP 범위이므로 아래 10장 역할 분담에는 **Phase 5~9만** 배분합니다.

---

## 10. 역할 분담

3명이 나눠 맡되, 서로의 코드는 **7장 디렉토리 구조**의 파일 경계로만 접촉합니다 — 다른 사람 폴더의 함수를 직접 고치는 대신, 필요한 값은 정해진 함수 시그니처(6장)로 주고받습니다.

> **MVP(P0, 6장 표에서 "우선순위=P0"로 표시된 모든 항목: Agent Profile, RAG 파이프라인, 조회 Tool 3종, MCP Server 기본 Tool, Backend 오케스트레이션, Streamlit 채팅 화면, 반복/오류 가드레일)는 이미 범위 확정된 공통 기반이므로 아래 역할 분담에서 제외했습니다.** 이 부분은 팀 전체가 Phase 1~4를 함께 완료한 뒤, P1부터 아래처럼 나눕니다.

### 손영민 — 예약 승인 · 소유권 검증 (Phase 5)

> 본인 희망 영역(에이전트·Tool)의 연장선으로, 상태를 변경하는 유일한 Tool과 그 승인 절차를 책임집니다.

| 구분          | 내용                                                                                                                                                                                                             |
| ------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 포함 Phase    | 5                                                                                                                                                                                                                |
| 소유 디렉토리 | `backend/app/services/approval_service.py`, `backend/app/repositories/pending_action_repository.py`, `backend/app/tools/zoo_tools.py`의 `reserve_experience_program`, `mcp_server/tools/zoo_bridge.py` |
| 주요 함수     | `create_pending_action()` · `confirm_pending_action()` · `reserve_experience_program()`                                                                                                                  |
| 담당 API      | `POST /api/agent/confirm`                                                                                                                                                                                      |
| 검증 대상     | N-06, N-07, A-06, A-07, A-08, A-08b (세션 불일치 즉시`rejected`, TTL 120초, `processing` 상태로 동시 확인 차단)                                                                                              |
| 받는 입력     | Phase 1~4에서 만들어진`AgentState.approval` 필드, `agent_orchestration_service.handle_ask()`의 Tool 제안 결과                                                                                                |
| 넘기는 출력   | `AgentAskResponse.pending_action`, 최두나의 평가 시나리오(T-N06, T-N07, T-A06~T-A08b)가 그대로 통과해야 함                                                                                                     |

### 최두나 — 조회 Tool 확장 · 개인화 · 세션 Memory (Phase 6, 7)

| 구분          | 내용                                                                                                                                                                                   |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 포함 Phase    | 6, 7                                                                                                                                                                                   |
| 소유 디렉토리 | `backend/app/tools/zoo_tools.py`의 `lookup_ticket_scope`/`lookup_public_weather`, `mcp_server/tools/public_data.py`, `backend/app/repositories/session_memory_repository.py` |
| 주요 함수     | `lookup_ticket_scope()` · `lookup_public_weather()` · `get_recent()` / `append_message()`                                                                                    |
| 담당 시나리오 | N-05(개인화 코스 추천, RAG+복수 Tool 조합), N-08(세션 Memory 기반 후속 질문)                                                                                                           |
| 넘기는 출력   | 손영민의`approval_service`가 조회하는 티켓/정원 관련 정보(필요 시), 프론트 대화 맥락 유지에 쓰이는 `session_memory_repository`                                                     |
| 비고          | Redis 전환이 필요해지면(8.2절) 이 사람이 Repository 인터페이스는 그대로 두고 구현체만 교체                                                                                             |

### 이원민 — 예약 카드 UI · P1 회귀 테스트 취합 (Phase 8, 9)

| 구분          | 내용                                                                                                                                                  |
| ------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| 포함 Phase    | 8, 9(취합)                                                                                                                                            |
| 소유 디렉토리 | `frontend/app_pages/02_reservation_card.py`, `frontend/clients/agent_client.py`의 `confirm()`, `docs/eval-scenarios.md`                       |
| 주요 함수     | `confirm(session_id, action_id)` · 4.4절 R1~R12 화면 상태 구현(TTL 카운트다운, 처리 중 스피너, 소유권 오류/만료/일시 오류를 서로 다른 안내로 분리) |
| 담당 API      | `POST /api/agent/confirm` 호출 측(프론트)                                                                                                           |
| 받는 입력     | 손영민의`AgentAskResponse.pending_action` 계약을 그대로 화면에 렌더링(정책 판단 없이 표시만)                                                        |
| 취합 작업     | 3명이 각자 작성한 P1 시나리오(N-05~N-08, A-06~A-08b)를 `docs/eval-scenarios.md`에 통합하고 Phase 9 회귀 테스트를 돌린다                            |

---

## 11. 다음 액션

- [ ] Phase 1~4(P0/MVP)를 팀 전체가 먼저 완료 — `backend/app/core/config.py`에 `MAX_AGENT_STEPS=6`, `RAG_MIN_SCORE=0.5`, `top_k=3` 등 3.1절 임계값을 하드코딩 없이 반영
- [ ] `data/animal_cards/`에 동물 정보카드 샘플 3~5건 확보 후 RAG 인덱싱 검증
- [ ] Tool Mock 데이터 확정 (동물사 목록, 먹이 시간표, 체험 프로그램, 정원) — 손영민이 Phase 5 착수 전 확정
- [ ] `backend/app/schemas/agent.py`에 `AgentAskRequest`/`AgentAskResponse`/`RunStatus` 확정 후 팀 공유
- [ ] MCP Server 최소 기동(`mcp_server/server.py`, P0 Tool 3종)과 backend `mcp_client` 연결 확인
- [ ] P0 체크리스트(설계서 17.2절) 전량 통과 확인 후 Phase 5~9(P1) 착수
- [ ] P0가 예정보다 늦어지면 P1은 시연에서 제외하고 설계 문서로만 남긴다 (설계서 17.3절 원칙 그대로 적용)
