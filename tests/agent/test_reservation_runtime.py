"""Agent 예약 Tool이 Pending Action으로 안전하게 전환되는지 검증한다."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from backend.app.agents.registry import get_agent_profile
from backend.app.agents.runtime import RuntimeSettings, run_agent
from backend.app.providers.mock_provider import ScriptedMockProvider
from backend.app.schemas.agent import AgentAskRequest, ModelToolCall, ModelTurn
from backend.app.schemas.tools import ToolRunResult
from backend.app.tools.executor import ToolExecutor


class FakeMcpClient:
    """예약 Tool이 MCP로 전송되지 않는지 확인하기 위한 가짜 MCP Client다."""

    async def list_tools(self) -> list[dict[str, Any]]:
        """이 테스트에는 MCP 조회 Tool이 필요 없으므로 빈 목록을 반환한다."""
        return []

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolRunResult:
        """예약 Tool이 MCP로 호출되면 테스트를 실패시킨다."""
        raise AssertionError(
            f"예약 Tool은 MCP로 호출하면 안 됩니다: {name}, {arguments}"
        )


def _create_executor(
    proposed_actions: list[dict[str, Any]],
) -> ToolExecutor:
    """예약 Pending Action 생성 여부를 기록하는 테스트용 Executor를 만든다."""

    def fake_rag_search(query: str, collection: str) -> ToolRunResult:
        """이 테스트에서는 RAG를 사용하지 않아 호출되면 실패시킨다."""
        raise AssertionError(
            f"예약 테스트에서 RAG 호출은 예상하지 않았습니다: {query}, {collection}"
        )

    def fake_reservation_proposer(
        *,
        session_id: str,
        user_id: str,
        program: str,
        visit_time: str,
        headcount: int,
    ) -> dict[str, Any]:
        """실제 예약 대신 확인용 Pending Action을 만들어 기록한다."""
        action = {
            "action_id": "action_reservation_001",
            "tool_name": "reserve_experience_program",
            "summary": f"{visit_time} {program} {headcount}명",
            "approval_status": "pending",
            "expires_at": "2026-09-08T12:02:00+00:00",
            # 실제 저장소는 내부 처리에 필요한 값도 가질 수 있다.
            # Runtime 응답에서는 이 값이 노출되면 안 된다.
            "arguments": {
                "user_id": user_id,
                "program": program,
                "visit_time": visit_time,
                "headcount": headcount,
            },
        }
        proposed_actions.append(
            {
                "session_id": session_id,
                "user_id": user_id,
                **action,
            }
        )
        return action

    return ToolExecutor(
        rag_search=fake_rag_search,
        mcp_client=FakeMcpClient(),
        reservation_proposer=fake_reservation_proposer,
    )


def test_reservation_tool_creates_pending_action_not_reservation() -> None:
    """로그인 사용자의 예약 요청은 확인 대기 상태로 종료해야 한다.

    이 테스트는 실제 예약 생성 대신 Pending Action만 만들어지는지,
    사용자 ID가 응답에 노출되지 않는지를 함께 확인한다.
    """
    proposed_actions: list[dict[str, Any]] = []
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_reservation_1",
                calls=[
                    ModelToolCall(
                        call_id="call_reservation_1",
                        name="reserve_experience_program",
                        arguments_json=(
                            '{"program":"사육사 체험",'
                            '"visit_time":"2026-09-10T15:00:00+09:00",'
                            '"headcount":2}'
                        ),
                    )
                ],
            )
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="9월 10일 15시에 사육사 체험 2명 예약해 줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=_create_executor(proposed_actions),
            settings=RuntimeSettings(),
            reservation_user_id="TEST",
            reservation_session_id="auth_session_test",
        )
    )

    assert response.status == "confirmation_required"
    assert response.termination_reason == "reservation_confirmation_required"
    assert response.intent == "tool"
    assert len(response.tool_calls) == 1
    assert response.tool_calls[0].name == "reserve_experience_program"

    assert response.pending_action == {
        "action_id": "action_reservation_001",
        "tool_name": "reserve_experience_program",
        "summary": "2026-09-10T15:00:00+09:00 사육사 체험 2명",
        "approval_status": "pending",
        "expires_at": "2026-09-08T12:02:00+00:00",
    }

    assert len(proposed_actions) == 1
    assert proposed_actions[0]["session_id"] == "auth_session_test"
    assert proposed_actions[0]["user_id"] == "TEST"

    # API 응답에는 내부 사용자 정보와 원본 실행 인자를 노출하지 않는다.
    assert "arguments" not in response.pending_action
    assert "user_id" not in response.pending_action


def test_reservation_tool_requires_login_before_pending_action() -> None:
    """로그인하지 않은 사용자는 예약 Pending Action을 만들 수 없어야 한다."""
    proposed_actions: list[dict[str, Any]] = []
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_reservation_2",
                calls=[
                    ModelToolCall(
                        call_id="call_reservation_2",
                        name="reserve_experience_program",
                        arguments_json=(
                            '{"program":"사육사 체험",'
                            '"visit_time":"2026-09-10T15:00:00+09:00",'
                            '"headcount":2}'
                        ),
                    )
                ],
            )
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="사육사 체험 2명 예약해 줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=_create_executor(proposed_actions),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "needs_clarification"
    assert response.termination_reason == "authentication_required"
    assert response.pending_action is None
    assert proposed_actions == []


def test_reservation_tool_rejects_string_headcount_before_pending_action() -> None:
    """문자열 인원 수는 Pending Action을 만들기 전에 차단해야 한다."""
    proposed_actions: list[dict[str, Any]] = []
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_reservation_3",
                calls=[
                    ModelToolCall(
                        call_id="call_reservation_3",
                        name="reserve_experience_program",
                        arguments_json=(
                            '{"program":"사육사 체험",'
                            '"visit_time":"2026-09-10T15:00:00+09:00",'
                            '"headcount":"2"}'
                        ),
                    )
                ],
            )
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="사육사 체험 2명 예약해 줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=_create_executor(proposed_actions),
            settings=RuntimeSettings(),
            reservation_user_id="TEST",
            reservation_session_id="auth_session_test",
        )
    )

    assert response.status == "needs_clarification"
    assert response.termination_reason == "invalid_tool_arguments"
    assert response.pending_action is None
    assert proposed_actions == []