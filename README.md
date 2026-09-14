# 동물원 관람 지원 AI 에이전트 (Zoo Visit Guide)

> LangGraph 기반 AI Agent 실습 과제 — "일정 조율 에이전트" 예시 시나리오를 **동물원 관람 안내**로 재구성해, 인지→판단→행동→검증과 자기 성찰(오류 감지·재시도) 루프를 갖춘 단일 Agent를 설계·구현·시험했습니다.

## 1. 프로젝트 개요

| 항목 | 내용 |
| --- | --- |
| 문제 정의 | 관람객은 동물 지식(먹이·서식지 등)과 실시간 운영 정보(휴장·동선·티켓·날씨·코스·예약)를 뒤섞어 질문한다. 사람 안내원 없이도 **근거 있는 답변**과 **실제 변경(예약)에 대한 승인 절차**를 함께 제공하는 것이 목표다. |
| 주요 사용자 | 동물원 관람객(질문·예약), 운영 관리자(예약 승인, Trace 조회) |
| Agent | `zoo_guide` 단일 Agent (Multi-Agent/Handoff 없음) |
| 핵심 기능 (P0 = MVP) | 동물 정보 RAG 검색 + 먹이시간·휴장·동선 조회 Tool 3종 |
| 확장 기능 (P1) | 티켓·날씨 조회, 날씨 기반 맞춤 코스 추천, 체험 프로그램 예약·승인, 세션 Memory |
| Backend / Frontend | FastAPI / Streamlit (관람객용 + 관리자용 2개 화면) |
| Tool 연결 | 별도 프로세스로 분리한 Streamable HTTP MCP Server |
| 저장소 | `STORAGE_MODE=memory`(In-Memory, 기본) 또는 `persistent`(Postgres+pgvector, Redis) |

자세한 설계 근거는 [plan.md](plan.md)(아키텍처·API·역할 분담)와 `docs/` 아래 개발 계획서·아키텍처 설계서를 참고하세요.

## 2. AI Agent 진행 상태 설계 — 인지 → 판단 → 행동 → 검증

```
사용자 질문
  → POST /api/agent/ask
  → [인지] Agent Runtime이 MCP tools/list로 Tool 목록을 받아 Agent Profile의 Allowlist와 교집합만 LLM에 노출
  → [판단] LLM이 질문·이전 Tool 결과를 보고 RAG 검색 또는 Tool 호출을 제안
      ├─ 정적 지식  → RAG Service → 유사도 검색 (RAG_MIN_SCORE=0.5 이상만 채택)
      └─ 실시간 정보 → Tool Allowlist·arguments(strict schema) 검증 → MCP tools/call
  → [행동] Tool 실행 결과를 다시 LLM에 전달해 최종 답변 판단 (필요 시 반복, 최대 6단계)
  → [검증] 실제 tool_calls·결과를 기준으로 최종 응답·출처·Trace를 재구성해 불일치 방지
  → RunStatus(completed | needs_clarification | confirmation_required | rejected | stopped | error)로 안전 종료
```

- **공유 상태(AgentState)**: `run_id, agent_id, session_id, question, intent, status, termination_reason, llm_calls, tool_calls, sources, trace, answer, approval(P1)`
- **종료 조건(무한 반복 방지)**: Model 최대 6단계, 동일 Tool·인자 반복 2회, 전체 Tool 호출 8회, 전체 실행 90초
- **예약처럼 상태를 바꾸는 요청(P1)**: 조회로 가능 여부 확인 → Pending Action 생성(TTL 120초) → `confirmation_required` → 사용자 확인(`POST /api/agent/confirm`, 같은 `session_id` 필수) → `completed`. 승인 전에는 실제 예약이 생성되지 않는다.

## 3. 자기 성찰(Self-Reflection) · 오류 감지·재시도 루프

과제 5단계 요구사항(할루시네이션·도구 선택 오류·파라미터 누락·응답 불일치 감지, 오류 감지→원인 분석→수정 전략→재실행→검증)을 아래처럼 구현했다.

| 오류 유형 | 감지 기준 | 처리 전략 |
| --- | --- | --- |
| 할루시네이션 | RAG/Tool 결과에 없는 사실·시간·운영 정보를 답변에 포함하려는 시도 | Agent 지시문으로 추측 금지, 근거 없으면 "확인 불가" 안내 (RAG_MIN_SCORE 미만 chunk는 애초에 미채택) |
| 도구 선택 오류 | Agent Profile이 허용하지 않은 Tool·RAG collection 선택 | MCP 호출 **전에** `TOOL_NOT_ALLOWED`로 즉시 차단 |
| 파라미터 누락·형식 오류 | arguments가 JSON 객체가 아니거나 필수값·타입이 strict schema와 불일치 | Tool 미실행 + 보완 질문(`needs_clarification`), 0회 재시도 |
| 응답 불일치 | 실제 Tool 호출·결과와 최종 status/intent/안내가 다름 | 실제 `tool_calls` 기록을 기준으로 최종 응답·Trace를 재구성 |
| 반복 초과 | 동일 Tool·arguments 2회 초과, 전체 Tool 호출 8회 초과 | 다음 호출 차단 후 `stopped` |
| MCP timeout·비정상 응답 | 응답 지연 또는 결과 계약 위반(JSON 형식 불일치, `success=false`) | 같은 인자로 **1회만 재시도** → 실패 시 `MCP_TIMEOUT` 기반 `error`로 표준화(성공으로 오인하지 않음) |
| 날씨 조회 실패(맞춤 코스) | 코스 추천 시 외부 날씨 API 실패 | 실내·실외 후보를 좁히지 못하면 기본 Course Tool 후보로 복귀 |
| 금지 요청 | 결제, 비밀정보, 권한 변경, 삭제, 질병 확진 요청 표현 감지 | Provider·Tool 호출 **이전에** `rejected`로 즉시 차단 |
| 예약 승인 오류 | 미인증, 다른 세션의 action, TTL 만료, 중복 결정 | 실제 예약을 만들지 않고 안전하게 거절/보완 질문 (상태 변경 Tool은 자동 재시도하지 않음) |

> 상태를 변경하지 않는 조회성 오류(timeout 등)만 제한적으로 재시도하고, 예약처럼 실제 변경이 발생하는 오류는 **재시도 없이** 사용자 확인을 다시 받도록 설계했다 — 자기 성찰 루프가 "안전하게 멈추는 것"과 "복구 가능한 것만 복구하는 것"을 구분한다.

## 4. 아키텍처

```
frontend (Streamlit, 관람객용)      ─┐
frontend_admin (Streamlit, 관리자용) ─┼─ HTTP ─▶ backend (FastAPI) ─┬─ MCP(streamable-http) ─▶ mcp_server (조회 Tool 8종)
                                     │                              ├─ Postgres(pgvector) — RAG/예약 (STORAGE_MODE=persistent)
                                     │                              ├─ Redis — 세션/Trace (STORAGE_MODE=persistent)
                                     │                              └─ OpenAI API — LLM Provider (APP_MODE=openai)
```

- **backend**: FastAPI 서버. Agent Runtime(2장), RAG, 예약, 인증, Trace를 담당.
- **frontend / frontend_admin**: 관람객용 채팅·지도·코스 추천·예약 화면, 관리자용 예약 승인·Trace 조회 화면.
- **mcp_server**: 사료시간·휴장·동선·티켓·날씨·코스 조회 Tool 8종을 별도 프로세스로 제공하는 Streamable HTTP MCP 서버 — Backend는 MCP Client로만 호출한다(Tool 직접 import 없음).
- **db / infra**: `infra/docker-compose.yml`로 로컬 Postgres(pgvector)/Redis만 띄울 수 있고, 루트 `compose.yml`로 Postgres/Redis/MCP 서버/Backend/Frontend 전체 스택을 한 번에 띄울 수 있다(8.5절).

## 5. 데모 시나리오

| 유형 | 예시 질문 | 확인 포인트 |
| --- | --- | --- |
| 동물 지식(RAG) | "이 호랑이는 몇 살이고 어디서 왔어?" | 출처 카드(`doc_id`, `score`) 함께 표시 |
| 실시간 운영 정보(Tool) | "지금 물개 먹이 주기 다음은 언제야?" | Tool 이름·조회 시각 표시 |
| 근거 없는 질문 | 카드에 없는 정보 질문 | 추측 없이 "확인 불가" 안내 |
| 맞춤 코스(P1) | "5살 아이와 2시간 볼 수 있는 코스를 추천해 줘" | 날씨 선조회 후 실내·실외 후보 제한 |
| 예약(P1) | "15시 사육사 체험 프로그램 2명 예약해줘" → 확인 클릭 | TTL 120초 내 승인 시에만 실제 예약 생성 |
| 금지 요청 | "결제까지 알아서 해줘" / "API 키 보여줘" | Provider 호출 전 즉시 거절 |

## 6. 시험 결과 요약

오늘 재검증 기준 **자동화 시험 243건 전부 통과(100%)** — Agent Runtime/Provider/Executor, MCP 오류 계약, 정책·안전, 운영 Tool, 예약 승인, Streamlit 화면(지도 포함) 전 영역.

| 지표 | 값 | 근거 |
| --- | ---: | --- |
| 자동화 시험 통과율 | 100% (243/243) | 단위·통합 시험 전체 재실행 |
| 도구 선택·입력 검증 정확도 | 100% | Allowlist·strict schema 시험 전부 PASS |
| 응답 일관성(Trace-응답 일치) | 100% | Runtime·정책 통합 시험 전부 PASS |
| MCP 오류 시 평균 재시도 | 1회 | timeout 시 동일 인자 1회 재호출 설계·시험 확인 |

자세한 표와 개선 이력은 [docs/동물원_관람_지원_Zoo_Visit_Guide_에이전트 시험 결과 보고서_0.3.md](<docs/동물원_관람_지원_Zoo_Visit_Guide_에이전트 시험 결과 보고서_0.3.md>)에, 인프라 연결 점검 기록은 [테스트보고서.md](테스트보고서.md)에 정리되어 있다.

## 7. 수행 과정 · 개선 이력(발췌)

| 문제 | 개선 내용 |
| --- | --- |
| MCP 클라이언트가 호출마다 세션을 새로 열어 반복 호출 시 응답 없이 멈춤 | 세션을 프로세스 생명주기 동안 재사용하도록 리팩터링 |
| 지도 이미지 경로 참조 오류로 지도·코스 추천 화면 전체가 깨짐 | 경로 정리, 관련 Streamlit 화면 시험 재작성 |
| RAG↔Runtime 연결 시험의 동기/비동기 계약 불일치 | 운영 코드와 동일한 비동기 래퍼로 테스트 정정 |
| 챗봇 화면의 예약 승인 흐름 오류 | 승인 대기 상태 처리 로직 개선, 회귀 시험 추가 |

## 8. 시작하기

### 8.1 의존성 설치

루트와 각 서비스의 `requirements.txt`를 **모두** 설치해야 한다(루트만 설치하면 frontend 계열 의존성이 빠진다).

```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt
pip install -r frontend_admin/requirements.txt
pip install -r mcp_server/requirements.txt
```

### 8.2 환경 변수 설정

`.env`는 더 이상 루트 1개를 공유하지 않고 **서비스별로** 둔다 — Docker 이미지에는 `.env`를 담지 않고 실행 시 각 서비스 디렉터리의 `.env`(또는 `env_file`)로 주입하기 위함이다. `backend/app/core/config.py`는 `backend/.env`를, `frontend/bootstrap.py`(관람객용)와 `frontend_admin/app.py`(관리자용, `frontend/.env`를 그대로 사용)는 `frontend/.env`를 읽는다.

```bash
cp .env.example backend/.env
cp .env.example frontend/.env
```

| 변수 | 설명 |
| --- | --- |
| `APP_MODE` | `mock`(결정적 테스트) 또는 `openai`(실제 LLM) |
| `STORAGE_MODE` | `memory`(In-Memory) 또는 `persistent`(Postgres/Redis) |
| `DATABASE_URL`, `REDIS_URL` | `STORAGE_MODE=persistent`일 때 필요 |
| `OPENAI_API_KEY`, `OPENAI_MODEL` | `APP_MODE=openai`일 때 필요 |
| `MCP_SERVER_URL` | Backend가 호출할 MCP 서버 주소 |
| `MCP_HOST`, `MCP_PORT` | MCP 서버를 직접 띄우는 경우에만(다른 팀원이 이미 띄웠다면 주석 처리) |
| `BACKEND_URL` | 프론트/평가기가 참조하는 Backend 주소 |
| `ADMIN_TOKEN` | `/api/admin/trace` 조회 인증(미설정 시 차단) |

`STORAGE_MODE=persistent`로 쓰려면 로컬 Postgres/Redis가 필요하다.

```bash
docker compose -f infra/docker-compose.yml up -d
```

### 8.3 서버 실행 (각각 별도 터미널)

```bash
# 1) MCP 서버 (조회 Tool 8종)
python -m mcp_server.server

# 2) Backend (FastAPI)
uvicorn backend.app.main:app --reload --port 8000

# 3) 관람객용 Frontend (Streamlit)
streamlit run frontend/app.py

# 4) 관리자용 Frontend (예약 승인, 선택)
streamlit run frontend_admin/app.py
```

### 8.4 RAG 카드 시드

`STORAGE_MODE=persistent`에서 pgvector 기반 RAG를 쓰려면 동물 정보카드를 임베딩해 넣어야 한다.

```bash
python scripts/seed_animal_cards.py
```

### 8.5 Docker Compose로 전체 스택 실행

사내망·개별 프로세스 실행 없이, Docker만으로 Postgres/Redis/MCP 서버/Backend/Frontend를 한 번에 띄울 수 있다.

**로컬 빌드로 실행** (`compose.yml`) — 이 저장소 코드를 그대로 빌드해서 띄운다.

```bash
cp .env.example backend/.env
cp .env.example frontend/.env
# backend/.env에 OPENAI_API_KEY를 채우면 APP_MODE=openai로 실제 LLM 응답 가능
docker compose -f compose.yml up -d --build
```

- Backend: http://localhost:8000, Frontend: http://localhost:8501
- Postgres/Redis/MCP 서버는 컨테이너 네트워크 안에서 서비스명(`postgres`, `redis`, `mcp_server`)으로 서로를 찾도록 `compose.yml`에서 `DATABASE_URL`/`REDIS_URL`/`MCP_SERVER_URL`을 덮어쓴다 — `backend/.env`·`frontend/.env`의 로컬/사내망 값은 이때 무시된다.

**빌드된 이미지만으로 실행** (`compose.release.yml`) — 소스 코드 없이 Registry에 올린 이미지만으로 배포하는 시나리오. `.env`에 `BACKEND_IMAGE`/`FRONTEND_IMAGE`/`MCP_IMAGE`(및 필요 시 `OPENAI_API_KEY` 등)를 지정한다.

```bash
docker compose -f compose.release.yml up -d
```

- 각 서비스 Dockerfile은 `backend/Dockerfile`, `frontend/Dockerfile`, `mcp_server/Dockerfile`이며, 저장소 루트 기준 절대 import(`from backend.app...`)를 쓰기 때문에 빌드 컨텍스트는 반드시 프로젝트 루트여야 한다.

## 9. 주요 API (Backend)

| Method | Path | 설명 |
| --- | --- | --- |
| GET | `/api/health` | Backend/MCP/Postgres/Redis 상태 확인 |
| POST | `/api/agent/ask` | 질문 1건 처리(동기) |
| POST | `/api/agent/ask/stream` | 질문 처리(SSE 스트리밍) |
| POST | `/api/agent/confirm` | 예약 등 승인 대기 action 확정/취소 |
| POST/GET | `/api/auth/login`, `/api/auth/logout`, `/api/auth/session` | 로그인 세션 |
| POST/GET | `/api/reservations`, `/api/reservations/mine` | 예약 생성/조회 |
| GET/POST | `/api/admin/reservations/pending`, `/api/admin/reservations/{action_id}/decision` | 관리자 예약 승인 |
| GET | `/api/admin/trace`, `/api/admin/trace/sessions` | Trace 조회(관리자) |
| GET | `/api/tools/*` | 개별 Tool 직접 호출(디버그용) |

## 10. 테스트

```bash
pytest
```

- `STORAGE_MODE=memory`에서는 Postgres/Redis 없이 대부분의 시험을 실행할 수 있다.
- `STORAGE_MODE=persistent` 관련 시험(`tests/data/test_*_postgres.py`, `*_redis.py` 등)은 `infra/docker-compose.yml` 또는 사내망 DB 연결이 필요하다.
- 마커: `integration`(실제 MCP/Backend 프로세스 필요), `live`(실제 OpenAI 키 필요), `policy`(정책/안전 시험).

## 11. 디렉토리 구조

```
backend/        FastAPI 서버 (Agent Runtime, RAG, 예약, 인증, Trace) + Dockerfile, .env
frontend/       관람객용 Streamlit 앱 + Dockerfile, .env(frontend_admin도 공유)
frontend_admin/ 관리자용 Streamlit 앱 (예약 승인)
mcp_server/     운영 조회 Tool을 제공하는 MCP 서버 + Dockerfile
db/             스키마·마이그레이션 관련 자료
data/           동물 정보카드 등 로컬 데이터
scripts/        RAG 카드 시드 등 운영 스크립트
eval/           시나리오 기반 평가 스크립트
infra/          로컬 Postgres(pgvector)/Redis만 띄우는 docker-compose
tests/          pytest 시험 전체
docs/           설계서·작업지시서·시험 결과 보고서
compose.yml            전체 스택(Postgres/Redis/MCP/Backend/Frontend) 로컬 빌드 실행용
compose.release.yml    전체 스택을 Registry 이미지만으로 실행하는 배포용
```

## 12. 팀 구성 및 역할 분담

MVP(P0: Agent Profile, RAG 파이프라인, 조회 Tool 3종, MCP Server, Backend 오케스트레이션, Streamlit 채팅 화면, 반복/오류 가드레일)는 팀 전체가 함께 완료한 공통 기반이며, 이후 P1 확장 기능을 아래처럼 분담했다.

| 담당 | 역할 |
| --- | --- |
| 손영민 | 예약 승인 · 소유권 검증(`approval_service`, `pending_action_repository`, `reserve_experience_program`, `/api/agent/confirm`) |
| 최두나 | 조회 Tool 확장 · 개인화 · 세션 Memory(`lookup_ticket_scope`, `lookup_public_weather`, `session_memory_repository`) |
| 이원민 | 예약 카드 UI · P1 회귀 테스트 취합(`02_reservation_card.py`, `agent_client.confirm()`, 시나리오 통합) |

역할 분담의 상세 근거(소유 디렉토리, 함수 시그니처, 입출력 계약)는 [plan.md 10장](plan.md#10-역할-분담)에 정리되어 있다.

## 13. 참고 문서

- [plan.md](plan.md) — 프로젝트 실행 계획(아키텍처, API 명세, 디렉토리·함수명 규약, 역할 분담)
- [docs/](docs/) — 개발 계획서, 아키텍처 설계서, 시험 결과 보고서
- [테스트보고서.md](테스트보고서.md) — 인프라 연결 상태 점검 기록
