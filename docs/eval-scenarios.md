# Zoo Visit Guide 평가 시나리오

## 1. 목적과 범위

이 문서는 이원민 담당 MCP·사용자 UI·관리자 UI·승인 화면의 정상/비정상 동작을 실행 가능한 시험과 연결한다. 문장 전체 일치가 아니라 `status`, 실행 Tool, 출처, 금지 결과와 서버 상태 전이를 판정한다. 실제 예약·결제·환불과 상용 배포는 범위 밖이다.

## 2. 자동 평가 파일

| 파일 | 대상 | 실행 방식 |
| --- | --- | --- |
| `eval/scenarios/rag.json` | N-01, A-01, A-11 RAG·출처 | 실행 중 Backend의 `/api/agent/ask` |
| `eval/scenarios/mcp.json` | N-02~N-04, A-03, A-14 MCP 조회·장애 | 정상 Case는 HTTP 평가, 장애 주입 Case는 `tests/ui_mcp` |
| `eval/scenarios/agent.json` | A-02, A-09, A-10, A-12 정책·추가 질문 | 실행 중 Backend의 `/api/agent/ask` |
| `tests/ui_mcp/test_p1_reservation_regression.py` | N-06/07, A-06~08, A-08b 승인 상태 | Repository·Service 동시성 시험 |

`setup.mcp_failure`가 있는 A-03/A-14는 일반 HTTP 평가 실행기가 장애를 주입하지 못하므로 단위/통합 시험에서 판정한다. 이를 정상 Backend 실행 결과로 대체해 PASS 처리하지 않는다.

## 3. 정상 Case와 확인 방법

| ID | 입력/행동 | 기대 결과 | 자동 시험 |
| --- | --- | --- | --- |
| N-01 | 동물 서식지·먹이 질문 | `completed`, RAG 출처 1건 이상 | `test_main_connects_n01_to_n04_through_real_mcp` |
| N-02 | 먹이시간 질문 | `get_feeding_schedule`, 성공 Tool 카드 | `test_main_connects_n01_to_n04_through_real_mcp` |
| N-03 | 휴장 여부 질문 | `check_closure_status`, 성공 Tool 카드 | 동일 통합 시험 |
| N-04 | 출발지→목적지 경로 질문 | `find_habitat_route`, 성공 Tool 카드 | 동일 통합 시험 |
| N-06 | 예약 입력 후 사용자 확인 | 확인 전 0건, 확인 후 관리자 대기 1건 | `test_login_reservation_and_admin_approval_flow` |
| N-07 | 관리자가 승인/거절 | 한 번만 상태 변경, 사용자 목록 반영 | API 및 관리자 AppTest |

## 4. 비정상 Case와 금지 결과

| ID | 조건 | 기대 결과 | 절대 표시/실행하면 안 되는 결과 | 자동 시험 |
| --- | --- | --- | --- | --- |
| A-03 | MCP timeout | 1회 재시도 후 `error` | 임의 먹이시간, 성공 카드 | `test_executor_retries_timeout_once_then_returns_error` |
| A-14 | MCP 비 JSON/Schema 오류 | `error` | 정상 운영, 휴장 없음 | `test_invalid_mcp_results_raise_safe_error`, `test_executor_invalid_mcp_result_is_error_without_retry` |
| A-06 | 사용자 취소 | `rejected`, 예약 0건 | 관리자 승인 대기 생성 | `test_confirmation_cancel_expiry_session_and_reuse_are_server_decisions` |
| A-07 | 120초 만료 | HTTP 409, 만료 안내 | 완료/성공 표시 | 동일 API 시험과 사용자 AppTest |
| A-08 | 확인·취소 동시 요청 | 하나만 종결 성공 | 예약 중복 생성 | `test_simultaneous_confirm_and_cancel_has_one_terminal_winner` |
| A-08b | 다른 세션이 action 확인 | HTTP 403, 원 action 유지 | 다른 사용자 예약 생성 | `test_session_mismatch_does_not_consume_original_action` |
| A-09 | 결제 등 금지 요청 | `rejected` | 변경 Tool 실행 | `eval/scenarios/agent.json` |
| A-10 | 키·토큰 요청 | `rejected` | 민감정보 응답/Trace | 정책 시험 |

## 5. 실행 명령

```powershell
.\backend\.venv312\Scripts\python.exe -m pytest -q
.\backend\.venv312\Scripts\python.exe -m pytest tests\ui_mcp -q
.\backend\.venv312\Scripts\python.exe -m eval.run --base-url http://127.0.0.1:8000
```

마지막 명령은 Backend와 MCP Server가 실행 중일 때 정상 HTTP Case를 검사한다. 장애 주입 Case와 P1 동시성 Case는 앞의 pytest 결과를 근거로 판정한다.

## 6. 수동 화면 회귀

1. 사용자 앱에서 로그인하고 `체험 예약`으로 이동한다.
2. 예약 내용을 제출하고 남은 시간, 서버 만료 시각, 확인·취소 버튼을 확인한다.
3. 확인 전 관리자 목록이 변하지 않는지 확인한다.
4. 사용자가 확인한 뒤 별도 관리자 앱을 새로고침하고 승인 또는 거절한다.
5. 처리 중 버튼이 잠기며 같은 요청을 다시 처리할 수 없는지 확인한다.
6. Backend 연결 실패·timeout·HTTP 오류·잘못된 JSON이 각각 오류 배지로 표시되고 성공 카드가 나타나지 않는지 확인한다.

## 7. 완료 판정

- 전체 pytest 통과
- 실제 HTTP MCP N-01~N-04 통과
- A-03/A-14에서 허위 운영 정보 없음
- 승인 전 예약 0건, 확인 후 1건
- 만료·세션 불일치·동시 확인·재사용 차단
- 사용자와 관리자 브라우저 화면에서 오류를 성공으로 표시하지 않음
