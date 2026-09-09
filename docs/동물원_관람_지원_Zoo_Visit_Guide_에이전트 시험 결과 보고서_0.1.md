# 동물원 관람 지원 Zoo Visit Guide 에이전트 시험 결과 보고서_0.1

## 1. 시험 개요

### 1.1 시험 목적

본 시험은 프로젝트 폴더에 구현된 Zoo Visit Guide 에이전트가 사용자 요청을 안전하고 일관되게 처리하는지 소스코드와 자동화 시험으로 검증한다. 주요 검증 대상은 동물 정보 RAG, 동물원 운영 정보 Tool, 날씨 기반 코스 추천, 체험 예약 승인 흐름, 오류 및 반복 제한, 응답 근거와 Trace의 일치 여부다.

샘플 보고서가 요구하는 자기 성찰 적용 전후 비교도 검토했다. 그러나 현재 구현에는 자기 성찰 기능을 켜고 끄는 실행 옵션, 전용 reflection 노드, 적용 전 기준 버전 또는 동일 조건 반복 실행 로그가 없다. 따라서 근거가 없는 전후 성능 수치는 산출하지 않고, 현재 구현된 안전 실행 루프와 시험 결과를 평가한다.

### 1.2 시험 기준과 범위

- 시험일: 2026-09-09
- 대상 commit: `1ca0a25`
- 실행 Python: `C:\Users\Playdata\AppData\Local\Programs\Python\Python312\python.exe` 3.12
- 분석 범위: `backend/app/agents`, `backend/app/tools`, `backend/app/providers`, `backend/app/services`, `backend/app/routers`, `backend/app/mcp_client`, `mcp_server`, `eval`, `tests`
- 변경 범위: 구현 소스는 변경하지 않고 본 보고서만 작성

## 2. 구현 구조 분석

| 계층           | 주요 구현                                                       | 시험 관점                                                                       |
| -------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Agent Profile  | `backend/app/agents/zoo_guide_agent.py`, `registry.py`      | 지시문, 허용 Tool과 RAG collection, 미등록 Agent 차단                           |
| Runtime        | `backend/app/agents/runtime.py`                               | 금지 요청 선차단, Model-Tool 반복, 상태·종료 사유·Trace 구성, 단계·시간 제한 |
| Provider       | `mock_provider.py`, `openai_provider.py`                    | Tool schema 전달, 병렬 호출 금지, 응답 및 arguments 해석                        |
| Tool Executor  | `backend/app/tools/executor.py`                               | Allowlist, strict 입력 검증, 반복·총 호출 제한, MCP timeout 재시도             |
| RAG·운영 Tool | `rag_service.py`, `zoo_tools.py`, MCP server tools          | 검색 점수·출처, 운영 데이터 조회, 공통 결과 계약                               |
| 승인 흐름      | `approval_service.py`, 예약 Router·Repository                | 로그인, 세션 소유권, TTL, pending→processing→completed 전이                   |
| Orchestration  | `agent_orchestration_service.py`                              | 서버 세션·최근 대화·인증 컨텍스트 결합, 실행 결과 저장                        |
| 평가           | `eval/run.py`, `eval/scenarios/*.json`, `eval_service.py` | 기대 status, 필수·금지 Tool, 최소 출처 수 비교                                 |

현재 실행 흐름은 다음과 같다.

1. Orchestration Service가 세션과 인증 컨텍스트를 구성한다.
2. Runtime이 결제, 비밀정보, 권한 변경, 삭제, 질병 확진 등 금지 요청을 Provider 호출 전에 차단한다.
3. 코스 요청이면 날씨를 먼저 조회해 실내·실외 Tool 후보를 좁히며, 날씨 실패 시 기본 코스 Tool로 복귀한다.
4. Provider가 질문과 Tool schema를 바탕으로 Tool 호출 또는 최종 답변을 선택한다.
5. Executor가 허용 Tool, RAG collection, JSON 객체 여부와 Pydantic strict schema를 검증한다.
6. 조회는 MCP, 동물 정보는 RAG, 예약 제안은 승인 서비스로 분기한다.
7. 성공한 Tool 결과를 Provider에 다시 전달하고, Runtime이 실제 호출 기록을 기준으로 상태, 의도, 출처, 승인 정보와 Trace를 만든다.
8. 실패는 `needs_clarification`, `rejected`, `stopped`, `error` 중 하나로 종결한다.

이 구조는 검증과 제한을 포함한 안전 실행 루프이지만, 모델이 최초 답변을 별도로 비평하고 프롬프트나 Tool 선택을 수정한 뒤 재실행하는 명시적 자기 성찰 루프는 아니다.

## 3. 시험 데이터와 실행 결과

### 3.1 평가 시나리오 구성

`eval/scenarios`에는 정상 및 비정상 요청이 JSON으로 정의되어 있다. Agent 시나리오는 동물 정보 검색, 운영 조회, 코스 추천, 예약 제안, 필수값 누락, 근거 부족, 프롬프트 주입과 금지 요청을 포함한다. MCP 시나리오는 정상 조회, timeout과 잘못된 결과 계약을 포함하고, RAG 시나리오는 근거 일치와 미일치를 다룬다.

### 3.2 재실행 결과

전체 `pytest` 실행은 Backend import 시 `psycopg_pool` 누락으로 UI/API 시험 4개 파일의 수집 단계에서 중단됐다. 이후 수집 가능한 시험군을 분리해 실행했다.

| 시험군                   | PASS | FAIL | ERROR | 합계 | 판정         |
| ------------------------ | ---: | ---: | ----: | ---: | ------------ |
| Agent 단위시험           |   93 |    0 |     0 |   93 | 통과         |
| 데이터·RAG·저장소 시험 |   99 |   10 |    15 |  124 | 미통과       |
| 정책·RAG 통합시험       |    4 |    3 |     0 |    7 | 미통과       |
| 수집 가능한 UI·MCP 시험 |   39 |   28 |     2 |   69 | 미통과       |
| 분리 실행 합계           |  235 |   41 |    17 |  293 | 통과율 80.2% |

분리 실행의 80.2%는 현재 환경에서 나온 자동화 검증 통과율이다. 사용자 태스크 완료율, 실제 LLM의 도구 선택 정확도 또는 자기 성찰 효과를 뜻하지 않는다.

### 3.3 주요 실패 원인

| 구분               | 재현 결과                                  | 원인 판단                                                                    | 영향                                            |
| ------------------ | ------------------------------------------ | ---------------------------------------------------------------------------- | ----------------------------------------------- |
| Backend 시험 수집  | 4개 UI/API 파일 수집 오류                  | 현재 Python 환경에`psycopg_pool` 미설치                                    | Backend main 기반 시험 실행 불가                |
| PostgreSQL 시험    | 다수 fixture setup 오류                    | 동일 의존성 누락 및 persistent 저장소 실행 조건 미충족                       | pgvector, 예약 원자성, seed 검증 불가           |
| Redis 시험         | `127.0.0.1:6380` 연결 거부               | 시험 시 Redis listener 부재                                                  | 세션·Trace·TTL 영속화 검증 실패               |
| RAG-Agent 통합     | 3건 실패,`ToolRunResult` await TypeError | Executor는 비동기`rag_search`를 기대하지만 통합 fixture가 동기 함수를 주입 | 정상 검색, no-match, 주입 방어의 종단 검증 실패 |
| Vision 비동기 시험 | async 함수 실행 플러그인 오류              | 현재 환경에 적절한 pytest async plugin 미적용                                | Vision service 2건 미실행                       |
| Streamlit UI       | 27건 연쇄 실패                             | `extra_streamlit_components` 누락으로 app import 실패                      | 화면 기능 검증 불가                             |
| 실제 MCP 호출      | 운영 Tool 호출 timeout                     | MCP 초기화 응답을 10초 안에 받지 못함                                        | Tool 목록 이후 실제 호출 종단 검증 실패         |

위 실패에는 구현 결함과 실행환경 결함이 혼재한다. RAG의 동기/비동기 계약 불일치는 코드·시험 계약 문제이며, 누락 패키지와 외부 저장소 미기동은 현재 검증 환경 문제다. 둘을 모두 해결하기 전에는 전체 시스템 통과를 선언할 수 없다.

## 4. 오류 감지 기준과 판정

| 오류 유형                | 감지 기준                                                     | 기대 처리                                         | 현재 결과                                               |
| ------------------------ | ------------------------------------------------------------- | ------------------------------------------------- | ------------------------------------------------------- |
| 할루시네이션             | RAG/MCP 결과에 없는 사실·운영 정보를 최종 답변에 포함        | 근거가 없으면 확인 불가 안내, 허위 출처 금지      | 지시·RAG 임계값 구현, 통합 3건 실패로 종단 보증 미완료 |
| 도구 선택 오류           | Profile 미허용 Tool 또는 collection 선택                      | MCP 호출 전`TOOL_NOT_ALLOWED` 및 `rejected`   | Agent 단위시험 통과                                     |
| 파라미터 누락·타입 오류 | arguments가 JSON 객체가 아니거나 strict schema 불일치         | 호출 중지 후`INVALID_TOOL_ARGUMENTS`, 보완 질문 | Agent 단위시험 통과                                     |
| 응답 불일치              | 실제 Tool 호출·결과·출처와 status, intent, 최종 안내 불일치 | 실제`state.tool_calls` 기반 응답 구성           | 단위시험 통과, RAG 종단 검증 미통과                     |
| 동일 호출 반복           | 같은 Tool과 정규화 arguments의 반복 횟수 초과                 | 세 번째 실행 전에`REPEAT_LIMIT_REACHED`         | 통과                                                    |
| 전체 Tool 초과           | 실행당 Tool 시도 횟수 8회 초과                                | 아홉 번째 실행 전에 중단                          | 통과                                                    |
| Agent 단계 초과          | Model 단계 6회 초과                                           | 다음 Model 호출 전`stopped`                     | 통과                                                    |
| 전체 실행 timeout        | 실행 90초 초과                                                | `error`, `run_timeout`                        | 단위시험 통과                                           |
| MCP timeout              | Tool 응답 제한시간 초과                                       | 동일 인자로 1회 재시도 후 오류 종료               | 오류 주입시험 통과, 실제 MCP 호출 실패                  |
| 금지 요청                | 결제·비밀정보·역할 변경·삭제·질병 확진 표현               | Provider와 Tool 호출 없이`rejected`             | 통과                                                    |
| 예약 승인 오류           | 미인증, 타 세션, 만료, 중복 결정                              | 예약 미생성 또는 안전한 거절                      | 단위시험 통과, persistent E2E는 환경 오류               |
| 프롬프트 주입            | 검색 문서 속 명령 실행 또는 비밀정보 노출                     | 문서를 데이터로만 취급                            | 정책 존재, RAG 통합 실패로 종단 검증 미완료             |

## 5. 오류별 재시도와 대체 전략

| 오류                      |           재시도 | 구현된 전략                            | 종료 조건                        |
| ------------------------- | ---------------: | -------------------------------------- | -------------------------------- |
| 필수 인자 누락·타입 오류 |              0회 | Tool 호출 중지, 추가 정보 요청         | 필수값 확보 또는 사용자 취소     |
| 미허용 Tool               |              0회 | Allowlist에서 즉시 차단                | `rejected`                     |
| MCP 조회 timeout          |              1회 | 같은 검증 인자로 재호출                | 총 2회 실패 후`error`          |
| MCP 비 JSON·실패 응답    |              0회 | 표준 Tool 오류로 변환                  | `error`                        |
| RAG 근거 부족             |              0회 | 임계값 미만 chunk 제외, 확인 불가 안내 | `matched=false` 결과 전달      |
| 동일 Tool 반복            |    최대 2회 실행 | 세 번째 실행 전 차단                   | `stopped`, 반복 제한 사유 기록 |
| 전체 Tool 호출            |    최대 8회 실행 | 아홉 번째 실행 전 차단                 | `stopped`, 호출 한도 사유 기록 |
| Agent 단계                |         최대 6회 | 다음 Model 호출 전 차단                | `stopped`                      |
| 날씨 조회 실패            | 별도 재시도 없음 | 기본 코스 Tool 후보로 복귀             | 코스 처리 계속 또는 후속 오류    |
| 예약 변경                 | 자동 재시도 없음 | 로그인·세션·TTL·상태 재검증         | 승인/취소/만료/거절 상태         |
| 금지 요청                 |              0회 | Provider 이전 정책 차단                | `rejected`                     |

예약처럼 상태를 변경하는 Tool을 자동 재시도하지 않고, 조회 timeout만 제한적으로 재시도하는 정책은 중복 변경 위험을 줄인다. 다만 현재 구현은 오류 원인을 모델이 분석해 다른 Tool로 전환하거나 프롬프트를 자동 조정하는 일반화된 대체 전략은 제공하지 않는다.

## 6. 오류 감지부터 재검증까지의 입출력

### 6.1 필수 파라미터 누락

- 입력: 예약 또는 조회에 필요한 필수값이 없는 Tool arguments
- 감지: strict Pydantic schema 검증 실패
- 원인: 필수 필드 누락 또는 타입 불일치
- 수정 전략: Tool을 실행하지 않고 보완 질문 반환
- 재실행: 사용자가 필수값을 제공한 새 요청에서만 가능
- 검증 출력: `needs_clarification`, Tool 실행 기록 없음

### 6.2 MCP timeout

- 입력: 허용된 조회 Tool과 유효한 arguments
- 감지: `asyncio.wait_for` 제한시간 초과
- 원인: MCP 서버 지연, 미기동 또는 통신 장애
- 수정 전략: 같은 요청을 1회 재시도
- 재실행: 최초 호출 포함 최대 2회
- 검증 출력: 성공 Tool 결과 또는 `MCP_TIMEOUT` 기반 `error`

### 6.3 반복 호출

- 입력: 같은 Tool과 같은 정규화 arguments의 반복 호출
- 감지: `repeat_counts`가 허용 횟수에 도달
- 원인: Provider가 동일 행동을 반복 선택
- 수정 전략: 다음 Tool 실행 차단
- 재실행: 없음
- 검증 출력: `stopped`, `repeat_limit_reached`, 제한 Trace

### 6.4 예약 승인

- 입력: 예약 제안과 이후 confirm/cancel 요청
- 감지: 로그인, 인증 세션, action 소유 세션, TTL, 현재 상태 검사
- 원인: 미인증, 타 세션 action, 만료 또는 중복 결정
- 수정 전략: 변경 Tool을 재시도하지 않고 안전하게 거절
- 재실행: 유효한 새 action을 생성한 경우에만 가능
- 검증 출력: `pending`, `processing`, `completed`, `cancelled`, `expired` 중 실제 상태

## 7. 프롬프트와 파라미터 조정 이력

Git 이력 기반 버전별 성능 비교 로그는 본 시험 범위에서 확인되지 않았다. 현재 소스에서 확인되는 조정 사항은 다음과 같다.

| 대상            | 현재 조정 내용                                                                  | 확인 근거                             |
| --------------- | ------------------------------------------------------------------------------- | ------------------------------------- |
| Agent 지시문    | 검색·Tool 결과 없는 사실 추측 금지, 필수정보 질문, 예약 확인 전 완료 표현 금지 | Profile 및 Runtime 단위시험           |
| OpenAI Provider | Tool schema 전달,`parallel_tool_calls=False`, Tool arguments JSON 해석        | Provider 단위시험                     |
| Runtime         | 최대 6단계, 전체 90초, 금지 요청 선차단, 상태·종료 사유 구성                   | Runtime 단위시험                      |
| Executor        | 동일 호출 최대 2회, 전체 Tool 최대 8회, MCP 재시도 1회                          | Executor 단위시험                     |
| RAG             | 허용 collection, 검색 점수 임계값, 출처 메타데이터                              | RAG 단위시험 일부 통과, 통합시험 실패 |
| 예약            | 로그인·세션 소유권·TTL·상태 전이, 변경 Tool 자동 재시도 금지                 | 예약 Runtime·Repository 시험         |

프롬프트 문구의 변경 전후, temperature 등 생성 파라미터 변경 전후, 동일 입력 반복 결과를 연결하는 원본 로그가 없으므로 각 조정의 정량 개선 효과는 산출할 수 없다.

## 8. 자기 성찰 적용 전후 비교

| 지표                         |   적용 전 | 현재 구현 | 판정 근거                                                 |
| ---------------------------- | --------: | --------: | --------------------------------------------------------- |
| 태스크 완료율                | 측정 불가 | 측정 불가 | 동일 평가셋의 reflection off/on 실행 결과 없음            |
| 도구 선택 정확도             | 측정 불가 | 측정 불가 | 실제 LLM Tool 선택 로그를 정답 라벨과 건별 집계하지 않음  |
| 응답 일관성                  | 측정 불가 | 측정 불가 | 동일 입력 반복 및 Tool 원본 대비 최종 답변 비교 로그 없음 |
| 평균 재시행 횟수             | 측정 불가 | 측정 불가 | 전체 시나리오별 재시행 횟수 집계 결과 없음                |
| Agent 단위시험 통과율        | 해당 없음 |    100.0% | 93/93 통과                                                |
| 분리 실행 자동화 시험 통과율 | 해당 없음 |     80.2% | 235/293 통과, FAIL 41·ERROR 17                           |

정량 전후 비교를 위해서는 동일 commit과 동일 평가 시나리오를 대상으로 자기 성찰 비활성·활성 조건을 각각 여러 번 실행해야 한다. 각 `run_id`에 입력, Model 응답, 선택 Tool, arguments, Tool 결과, 최종 답변, 재시도 횟수, 종료 사유를 저장하고 동일 판정기로 평가해야 한다.

## 9. 종합 판정과 개선 우선순위

### 9.1 종합 판정

**조건부 미통과**

Agent 핵심 정책과 실행 제한은 93개 단위시험에서 모두 통과했다. 그러나 RAG-Agent 통합 계약 오류가 재현됐고, 현재 프로젝트 환경에서 Backend·persistent 저장소·Streamlit UI·실제 MCP 호출의 종단 검증이 완료되지 않았다. 따라서 단위 수준의 안전장치는 확인됐지만, Zoo Visit Guide 에이전트 전체를 운영 준비 완료로 판정할 수 없다.

### 9.2 개선 우선순위

1. `ToolExecutor`의 `rag_search` 비동기 계약과 통합시험 fixture를 일치시키고 RAG 3개 종단 시험을 모두 통과시킨다.
2. 프로젝트 전용 가상환경을 만들고 루트·Backend·Frontend 요구사항을 일관되게 설치해 `psycopg_pool`, async pytest plugin, `extra_streamlit_components` 누락을 제거한다.
3. PostgreSQL(pgvector)과 Redis를 정해진 포트로 기동한 뒤 seed, 예약 원자성, 세션·Trace TTL과 persistent E2E를 재실행한다.
4. 실제 MCP 프로세스의 초기화 timeout 원인을 확인하고 Tool 목록 조회뿐 아니라 운영 Tool 3종 호출까지 검증한다.
5. 명시적 자기 성찰을 평가하려면 off/on 플래그와 Trace 필드를 추가하고 동일 시나리오 반복 실행 결과를 보존한다.
6. 전체 `pytest`가 수집 오류 없이 종료되고 평가 시나리오 원본 로그가 확보된 뒤 완료율, 도구 선택 정확도, 응답 일관성, 평균 재시행 횟수를 다시 산출한다.

## 10. 재현 명령

```powershell
py -3.12 -m pytest -q --disable-warnings --maxfail=0
py -3.12 -m pytest tests/agent -q
py -3.12 -m pytest tests/data -q --maxfail=0
py -3.12 -m pytest tests/integration -q --maxfail=0
```

환경 의존 시험은 프로젝트 요구사항을 설치한 전용 가상환경과 PostgreSQL·Redis·MCP 프로세스가 준비된 상태에서 다시 실행해야 한다.
