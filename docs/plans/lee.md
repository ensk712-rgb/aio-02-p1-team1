# 이원민 개발 계획 — MCP·프론트·조회 API 연결

담당자 / 브랜치: 이원민 / `feat/lee-mcp-ui-p0`

## 범위와 선행 원칙

- P0 범위는 L1~L6이며 완료했다. 후속 요청으로 L7 승인 화면을 P1 범위에 추가한다. SSE와 음성은 제외한다.
- 프론트는 MCP를 직접 호출하지 않고 Backend의 `/api/agent/ask`만 호출한다. 단, L1~L2의 연결 검증 테스트는 Backend 없이 MCP Client가 MCP Server를 직접 호출한다.
- 최두나 소유의 `backend/app/tools/zoo_tools.py`와 운영 JSON은 수정하지 않고 얇은 MCP wrapper에서 재사용한다.
- 손영민 소유의 공통 Schema와 `AgentAskResponse`를 소비하며 필드명을 독자적으로 변경하지 않는다.
- MCP Client는 재시도하지 않는다. timeout 재시도와 실행 횟수 판정은 Runtime/Executor가 담당한다.
- 비밀번호, API 키, `ADMIN_TOKEN`은 화면·응답·Trace·테스트 출력에 기록하지 않는다.

## 수정할 파일(소유 범위)

- `backend/app/mcp_client/__init__.py`, `backend/app/mcp_client/client.py`
- `mcp_server/__init__.py`, `mcp_server/server.py`
- `mcp_server/tools/__init__.py`, `mcp_server/tools/zoo_read.py`
- `frontend/app.py`, `frontend/clients/__init__.py`, `frontend/clients/agent_client.py`
- `backend/app/core/auth.py`
- `backend/app/routers/health_router.py`, `backend/app/routers/admin_router.py`
- `tests/ui_mcp/`, `tests/integration/test_mcp_agent.py`, `tests/integration/test_e2e_ui.py`
- `eval/scenarios/mcp.json`

공통 파일인 `backend/app/main.py`, `requirements.txt`, `.env.example`, `pytest.ini`는 직접 수정하지 않고 각 소유자에게 조립 또는 변경을 요청한다.

## 단계별 작업

### L1 — Streamable HTTP MCP Server/Client

1. `create_mcp_server()`가 `127.0.0.1:8010/mcp`에서 Streamable HTTP로 실행되도록 구성한다.
2. `McpClient.list_tools()`가 SDK 객체를 `{name, description, input_schema}` dict로 정규화한다.
3. `McpClient.call_tool()`은 Text content의 JSON을 공통 `ToolRunResult`로 검증한다. 비 JSON, 빈 content, 오류 응답은 성공으로 바꾸지 않는다.
4. `check_health()`는 initialize + tools/list 성공 여부만 반환하며 예외 원문이나 URL의 민감정보를 외부로 노출하지 않는다.

완료 판단: Backend 없이 실제 MCP 프로세스를 띄운 테스트에서 세 Tool의 이름과 입력 Schema가 고정 계약과 일치한다.

### L2 — 순수 운영 함수 wrapper

1. `mcp_server/tools/zoo_read.py`에 `get_feeding_schedule`, `check_closure_status`, `find_habitat_route` wrapper를 둔다.
2. wrapper는 동일 이름의 순수 Python 함수를 명시적으로 호출하고 `ToolRunResult.model_dump(mode="json")`만 반환한다.
3. 동적 import·`eval()`·Backend HTTP 재호출은 사용하지 않는다.

완료 판단: tools/call 3종의 결과가 `success`, `data`, `error`, `source`, timezone 포함 `retrieved_at` 계약을 통과한다.

### L3 — Fake 기반 Streamlit 화면

1. 기본 채팅 입력, 실행 spinner, 새 대화, 교육용 Mock 안내를 구현한다.
2. `st.session_state`에는 `session_id`, 화면용 메시지, 제출 중 상태만 저장한다.
3. 답변, 출처(title/page/score), Tool 카드(name/arguments/result/source/as_of/retrieved_at)를 분리 렌더링한다.
4. `completed`, `needs_clarification`, `rejected`, `stopped`, `error`를 구분하고 실패를 성공 스타일로 표시하지 않는다.

상대 구현 전 Fake: 상태별 `AgentAskResponse` dict와 health 정상/degraded 응답을 주입한다.

완료 판단: 네트워크 없이 Fake Client로 상태별 화면 단위 시험이 통과한다.

### L4 — health/admin Trace Router

1. `/api/health`는 Backend와 MCP의 실제 상태를 구분하여 `ok` 또는 `degraded`로 반환한다. MCP 불가 시 HTTP 503이며 저장소를 DB/Redis로 허위 표시하지 않는다.
2. `/api/admin/trace?session_id=...`는 최두나의 Trace Repository를 읽어 `{runs:[...]}`로 반환한다.
3. `ADMIN_TOKEN`이 미설정이거나 Authorization Bearer 토큰이 없거나 불일치하면 401로 차단한다.
4. 토큰 값은 로그, Trace, 응답 detail에 포함하지 않는다.

완료 판단: 관리자 토큰 미설정/누락/불일치 3종 차단과 정상 Trace 조회 테스트가 통과한다.

### L5 — 실제 ask API와 UI 연결

1. `frontend/clients/agent_client.py`가 동기 `ask(message, session_id=None)`와 `get_health()`를 제공한다.
2. HTTP timeout, 연결 실패, 비 2xx, 잘못된 JSON을 구분된 안전 오류로 변환한다.
3. L3 화면 단위 시험 통과 후에만 Fake를 실제 Client로 교체한다.
4. Backend가 발급한 `session_id`를 저장하고 새 대화에서 제거한다.

완료 판단: N-01은 출처와 점수, N-02~N-04는 실제 MCP Tool 결과 카드가 브라우저에 표시된다.

### L6 — MCP/UI 오류 및 회귀

1. MCP initialize/list/call timeout, 비 JSON content, `isError`, 결과 Schema 불일치를 각각 시험한다.
2. A-03은 Runtime의 1회 재시도 뒤 `status=error`, A-14는 MCP 예외 뒤 `status=error`와 허위 운영 정보 없음으로 확인한다.
3. UI는 Backend 연결 실패, HTTP 오류, 실행 결과 `error`를 서로 구분하되 어느 경우도 성공 카드로 렌더링하지 않는다.
4. `eval/scenarios/mcp.json`에 N-02~N-04, A-03, A-14의 입력·기대 status·Tool·금지 결과를 기록한다.

완료 판단: 단위 시험, 로컬 MCP 연결 시험, 브라우저 시연 결과를 구분해 기록한다.

### L7(P1) — 예약 확인·취소·만료·멱등성

1. 예약 입력은 즉시 예약 데이터를 생성하지 않고 120초 TTL의 Pending Action Snapshot을 만든다.
2. 확인/취소 요청은 `action_id`와 서버 발급 세션 ID만 전달하며 저장된 arguments를 다시 보내지 않는다.
3. Backend가 세션 소유권, TTL, pending 상태를 한 lock 안에서 판정하고 확인된 요청만 예약으로 한 번 생성한다.
4. 화면은 확인 카드와 서버 판정 문장을 표시하며 처리 중에는 확인/취소 버튼을 비활성화한다.
5. 취소, 만료, 세션 불일치, 이미 처리된 action 재사용을 각각 시험한다.

완료 판단: 120초 만료 및 중복 클릭이 서버에서 차단되고, 확인 전에는 관리자 예약 목록이 변경되지 않는다.

### L8(P1) — 전용 체험 예약 화면

1. 홈의 접힌 예약 기능을 유지하면서 좌측 메뉴에서 접근 가능한 전용 예약 페이지를 추가한다.
2. 프로그램 선택 → 120초 내 사용자 확인 → 관리자 검토의 책임 경계를 화면에 설명한다.
3. 기존 `AgentClient`와 승인 컴포넌트를 재사용하고 페이지에서 Backend/MCP를 직접 호출하지 않는다.
4. 실제 API와 Fake 모드의 데이터 경계를 명시하고 로그인 Session State를 그대로 유지한다.

완료 판단: 전용 페이지에서 예약 생성·확인·취소·내 예약 조회가 기존 L7 서버 계약으로 동작하고 화면 단위 시험과 브라우저 시연이 통과한다.

### L9(P1) — 평가 시나리오와 최종 회귀

1. `docs/eval-scenarios.md`에서 정상·비정상 Case를 실행 파일과 자동 시험에 일대일로 연결한다.
2. 장애 주입용 A-03/A-14는 일반 HTTP 평가에서 거짓 실패로 판정하지 않고 대응 pytest로 분리한다.
3. 승인·취소 동시 요청은 서버의 원자적 상태 전이로 하나만 성공하는지 시험한다.
4. 다른 세션의 확인 실패가 원 사용자의 pending action을 소비하지 않는지 시험한다.
5. Fake/실제 Backend 화면 표시는 실행 모드와 일치해야 한다.

완료 판단: 전체 자동 시험, 실제 HTTP 평가, 사용자→관리자 예약 승인 브라우저 E2E가 모두 통과한다.

## 입력 계약 / 넘길 출력

- 받는 입력: `AgentProfile.allowed_tools`, 공통 `ToolRunResult`, `AgentAskResponse`, 순수 조회 함수 3종, Trace Repository.
- 넘기는 출력: 정규화된 MCP Tool 목록, 검증된 `ToolRunResult`, MCP health, Streamlit 화면, health/admin Router.
- Tool 이름과 입력: `get_feeding_schedule(habitat)`, `check_closure_status(habitat=None)`, `find_habitat_route(current,destination)`.

## 의존하는 상대 작업

- 손영민: 공통 Schema 안정화, Runtime/Executor에서 MCP Client 주입, `main.py` Router 조립, ask 응답 계약.
- 최두나: 운영 조회 함수·JSON, Trace Repository, 환경/requirements 반영.

## 완료 판단 테스트와 실행 기록

| 단계 | 시험 | 완료 기준 | 현재 결과 |
| --- | --- | --- | --- |
| L1~L2 | `python -m pytest -c tests/ui_mcp/pytest.ini tests/ui_mcp/test_mcp_direct.py -q` | 실제 HTTP MCP tools/list + tools/call 3종 | PASS — 2 passed (2026-09-07 12:00 KST) |
| L3 | Fake Client Streamlit AppTest | 상태별 렌더링, 오류의 성공 표시 없음 | PASS — Fake 완료/추가정보/오류/새 대화 및 브라우저 확인 |
| L4 | FastAPI TestClient | health 계약, admin token 차단/정상 조회 | PASS — 정상/503 및 인증 4경로 |
| L5 | 로컬 MCP→Backend→Streamlit | N-01~N-04 화면 시연 | PASS — `main.py` 조립, 실제 HTTP MCP/API/브라우저 확인 |
| L6 | Fake timeout/invalid result + UI | A-03/A-14 `error`, 허위 성공 없음 | PASS — timeout 2회, invalid 결과 무재시도, Client 오류 4종 구분, 전체 145 tests 및 브라우저 오류 확인 |
| L7(P1) | Pending Action API + Streamlit AppTest | 120초 TTL, 취소, 세션 불일치, 재사용 차단 | PASS — 사용자 서버 판정 안내, 관리자 중복 클릭 방지, 전체 146 tests 및 사용자·관리자 브라우저 확인 |
| L8(P1) | 전용 체험 예약 페이지 | 기존 L7 계약 재사용, 로그인 상태 유지, Mock 경계 표시 | PASS — 전체 147 tests 및 전용 페이지 브라우저 확인 |
| L9(P1) | 평가 문서·P1 회귀·실제 E2E | Case-시험 추적, 경합·세션 보존, 실제/Mock 구분 | PASS — 전체 152 tests, HTTP 평가 12 PASS/0 FAIL/2 SKIP 및 실제 예약 승인 E2E 확인 |

처음 확인한 실패: 저장소 전체 `python -m pytest -q`는 구현 시험 전에 `pytest.ini`의 `markers` 키가 두 번 선언되어 설정 파싱 오류로 중단된다. 이 파일은 손영민 소유이므로 별도 수정 요청 대상으로 남긴다.

남은 일 / 제한사항: 요청에 따라 `backend/app/main.py`까지 구현하여 L5/L6를 연결했다. 기본 `pytest.ini`의 중복 `markers` 선언을 병합했고, 팀 공통 버전과 같은 Python 3.12.7 환경 `backend/.venv312`에 루트 및 frontend requirements를 설치했다. 기본 테스트 명령은 Python 3.11과 3.12.7에서 각각 123건 통과했다. Starlette TestClient의 upstream deprecation warning 1건은 기능 실패가 아니다.
