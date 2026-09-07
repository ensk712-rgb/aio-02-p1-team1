# 설계 결정 기록

## P0-001: 단일 Agent 사용

- 결정: P0에서는 `zoo_guide` Agent 하나만 등록한다.
- 이유: 다중 Agent 분업보다 Tool 결과 재전달과 Backend 정책 통제를 명확히 학습하는 것이 우선이다.

## P0-002: Provider와 Runtime 책임 분리

- 결정: Provider는 다음 행동 또는 최종 답변만 제안하고, Runtime이 반복·종료를 관리한다.
- 이유: Mock Provider와 OpenAI Provider를 같은 Runtime에서 교체할 수 있어야 한다.

## P0-003: Tool 실행은 Backend만 담당

- 결정: Provider는 Tool을 직접 실행하지 않는다.
- 이유: Executor가 allowlist, Pydantic 입력 검증, 반복 제한을 적용해야 하기 때문이다.

## P0-004: 허용 Tool 목록 제한

- 결정: `zoo_guide`는 RAG Tool 1개와 운영 MCP Tool 3개만 사용할 수 있다.
- 허용 RAG: `retrieve_animal_info`
- 허용 MCP: `get_feeding_schedule`, `check_closure_status`, `find_habitat_route`
- 이유: MCP Server에서 예상하지 못한 Tool이 발견되어도 Provider에 노출하지 않기 위해서다.

## P0-005: 반복 Tool 호출 제한

- 결정: 같은 Tool과 같은 인자는 최대 2회 실행한다.
- 결과: 세 번째 실행 전 `stopped` 상태로 종료한다.
- 이유: Agent가 같은 조회를 무한 반복하는 상황을 차단하기 위해서다.

## P0-006: 금지 요청 사전 차단

- 결정: 결제, 민감정보 요청, 동물 질병 확진 요청은 Provider와 Tool 실행 전에 Backend가 차단한다.
- 결과: `rejected` 상태와 일반 안내 문장을 반환한다.
- 이유: LLM의 답변 선택에만 의존하지 않고 P0 안전 요구사항을 결정적으로 보장하기 위해서다.

## P0-007: OpenAI Tool 결과 재전달

- 결정: OpenAI Responses API의 `function_call_output`에 직전 응답의 `call_id`를 사용한다.
- 이유: Tool 결과가 어떤 Function Call의 결과인지 OpenAI가 정확히 연결해야 하기 때문이다.

## P0-008: 테스트 방식

- 결정: 단위 테스트에서는 Fake MCP Client, Fake Repository, Scripted Mock Provider를 사용한다.
- 이유: 네트워크, API Key, 상대 팀 구현 없이 정책과 Runtime을 반복 가능하게 검증하기 위해서다.