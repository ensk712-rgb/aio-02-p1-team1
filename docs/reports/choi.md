# 최두나 작업 보고서 (C1~C5, 초안)

> 8.4절 공통 양식을 따른다. 이 보고서는 최두나 담당 파트(C1~C5)만 다룬다.
> C6(전체 결과 취합)은 손영민(Agent Runtime/API)·이원민(MCP/프론트) 파트가
> 구현된 뒤에만 완성할 수 있어, 이 문서는 P0 최종 취합본이 아니라
> **최두나 파트 진행 보고**다.

## 담당자 / 브랜치

- 담당자: 최두나 (ensk712@gmail.com)
- 브랜치: `choiduna`
- 기준 커밋: `fb10a6e` (직전 커밋들 위에서 작업, 아래 변경 사항은 **아직 커밋되지 않은 작업 트리 상태**)
- 실행 환경: Windows 10 Pro, Python 3.12.7, 로컬 venv(`.venv`)

## 수정할 파일 (소유 범위)

| 구분 | 파일 |
|---|---|
| 설정/환경 | `.env.example`, `requirements.txt`, `requirements/data.txt`, `requirements/agent.txt`(임시), `requirements/ui-mcp.txt`(임시), `pytest.ini`(임시) |
| Config | `backend/app/core/config.py` |
| Schema (임시, 원 소유자 손영민) | `backend/app/schemas/common.py`, `backend/app/schemas/tools.py` |
| Tool | `backend/app/tools/zoo_tools.py` |
| Repository | `backend/app/repositories/document_repository.py`, `session_repository.py`, `trace_repository.py` |
| Service | `backend/app/services/rag_service.py`, `eval_service.py` |
| 데이터 | `data/animal_cards/*.json`(4건), `data/operations/*.json`(4종) |
| 평가 | `eval/run.py`, `eval/scenarios/rag.json` |
| 테스트 | `tests/data/test_config_and_data.py`, `test_zoo_tools.py`, `test_rag_service.py`, `test_rag_service_safety.py`, `test_session_and_trace_repository.py`, `test_eval_service.py` |

> `requirements/agent.txt`, `requirements/ui-mcp.txt`, `pytest.ini`, `backend/app/schemas/*`는 원래
> 손영민 소유 파일이다. Gate 0 전에 팀원이 아직 없어 최두나가 계약 표(5장/3.4절)에 정의된
> 필드만 그대로 옮겨 임시로 채워 두었다. 손영민 담당자가 배정되면 리뷰 후 정식 소유권을
> 넘긴다.

## 작업 순서

C1(환경·데이터) → C2(조회 Tool 3종 + RAG) → C3(세션·Trace 저장소) → C4(근거 없음/문서
지시문 무시/검색 장애 테스트 + `eval/scenarios/rag.json`) → C5(평가 실행기 골격) 순서로
진행했다. 각 단계는 이전 단계의 산출물에 의존한다 (예: C2는 C1의 `DATA_DIR`/카드 데이터에,
C4/C5는 C2의 `rag_service`/`ToolRunResult` 계약에 의존).

## 입력 계약 / 넘길 출력

- **받은 입력**: 없음 (Gate 0 전, 팀원 미배정 상태라 손영민/이원민의 실제 산출물 없이 계약
  표(3.4절/5장/6장)만 참고해 진행)
- **넘길 출력**:
  - `ToolRunResult`/`ToolError`/`RetrievedChunk` 등 공통 스키마 (`backend/app/schemas/common.py`) — 손영민 확정 대기
  - `get_feeding_schedule`/`check_closure_status`/`find_habitat_route` (`backend/app/tools/zoo_tools.py`) — Executor(손영민)·MCP wrapper(이원민)가 그대로 재사용할 순수 함수
  - `retrieve_animal_info`/`retrieve_chunks` (`backend/app/services/rag_service.py`) — Runtime(손영민)이 호출할 RAG 준-Tool
  - `create_session`/`validate_session`/`save_run`/`list_runs` — Orchestration Service(손영민)·admin Router(이원민)가 사용할 세션/Trace 접근 함수
  - `run_scenarios`/`eval/run.py` — `/api/agent/ask`가 생기면 그대로 붙는 평가 실행기

## 의존하는 상대 작업

- 손영민의 `AgentProfile`/`Runtime`/`agent_orchestration_service.handle_ask` — 아직 없음. 위 함수들은 이 서비스가 호출하는 대상으로만 존재하고, 아직 실제로 호출되지는 않음.
- 이원민의 MCP Server/Client, Streamlit 화면 — 아직 없음. `zoo_tools.py`는 "FastAPI/Runtime/MCP를 import하지 않는다"는 계약을 지켜 작성해, `mcp_server/tools/zoo_read.py`가 그대로 재사용할 수 있게 해 둠.

## 상대 구현 전 사용할 Fake

- `/api/agent/ask`가 없으므로 `eval_service.run_scenarios()` 테스트는 `httpx.MockTransport`로 가짜 HTTP 응답을 만들어 검증했다 (`tests/data/test_eval_service.py`).
- 실제 서버에 연결할 수 없을 때 `eval/run.py`는 예외 대신 시나리오별 `SKIP`을 출력하도록 만들어, API가 없는 지금 상태에서도 실행 자체는 항상 성공(exit code 0)한다.

## 완료 판단 테스트

`python -m pytest tests/data -v` (60개), 그리고 `python -m eval.run --base-url http://127.0.0.1:8000`(서버 없는 상태에서 SKIP 처리 확인).

## 실행 결과 (PASS/FAIL/SKIP, 실제 실행 일시)

**실행 일시**: 2026-09-06 20:2x KST (Windows 로컬 시각) · **모드**: `mock`(단위 테스트, LLM/외부 API 미사용) · **명령**: `./.venv/Scripts/python.exe -m pytest tests/data -v`

| 파일 | 개수 | 결과 |
|---|---|---|
| `test_config_and_data.py` | 13 | 13 PASS |
| `test_zoo_tools.py` | 13 | 13 PASS |
| `test_rag_service.py` | 8 | 8 PASS |
| `test_rag_service_safety.py` | 3 | 3 PASS |
| `test_session_and_trace_repository.py` | 9 | 9 PASS |
| `test_eval_service.py` | 10 | 10 PASS |
| `test_zoo_tools.py`(route 관련 포함) | — | 위 13에 포함 |
| **합계** | **60** | **60 PASS / 0 FAIL / 0 SKIP** |

추가로 다른 작업 디렉토리(`%TEMP%\claude_test_cwd`)에서 동일 명령을 실행해 60개 전부
동일하게 PASS함을 확인했다 (C1 요구사항: "다른 현재 디렉토리에서도 경로 로딩 정상").

`eval/scenarios/rag.json`(5개 시나리오, N-01/N-01b/A-01/A-01b/A-11)을 실제
`http://127.0.0.1:8000`(아직 기동되지 않은 서버)에 대해 실행한 결과: **5 SKIP / 0 PASS / 0 FAIL**,
종료 코드 0. API가 없는 지금 단계에서 기대한 정상 동작이다.

**실제 LLM(`APP_MODE=openai`) 시연**: 미실시 (SKIP으로 기록). Agent Runtime/API가 아직 없어
연결할 대상 자체가 없음.

## 처음 실패한 Trace와 수정 내용

이번 파트는 자동화 실행 Trace(Runtime)가 아직 없어 "Trace"는 pytest 실패 로그로 대체한다.
개발 중 실제로 실패했다가 고친 항목:

1. **`ZoneInfoNotFoundError: 'Asia/Seoul'`** — Windows에는 IANA tzdata가 기본 포함되지 않음.
   `tzdata` 패키지를 설치하고 `requirements/data.txt`에 조건부(`sys_platform == "win32"`)로 추가해 해결.
2. **`get_feeding_schedule` 테스트 실패** — 해양관에 펭귄(11:00/14:30)과 물개(13:00/16:00) 두
   일정이 섞여 있는데, 정오 기준으로는 물개(13:00)가 펭귄(14:30)보다 먼저였다. 테스트의
   기대값이 틀렸던 것으로 확인, 시각을 나눠(정오/13:30 이후) 두 케이스로 재작성해 해결.
3. **`find_habitat_route("호랑이관","기린관")` 실패** — `routes.json`에 실제로 정의되지
   않은 조합이었다. 모든 시설 쌍을 다 채우는 대신, "정의 안 된 조합은 `ROUTE_NOT_FOUND`가
   정상"이라는 방향으로 테스트를 재작성.
4. **`ToolError.message`에 원본 예외 텍스트 노출** (`rag_service.retrieve_animal_info`) —
   검색 저장소 예외 발생 시 `str(exc)`를 그대로 담고 있어 "내부 예외 원문·키를 넣지
   않는다"는 계약 위반. 고정된 안전 문구로 교체(A-14/보안 테스트로 고정).
5. **`eval/run.py` 한글 출력 깨짐** — Windows 콘솔/파일 리다이렉션이 기본적으로 cp949로
   열려, 파일에 실제로 깨진 바이트가 기록되는 것을 확인(터미널 표시 문제가 아니었음).
   `sys.stdout.reconfigure(encoding="utf-8")`로 해결.

## 연결 시험: RAG → Runtime → ask API (7.3절, 시험 주관: 최두나)

`tests/integration/rag_agent/`에 7.3절 통과 기준(N-01, A-01, A-11)에 맞춘 연결
시험 3건을 추가했다. Fake `rag_search`가 아니라 **실제** `rag_service.retrieve_animal_info`를
`ToolExecutor`에 그대로 연결하고, Provider만 `ScriptedMockProvider`로 대체해
RAG 결과가 Runtime(`agents/runtime.py`, 손영민 소유)을 거쳐 `AgentAskResponse`까지
올바르게 전달되는지 확인했다.

**실행 결과: 3개 전부 FAIL.** 처음 실패한 Trace:

```
python -m pytest tests/integration/rag_agent -v
...
pydantic_core._pydantic_core.ValidationError: 1 validation error for ToolCallRecord
result
  Input should be a valid dictionary or instance of ToolRunResult [type=model_type, ...]
```

**원인**: `backend/app/schemas/common.py`(최두나가 Gate 0 전 임시로 채운 파일)와
`backend/app/schemas/tools.py`(손영민이 만든 정식 분리 구조) 양쪽에 `ToolRunResult`
/`ToolError`/`ToolCallRecord`가 **각각 독립적으로 다시 정의**되어 있다. 이름은
같지만 서로 다른 Python 클래스라서, `rag_service.py`가 반환하는 `common.ToolRunResult`
인스턴스를 `executor.py`가 만드는 `ToolCallRecord`(`tools.ToolRunResult`를 기대)에
넣는 순간 Pydantic이 타입 불일치로 예외를 던진다. 이 예외가 `runtime.py`의
`except Exception: status="error"`에 조용히 삼켜져서, 겉으로는 그냥 "완료된 요청인데
error 상태"처럼만 보이고 원인이 드러나지 않는다.

부수적으로 발견한 것: 같은 병합 과정에서 `schemas/tools.py` 안에
`FeedingScheduleInput`/`ClosureStatusInput`도 두 번 정의되어 있고(뒤 정의가 덮어씀),
`ClosureStatusData`/`ClosureItem` 근처에 `reason` 필드가 클래스 경계를 벗어나
엉뚱한 곳에 붙어 있다. 지금 당장 실행 경로에 영향은 없어 보이지만 잠재적 위험이다.

**처리 방향**: 9장 규칙("공통 Schema 변경은 손영민이 작성, 소비자가 리뷰")에 따라
`schemas/tools.py`·`schemas/common.py`는 이 보고서 작성자가 직접 고치지 않고,
실패하는 연결 시험을 그대로 남겨 손영민에게 공유한다. 제안하는 정리 방향은
`common.py`는 실제로 그 자리에 있어야 하는 `Source`/`TraceItem`만 남기고,
중복된 `ToolError`/`ToolRunResult`/`ToolCallRecord`/`RetrievedChunk`/`RagInput`/`RagSearchData`는
제거한 뒤 `tools.py`/`rag.py`를 단일 출처로 삼는 것이다. 그렇게 되면 `rag_service.py`
등 최두나 소유 파일들의 import 경로도 함께 바꿔야 하므로, 이 변경은 공동 작업이
필요하다.

- 실행 명령: `python -m pytest tests/integration/rag_agent -v`
- 실행 결과(현재): `test_n01_matched_card_flows_into_tool_calls_with_score_and_status` FAIL,
  `test_a01_no_match_completes_without_fabricating_an_answer` FAIL,
  `test_a11_document_instruction_stays_inert_through_runtime` FAIL — 셋 다 위와 같은
  `ToolRunResult` 타입 불일치가 원인.
- `sources`(RAG 근거를 API 응답의 `sources` 필드에 반영하는 로직)는 위 버그에 가려
  아직 검증되지 않았다. 스키마 문제를 먼저 고친 뒤 재확인이 필요하다.

## 남은 일 / 제한사항

- **C6(전체 결과 취합)**: 손영민(Runtime/API)·이원민(MCP/화면)의 실제 구현과 실행 결과가
  나와야 완성 가능. 지금은 최두나 파트만 기록된 진행 보고임.
- **`.env`의 실제 API 키 노출**: `git log`상 이미 히스토리에 커밋된 상태(첫 커밋부터).
  사용자가 "지금은 그대로 두기"로 결정해 손대지 않았음 — 원격에 push된 적이 있다면
  키 폐기(rotate)가 필요하다는 점은 별도로 전달함.
- **`.env`의 `APP_MODE=real` 등 이 프로젝트 스펙과 무관한 값**: 실제 Backend가 기동되기
  전에는 문제되지 않지만(모든 코드가 `try_get_settings()`로 안전하게 우회), 손영민의
  `main.py` 조립 단계에서는 `.env`를 이번 프로젝트용으로 교체해야 함.
- **실제 LLM 시연(`APP_MODE=openai`), Agent Runtime, MCP 서버, Streamlit 화면**: 전부
  미구현 (Gate 0 이후 손영민/이원민 담당 범위).
- **P1(C7: Pending/예약/세션 Memory)**: 계약만 파악해 둔 상태, 착수 전.
- **RAG 점수 알고리즘의 한계**: 완전한 형태소 분석이 아니라 조사/질문표현을 제거하는
  작은 규칙 기반이라, 대표 질문 5개 밖의 새로운 질문 형태에서는 씬규칙 추가가 필요할 수
  있음 (`document_repository.py`의 `_PARTICLE_SUFFIXES`/`_STOPWORDS`/`_SYNONYMS`에 새 규칙 추가로 대응).
