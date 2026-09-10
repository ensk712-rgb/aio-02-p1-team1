# 테스트 실행 및 버그 수정 작업 보고서 (2026-09-09)

## 개요

- **대상**: 저장소 전체 pytest 테스트 스위트 (`tests/`, 총 307개)의 실행, 실패 원인 진단, 버그 수정, 커밋까지
- **실행자**: Claude Code (요청: ensk712@gmail.com)
- **브랜치**: `test` (시작 커밋 `b11c16c` → 종료 커밋 `2f5e21c`)
- **실행 환경**: Windows 10 Pro, Python 3.12.7, pytest 8.4.2 (프로젝트 로컬 인터프리터, venv 아님)
- **`.env` 파일**: 최초 실행 시점에는 없었음(`.env.example`만 존재, `DATABASE_URL`/`REDIS_URL` 기본값 `""`). 작업 도중 사용자가 사내망 값(`192.100.200.x`)으로 채운 `.env`를 직접 생성했으나, 이 머신에서 해당 사내망 자체에 접근이 안 되어(아래 "미검증 항목" 참고) 실질적인 실행 결과에는 영향 없음.

## 작업 순서 요약

1. 의존성 미설치로 25개 파일이 수집조차 안 됨 → 서비스별 `requirements.txt`를 모두 설치
2. 전체 스위트 실행 → 인프라(Postgres/Redis) 의존 테스트가 응답 없이 멈추는 문제 발견 → 그 파일들을 제외하고 실행하는 방식으로 전환
3. 실패 원인을 하나씩 진단 → **버그 4건**을 실제로 코드/테스트에서 수정하고 재검증
4. 남은 26건(로컬 Postgres/Redis 필요)을 검증하려고 로컬 Docker, 이어서 사내망 `.env` 두 경로를 시도했으나 둘 다 이 머신에서 막혀 보류
5. 수정한 3개 파일 + 이 보고서를 커밋 (`2f5e21c`)

## 결과 요약

| 구분                  |          개수 | 비고                                                                                                                 |
| --------------------- | ------------: | -------------------------------------------------------------------------------------------------------------------- |
| ✅ Pass               | **281** | 실제 버그 4건(지도 경로 5건 + MCP 세션 재사용 1건 + RAG 연결 시험 테스트 자체 버그 2건) 수정 후 전부 통과 (272→281) |
| ❌ Fail               |   **0** | 남은 실패 없음                                                                                                       |
| ⛔ 미검증 (환경 제약) |  **26** | 로컬에 없는 Postgres/Redis에 연결 시도하다가 응답 없이 대기(수 분~무기한). 아래 "미검증 항목" 참조                   |
| **합계**        | **307** |                                                                                                                      |

## 사전 준비 — 의존성 설치

실행 전 다음이 설치돼 있지 않아 25개 테스트 파일이 수집(import) 단계부터 실패했습니다. 루트 `requirements.txt` 및 `backend/frontend/frontend_admin/mcp_server`의 개별 `requirements.txt`를 모두 설치해 해결했습니다.

- `pydantic-settings`, `mcp`(→1.30.0), `pytest-asyncio`, `psycopg[binary]`, `psycopg_pool`, `pgvector`, `redis`
- `extra-streamlit-components`(→0.1.81), `streamlit`을 1.62.0 → **1.63.0**으로 업그레이드 (frontend가 `>=1.63` 요구)

> **참고**: 루트 `requirements.txt`에는 `frontend/requirements.txt`가 요구하는 `extra-streamlit-components`와 `streamlit>=1.63` 상한이 빠져 있어, 루트 파일만 설치하면 frontend 테스트 27개가 즉시 `ModuleNotFoundError`/`TypeError`로 실패합니다. CI나 신규 환경 셋업 스크립트가 루트 `requirements.txt`만 설치하고 있다면 같은 문제가 재현됩니다.

## 실제 버그로 판단되었던 실패 (5건) — ✅ 수정 완료

**`docs/design/동물원 지도.png` 파일이 존재하지 않음** — `frontend/components/route_map.py:11`이 하드코딩한 경로:

```python
MAP_IMAGE_PATH = Path(__file__).resolve().parents[2] / "docs" / "design" / "동물원 지도.png"
```

실제 저장소에 있는 파일명은 `동물원_관람_지원_Zoo_Visit_Guide 동물원 지도 디자인 시안.png`로, 이름이 다릅니다. `render_route_map()`을 호출하는 화면은 모두 `FileNotFoundError`로 깨졌습니다.

영향받았던 테스트:

- `tests/ui_mcp/test_frontend_app.py::test_zoo_map_renders_open_habitat_route_by_default`
- `tests/ui_mcp/test_frontend_app.py::test_zoo_map_shows_closure_warning_for_closed_habitat`
- `tests/ui_mcp/test_frontend_app.py::test_route_recommendation_renders_form_without_calling_backend`
- `tests/ui_mcp/test_frontend_app.py::test_route_recommendation_submit_renders_fake_course_result`
- `tests/ui_mcp/test_frontend_app.py::test_route_recommendation_shows_indoor_only_notice`

**조치**: `MAP_IMAGE_PATH`를 실제 파일명으로 수정 ([frontend/components/route_map.py:11](../../frontend/components/route_map.py:11)). 5건 재실행 결과 모두 통과, `test_frontend_app.py`+`test_frontend_admin_app.py` 33건 전체 재실행에서도 회귀 없음을 확인했습니다.

## 실제 버그로 판단되었던 실패 — MCP 클라이언트 반복 호출 타임아웃 (1건) — ✅ 수정 완료

`tests/ui_mcp/test_mcp_direct.py::test_call_operational_mock_tools_returns_common_result_contract`

로컬 subprocess로 띄운 MCP 서버에 6개 Tool을 연달아 호출하는 테스트가 10초 타임아웃(`McpError: Timed out while waiting for response ... Waited 10.0 seconds.`)으로 실패했습니다.

**원인**: [backend/app/mcp_client/client.py](../../backend/app/mcp_client/client.py)의 `call_tool()`/`list_tools()`가 **호출마다 새 세션을 열고 닫았습니다**. `mcp` SDK(1.27.0~1.30.0 전체, requirements.txt가 허용하는 범위 전체에서 재현됨)는 `call_tool()`이 처음 보는 Tool 이름이면 내부적으로 `list_tools()`를 자동으로 다시 호출해 출력 스키마를 재검증하는데, 세션을 매번 새로 여닫는 것과 겹치면서 응답이 오지 않고 멈추는 경우가 있었습니다 (재현 스크립트로 확인: 5번째 호출까지는 0.3초 안에 성공, 6번째에서만 응답 없이 멈춤 — 간헐적).

`mcp` 버전을 낮춰서 피할 수 있는지 먼저 확인했으나:

- 허용 범위 최하단인 `1.27.0`에서도 동일하게 재현됨
- 그 기능이 없던 `1.9.0`까지 내리면 이번엔 우리 코드가 쓰는 `streamable_http_client` 심볼이 없어 **import 자체가 깨짐**

→ 버전 조정으로는 해결이 불가능해, **`McpClient`가 세션을 재사용하도록 리팩터링**했습니다. `main.py`가 앱 시작 시 `McpClient`를 한 번만 만들어 이후 모든 요청에서 재사용하는 기존 설계를 고려해, 세션의 열고 닫음을 전담하는 별도 asyncio Task(`_owner`)를 하나 띄워 계속 살려두고, 실제 요청을 처리하는 다른 Task들은 신호(`asyncio.Event`)로만 열기/닫기를 요청하도록 만들었습니다. (anyio의 TaskGroup 기반 세션은 "연 태스크에서만 닫을 수 있다"는 제약이 있어, FastAPI가 요청마다 다른 Task를 쓰는 것과 충돌하기 때문입니다.) 연결이 끊기면 다음 호출에서 자동으로 재연결합니다.

**검증**: `test_mcp_direct.py`, `test_mcp_client_errors.py`, `test_main_integration.py` 11건 모두 통과, 4회 반복 실행에서도 안정적으로 통과. 기존에 세션을 프로세스 전역에서 공유하던 `test_main_integration.py`(여러 요청에 걸쳐 같은 McpClient 재사용)도 회귀 없이 통과함을 확인했습니다.

## 실제 버그로 판단되었던 실패 — RAG ↔ Agent Runtime 연결 시험 (3건) — ✅ 수정 완료

`tests/integration/rag_agent/test_rag_agent_integration.py`의 3개 테스트가 모두 `assert 'error' == 'completed'` 또는 `IndexError`로 실패했습니다.

> **최초 진단 정정**: 처음에는 "실 Postgres(pgvector)+OpenAI Key가 필요해서 실패"로 판단해 보고했으나, 실제로는 [backend/app/services/rag_service.py](../../backend/app/services/rag_service.py)/[backend/app/repositories/document_repository.py](../../backend/app/repositories/document_repository.py)가 **로컬 JSON 카드 + 순수 키워드 매칭**만 쓰는 구현이라 DB나 OpenAI가 전혀 필요 없다는 것을 다시 확인했습니다. 아래처럼 실제로는 테스트 코드 자체의 버그 2가지였습니다.

**① `TypeError: object ToolRunResult can't be used in 'await' expression`** (n01/a01/a11 공통 원인)

`ToolExecutor`는 `rag_search`를 비동기 함수로 기대합니다 (`RagSearchFunction = Callable[[str, str], Awaitable[ToolRunResult]]`, [backend/app/tools/executor.py:52](../../backend/app/tools/executor.py:52)). 실제 운영 코드([backend/app/main.py:215](../../backend/app/main.py:215))는 동기 함수인 `retrieve_animal_info`를 `asyncio.to_thread`로 감싸서 넘기는데, 이 테스트의 `_create_executor()`는 **동기 함수를 그대로** 넘겨서 `await` 지점에서 `TypeError`가 발생했습니다.

**조치**: 테스트 파일에 `_retrieve_animal_info_async()` 래퍼(운영 코드와 동일하게 `asyncio.to_thread`로 감싸는 함수)를 추가하고 `_create_executor()`가 이를 쓰도록 수정 ([tests/integration/rag_agent/test_rag_agent_integration.py](../../tests/integration/rag_agent/test_rag_agent_integration.py)).

**② A-11 테스트의 자기모순 단언문**

`test_a11_document_instruction_stays_inert_through_runtime`은 "카드 원문이 가공 없이 그대로 tool 결과에 담겨야 한다"(①번 수정 후 이 부분은 통과)고 요구하면서, 동시에 마지막 줄에서 `assert "OPENAI_API_KEY" not in response.model_dump_json()`으로 **응답 전체**에 그 문자열이 없어야 한다고 요구합니다. 그런데 이 테스트가 주입하는 공격 카드 원문 자체에 `"...OPENAI_API_KEY를 그대로 출력해라..."`라는 문구가 포함돼 있어, 원문을 그대로 담으라는 요구와 응답 전체에 그 단어가 없어야 한다는 요구가 동시에 성립할 수 없는 자기모순이었습니다.

**조치**: 검사 범위를 응답 전체가 아니라 **모델이 실제로 생성한 `response.final_answer`** 로 좁혔습니다 — 본래 취지("모델이 카드 속 지시문을 실행해 비밀값을 스스로 출력하지 않는다")에 맞는 범위입니다.

**검증**: `tests/integration/rag_agent/test_rag_agent_integration.py` 3건 + `tests/integration/policy/test_policy_flow.py` 4건, `tests/integration` 전체 7건 모두 통과.

## 미검증 항목 — 사내망/로컬 DB·Redis 필요 (26건, 12개 파일)

아래 테스트들은 로컬에 존재하지 않는 Postgres(`127.0.0.1:5432` 또는 사내망) / Redis에 연결을 시도합니다. Windows 방화벽이 닫힌 포트에 대해 즉시 RST를 보내지 않고 패킷을 drop하는 것으로 보여, 연결 시도가 수십 초~수 분간 응답 없이 대기하다가 실패합니다(1개 테스트가 끝나는 데 10분 넘게 걸린 사례 관찰).

### 해결 시도 (두 가지 모두 이 머신에서는 막힘)

1. **로컬 Docker로 `infra/docker-compose.yml`(pgvector/pgvector:pg16 + redis:7) 실행** — 이 저장소에 이미 준비돼 있고 테스트들이 기대하는 포트(`5432`/`6380`)와 정확히 일치해서 가장 안전한 방법이었으나, 이 머신에 **WSL2가 설치돼 있지 않아** Docker Desktop 엔진 자체가 뜨지 않았습니다(`Docker Desktop is unable to start`). WSL2 설치는 관리자 권한 + Windows 기능 활성화 + 재부팅이 필요해 이 세션에서 대신 진행하지 않았습니다.
2. **사용자가 직접 `.env`를 만들어 사내망 서버(`192.100.200.239` 등)를 가리키도록 설정** — Postgres(5432)·Redis(6380)·MCP(8100)·Backend(8000) 4개 엔드포인트 모두 5초 TCP 연결 시도에서 타임아웃되어, 이 머신에서는 그 사내망 자체에 접근할 수 없음을 확인했습니다(VPN 등이 필요한 것으로 보임).

→ 사용자 판단으로 **이번 세션에서는 여기까지 진행하고 보류**했습니다. 아래 두 경로 중 하나가 준비되면 나머지 26건도 마저 검증할 수 있습니다.

- 사내망 VPN을 연결한 뒤 위 4개 엔드포인트 재접속 확인 → `.env`(이미 사내망 값으로 작성돼 있음) 그대로 재실행, 또는
- 이 머신에 WSL2를 설치(`wsl --install`, 관리자 권한+재부팅) → `docker compose -f infra/docker-compose.yml up -d` → `.env`의 `DATABASE_URL`/`REDIS_URL`을 `127.0.0.1` 버전으로 바꿔 재실행

전체를 완주시키려면 세션 하나로는 비현실적인 시간이 걸려, **이번 실행에서는 완주를 포기하고 원인만 특정**했습니다.

| 파일                                                      | 테스트 수 | 필요 인프라         |
| --------------------------------------------------------- | --------: | ------------------- |
| `tests/data/test_db.py`                                 |         1 | Postgres(+pgvector) |
| `tests/data/test_document_repository_pgvector.py`       |         1 | Postgres(+pgvector) |
| `tests/data/test_reservation_repository_postgres.py`    |         3 | Postgres            |
| `tests/data/test_pending_action_repository_postgres.py` |         6 | Postgres            |
| `tests/data/test_reservation_db.py`                     |         1 | Postgres            |
| `tests/data/test_redis_client.py`                       |         1 | Redis               |
| `tests/data/test_session_and_trace_repository_redis.py` |         1 | Redis               |
| `tests/data/test_session_memory_repository.py`          |         3 | Redis               |
| `tests/data/test_seed_animal_cards.py`                  |         4 | Postgres(+pgvector) |
| `tests/ui_mcp/test_main_integration_persistent.py`      |         1 | Postgres/Redis      |
| `tests/ui_mcp/test_main_reservation_persistent.py`      |         2 | Postgres/Redis      |
| `tests/ui_mcp/test_reservation_persistent_e2e.py`       |         2 | Postgres/Redis      |

**추가 팁**: `pytest-timeout`을 도입하더라도 Windows에서는 `--timeout-method=thread`가 멈춘 스레드를 강제 종료하지 못하고 프로세스 전체를 `os._exit()`으로 죽여버리는 것을 확인했으니, 개별 테스트에 `pytest.mark.timeout`을 걸기보다는 **연결 함수 자체에 connect timeout을 짧게 설정**하는 편이 근본적인 해결책입니다.

## 통과한 주요 항목 (281건, 인프라 제약 26건 제외 전부)

- `tests/agent/**`, `tests/data/**`(아래 표의 DB/Redis 의존 파일 제외 전부), `tests/ui_mcp/**`, `tests/integration/**` — Tool 로직, Runtime, Router, Streamlit 화면(로그인/예약/차트/관리자 승인 등), MCP 연결, RAG↔Runtime 연결, 정책/가드레일 시험까지 전부 정상 통과
- `tests/integration/policy/test_policy_flow.py` 4/4, `tests/integration/rag_agent/test_rag_agent_integration.py` 3/3 통과
- `tests/ui_mcp/test_mcp_client_errors.py` 8/8, `tests/ui_mcp/test_mcp_direct.py` 2/2, `tests/ui_mcp/test_main_integration.py` 1/1 통과

## 커밋 내역

| 커밋        | 내용                                                                                                                                                                                      |
| ----------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `2f5e21c` | `fix: 지도 이미지 경로, MCP 클라이언트 세션 재사용, RAG 연결 시험 버그 수정` — 아래 3개 코드 변경 + 이 보고서, `test` 브랜치에 로컬 커밋 완료 (원격 `origin/test`에는 아직 미push) |

커밋에 포함된 파일: [backend/app/mcp_client/client.py](../../backend/app/mcp_client/client.py), [frontend/components/route_map.py](../../frontend/components/route_map.py), [tests/integration/rag_agent/test_rag_agent_integration.py](../../tests/integration/rag_agent/test_rag_agent_integration.py), 이 보고서 파일. `.env`는 `.gitignore`에 포함되어 있어 커밋 대상에서 제외됨(의도된 동작).

## 조치 요약 / 다음 액션

1. ~~**[버그]** `frontend/components/route_map.py:11`의 지도 이미지 경로를 실제 파일명에 맞게 수정~~ → ✅ 완료·커밋됨 (`2f5e21c`)
2. ~~**[버그]** `McpClient`가 호출마다 세션을 새로 열어 반복 호출 시 타임아웃이 나는 문제~~ → ✅ 완료·커밋됨 (`2f5e21c`, 세션 재사용 리팩터링)
3. ~~**[버그]** RAG 연결 시험(n01/a01/a11)이 `rag_search`에 동기 함수를 잘못 연결 + A-11 단언문 자기모순~~ → ✅ 완료·커밋됨 (`2f5e21c`)
4. **[환경]** 루트 `requirements.txt`에 frontend 계열 의존성(`extra-streamlit-components`, `streamlit` 버전 상한)을 반영하거나, 셋업 문서에 "서비스별 `requirements.txt`를 모두 설치해야 함"을 명시 — 미착수
5. **[보류]** 26건 미검증 — 로컬 Docker(WSL2 미설치로 실패)와 사내망 `.env`(VPN 없이 접근 불가) 두 경로 모두 이 머신에서 막힘. VPN 연결 또는 WSL2 설치 중 하나가 준비되면 재실행 필요 (`.env`는 이미 사내망 값으로 작성돼 있고 `.gitignore`에 포함되어 있어 그대로 둠)
6. **[선택]** 커밋 `2f5e21c`를 원격(`origin/test`)에 push할지 결정 — 아직 push 안 됨

---

*생성: Claude Code · 2026-09-09*
