# 이원민 — MCP·프론트·조회 API 연결 계획

- 담당자 / 브랜치: 이원민 / `feat/lee-mcp-ui-p0`
- 수정할 파일(소유 범위): `mcp_server/`, `backend/app/mcp_client/`, `frontend/`, `backend/app/routers/health_router.py`, `backend/app/routers/admin_router.py`, `tests/ui_mcp/`, `eval/scenarios/mcp.json`
- 작업 순서: L1 계약 → L2 wrapper → L3 화면 → L4 health/admin → L5 ask 연결 → L6 장애 시험
- 입력 계약 / 넘길 출력: MCP 3종 `{name, description, input_schema}` 및 공통 Tool 결과 봉투; UI는 `AgentAskResponse`를 읽고 Tool 이름·인자를 보내지 않음
- 의존하는 상대 작업: 손영민의 공통 Schema/Runtime/ask, 최두나의 조회 함수·Trace 저장소·Settings
- 상대 구현 전 사용할 Fake: MCP SDK 결과 Fake, HTTP MockTransport, 고정 Agent 응답
- 완료 판단 테스트: tools/list·tools/call 3종, timeout/비정상 JSON, 관리자 토큰, HTTP Client, Streamlit 상태 렌더링
- 실행 결과: 담당 단위 시험 PASS, Streamlit AppTest PASS, 실제 MCP tools/list·tools/call 3종 PASS (`docs/reports/lee.md` 참조)
- 처음 실패한 Trace와 수정 내용: MCP SDK `list_tools()` 반환형을 dict로 가정한 시험을 실제 `list[Tool]` 계약으로 수정
- 남은 일 / 제한사항: Router의 `main.py` 조립과 Runtime의 MCP Client 주입은 손영민 소유 연결 작업. requirements 반영은 최두나 소유 작업
