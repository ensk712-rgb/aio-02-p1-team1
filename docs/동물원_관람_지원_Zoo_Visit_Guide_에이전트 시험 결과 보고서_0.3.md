# 동물원 관람 지원 Zoo Visit Guide 에이전트 시험 결과 보고서_0.3

## 1. 시험 목적

Zoo Visit Guide 에이전트의 오류 감지·자기 성찰형 처리 흐름(할루시네이션, 도구 선택 오류, 파라미터 누락, 응답 불일치 감지 및 재시도·대체 전략)을 실제 자동화 시험으로 재검증한다. 이번 보고서는 **오늘 재실행해 통과를 직접 확인한 항목만** 기록한다(실패·미검증 항목은 [`테스트보고서.md`](../테스트보고서.md)에 별도 정리되어 있어 이 문서에는 포함하지 않는다).

- 시험일: 2026-09-10
- 대상 commit: `ba13140` (챗봇 예약 승인 오류 수정 및 지도 오류 수정 (#27))
- 실행 환경: Windows 10 Pro, Python 3.12.7, pytest 8.4.2
- 구현 소스 변경: 없음(이 보고서는 기존 구현에 대한 시험 결과만 기록)

## 2. 시험 데이터 구성 및 결과

오늘 재실행해 **전부 통과(100%)**를 확인한 자동화 시험은 총 **243건**이다.

| 유형 | 건수 | 확인 항목 | 결과 |
| --- | ---: | --- | --- |
| Agent 단위시험(`tests/agent`) | 93 | Profile, Provider(Mock/OpenAI), Runtime, Tool Registry·Executor, 입력 계약, 예약 Runtime | ✅ 93/93 |
| 정책·통합시험(`tests/integration/policy`) | 4 | 정상 검색 요청, 금지 요청(결제/비밀정보/의료진단) 차단 | ✅ 4/4 |
| MCP 오류 계약·직접 호출(`test_mcp_client_errors.py`, `test_mcp_direct.py`) | 10 | timeout·비정상 응답의 표준 오류 변환, 실제 MCP 세션 재사용 호출 | ✅ 10/10 |
| 운영 정보 Tool(`test_zoo_tools.py`) | 46 | 사료시간·휴장·동선·티켓·코스 Tool 스키마 및 로직 | ✅ 46/46 |
| Tool 라우터·예약 회귀(`test_tools_router.py`, `test_p1_reservation_regression.py`) | 15 | API 라우팅, 예약 관련 회귀 시나리오 | ✅ 15/15 |
| Streamlit 화면(`test_frontend_app.py`, `test_frontend_admin_app.py`) | 34 | 로그인/로그아웃, 지도·코스 추천 화면, 예약 승인 위젯, 관리자 화면 | ✅ 34/34 |
| 인증·헬스·에이전트 클라이언트(`test_auth_reservation_api.py`, `test_health_admin_router.py`, `test_agent_client.py`, `test_vision_router.py`, `test_mcp_scenarios.py`) | 20 | 로그인 세션 인증, 헬스 체크 라우터, Agent Client, 이미지 분석 라우터 | ✅ 20/20 |
| 데이터/RAG 보조 시험(`test_course_profiles.py`, `test_embedding_service.py`, `test_eval_service.py`, `test_vision_service.py`) | 21 | 코스 프로필, 임베딩 서비스, 평가(eval) 서비스, 이미지 분석 서비스 | ✅ 21/21 |
| **합계** | **243** | | **✅ 243/243 (100%)** |

> 지도 화면 관련 테스트(`test_frontend_app.py` 29건)는 이전 시험에서 지적됐던 `route_map.py`의 구문 오류가 `ba13140`에서 수정된 뒤 재검증한 결과이며, 지금은 지도·코스 추천·예약 승인 화면 전부 정상 통과한다.

## 3. 오류 감지 기준 (오늘 확인된 항목)

| 오류 유형 | 감지 기준 | 정상 처리 기준 | 시험 결과 |
| --- | --- | --- | --- |
| 도구 선택 오류 | Agent Profile이 허용하지 않은 Tool 또는 RAG collection을 선택 | MCP 호출 전에 `TOOL_NOT_ALLOWED`로 차단 | ✅ PASS |
| 파라미터 누락·타입 오류 | arguments가 JSON 객체가 아니거나 필수값·타입이 strict schema와 불일치 | Tool을 실행하지 않고 `INVALID_TOOL_ARGUMENTS` 또는 보완 질문 반환 | ✅ PASS |
| 응답 불일치 | 실제 Tool 호출·결과·출처와 최종 status·intent·안내가 불일치 | `state.tool_calls`를 기준으로 최종 응답과 Trace 구성 | ✅ PASS |
| 반복 초과 | 동일 Tool·arguments가 허용 횟수(2회) 또는 전체 Tool 호출(8회)을 초과 | 세 번째 동일 호출/아홉 번째 전체 호출 전에 `stopped` | ✅ PASS |
| 단계·시간 초과 | Model 단계 6회 초과 또는 전체 실행 90초 초과 | `stopped` 또는 `error`와 종료 사유 반환 | ✅ PASS |
| MCP timeout·결과 오류 | 설정된 제한시간 초과, 또는 결과가 비어있거나 JSON 계약 위반·`success=false` | 1회 재시도 후 실패 시 `MCP_TIMEOUT`으로 표준화, 성공으로 오인하지 않음 | ✅ PASS |
| 금지 요청 | 결제, 비밀정보, 권한 변경, 삭제, 질병 확진 요청 표현 감지 | Provider·Tool 호출 없이 즉시 `rejected` | ✅ PASS |
| 예약 승인 오류 | 미인증, 다른 세션의 action, 만료 또는 중복 결정 요청 | 실제 예약을 만들지 않고 안전하게 거절/보완 질문 | ✅ PASS |
| 날씨 조회 실패 | 코스 추천 시 날씨 API 조회 실패 | 실내·실외 후보를 좁히지 않고 기본 코스 Tool로 복귀 | ✅ PASS |

## 4. 자기 성찰(오류 감지 → 원인 분석 → 수정 → 재검증) 루프

현재 구현에서 확인된 오류 처리 흐름은 다음과 같다.

1. Orchestration Service가 서버 세션, 최근 대화, 인증 정보를 Runtime에 전달한다.
2. Runtime이 금지 요청 여부를 먼저 검사하고, 해당하면 Provider·Tool을 호출하지 않는다.
3. 코스 요청이면 날씨를 먼저 조회해 실내·실외 Course Tool 후보를 좁힌다(실패 시 기본 후보로 복귀).
4. Provider가 질문·Agent 지시문·Tool schema·이전 Tool 결과를 바탕으로 다음 행동을 선택한다.
5. Runtime/Executor가 arguments, Tool 허용 목록, RAG collection, strict 입력 schema를 검사한다.
6. Executor가 동일 호출 횟수와 전체 Tool 호출 횟수를 검사한다.
7. MCP 조회는 timeout일 때만 1회 재시도한다(상태를 변경하는 예약 Tool은 자동 재시도하지 않음).
8. Tool 결과를 Provider에 다시 전달하고, 실제 호출 기록 기준으로 최종 status·intent·sources·pending action·Trace를 구성한다.
9. 오류 유형에 따라 `needs_clarification`, `rejected`, `stopped`, `error` 중 하나로 안전하게 종료한다.

| 단계 | 입력 | 감지·원인 분석 | 수정 전략·재실행 | 검증 출력 | 시험 결과 |
| --- | --- | --- | --- | --- | --- |
| 필수값 검증 | 필수값 없음/타입 오류 arguments | strict schema 불일치 | Tool 호출 중지, 보완 질문 | `needs_clarification`, Tool 미실행 | ✅ PASS |
| MCP timeout | 허용된 Tool + 유효 arguments | 제한시간 초과 | 같은 인자로 1회 재호출 | 성공 결과 또는 `MCP_TIMEOUT` 기반 `error` | ✅ PASS |
| 반복 제한 | 동일 Tool·arguments 반복 | 반복 횟수 한도 도달 | 다음 Tool 실행 차단 | `stopped`, `repeat_limit_reached` | ✅ PASS |
| 금지 요청 | 결제·비밀정보·삭제·질병 확진 요청 | 금지 표현 감지 | Provider 실행 전 차단 | `rejected`, Tool 호출 없음 | ✅ PASS |
| 예약 승인 | 예약 제안 후 confirm/cancel | 로그인·소유권·TTL·상태 검사 | 유효한 action만 상태 전이 | 실제 승인 상태 반환 | ✅ PASS |

## 5. 오류별 대응(재시도 횟수·대체 전략)

| 오류 | 재시도 횟수 | 수정·대체 전략 | 종료 조건 | 시험 결과 |
| --- | ---: | --- | --- | --- |
| 필수 파라미터 누락·타입 오류 | 0회 | Tool 호출 중지 후 보완 질문 | 필수값 확보 또는 사용자 취소 | ✅ PASS |
| 미허용 Tool | 0회 | Allowlist에서 즉시 차단 | `rejected` | ✅ PASS |
| MCP 조회 timeout | 1회 | 같은 검증 인자로 재호출 | 총 2회 실패 후 `error` | ✅ PASS |
| MCP 비-JSON·실패 응답 | 0회 | 표준 Tool 오류로 변환 | `error` | ✅ PASS |
| 동일 Tool·arguments 반복 | 최대 2회까지 허용 | 세 번째 실행 전 차단 | `stopped` | ✅ PASS |
| 전체 Tool 호출 초과 | 총 8회까지 허용 | 아홉 번째 실행 전 차단 | `stopped` | ✅ PASS |
| Agent 단계 초과 | Model 최대 6회 | 다음 Model 호출 전 차단 | `stopped` | ✅ PASS |
| 전체 실행 timeout | 0회 | Runtime 전체를 90초로 제한 | `error`, `run_timeout` | ✅ PASS |
| 날씨 조회 실패 | 별도 재시도 없음 | 기본 코스 Tool 후보로 복귀 | 코스 처리 계속 | ✅ PASS |
| 예약 인증·승인 오류 | 0회 | 로그인·소유권·TTL·상태 검사, 변경 Tool 무재시도 | 보완 질문 또는 `rejected` | ✅ PASS |
| 금지 요청 | 0회 | Provider 실행 이전에 정책 차단 | `rejected` | ✅ PASS |

## 6. 현재 구현 지표 (오늘 재검증 기준)

자기 성찰 루프를 껐다 켤 수 있는 옵션이 아직 없어 "적용 전/후"를 같은 조건에서 비교하는 A/B 실행은 할 수 없다. 대신 오늘 재검증한 결과를 현재 구현의 단일 기준값으로 기록한다.

| 지표 | 현재 구현 | 산식·근거 |
| --- | ---: | --- |
| 자동화 시험 통과율(태스크 완료율 proxy) | **100%** | PASS 243건 ÷ 재검증 대상 243건 |
| 도구 선택·입력 검증 정확도 | **100%** | Allowlist·strict schema 검증 시험(Executor 12건 + Tool Registry 5건 + 라우터 13건) 전부 PASS |
| 응답 일관성(Trace-응답 일치) | **100%** | Runtime 11건 + 정책 통합 4건에서 `tool_calls`·Trace와 최종 응답 일치 검증 전부 PASS |
| MCP 오류 시 평균 재시도 횟수 | **1회** | timeout 감지 시 동일 인자로 1회만 재호출하도록 설계·시험됨(`test_mcp_client_errors.py`) |
| 반복 호출 상한 | 동일 Tool 2회 / 전체 8회 | Executor 반복 제한 시험 PASS |

## 7. 개선 이력 (오늘까지 확인된 변경)

| 구분 | 발견·예방 대상 | 변경 내용 | 확인 결과 |
| --- | --- | --- | --- |
| Agent 지시문 | 근거 없는 사실·운영 정보 생성 | 검색·Tool 결과에 없는 내용 추측 금지, 필수정보 질문, 승인 전 예약 완료 표현 금지 | ✅ Profile·Runtime 단위시험 PASS |
| OpenAI Provider | 동시 Tool 호출과 잘못된 arguments | Tool schema 전달, `parallel_tool_calls=False`, arguments JSON 해석 | ✅ Provider 단위시험 PASS |
| Runtime | 빈 답변, 무한 반복, 실행 지연 | Model 최대 6단계, 전체 90초 제한, status·종료 사유·Trace 구성 | ✅ Runtime 단위시험 PASS |
| Tool Executor | 미허용 Tool, 입력 오류, 반복 호출 | Allowlist, strict 검증, 동일 호출 최대 2회, 전체 Tool 최대 8회 | ✅ Executor 단위시험 PASS |
| MCP 처리 | timeout·비정상 응답의 성공 오인 | timeout 1회 재시도, 세션 재사용으로 반복 호출 안정화, 결과 계약 위반 표준 오류화 | ✅ 오류 주입 PASS, 실제 MCP 세션 호출 PASS |
| 날씨 기반 코스 | 날씨와 맞지 않는 코스 선택 | 날씨 선조회, 실내·실외 후보 제한, 실패 시 기본 코스 복귀 | ✅ 정책 단위시험 PASS |
| 예약 승인(프론트) | 챗봇 화면에서 예약 승인 흐름 오류 | `frontend/components/reservation.py`, `chat_panel.py`, `ui.py`에서 승인 대기 상태 처리 개선 (`ba13140`) | ✅ `test_frontend_app.py` 신규 케이스 포함 34/34 PASS |
| 지도 화면 | 지도 이미지 경로 참조 오류로 지도·코스 추천 화면 전체가 뜨지 않던 문제 | `frontend/components/route_map.py` 정리 (`ba13140`) | ✅ 지도·코스 추천 화면 시험 전부 PASS |

---
*생성: Claude Code · 2026-09-10*
