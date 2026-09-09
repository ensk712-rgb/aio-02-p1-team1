"""Agent Runtime의 Provider → Tool → Provider 반복 흐름을 검증한다."""

import asyncio
from datetime import datetime, timezone
from typing import Any

from backend.app.agents.registry import get_agent_profile
from backend.app.agents.runtime import RuntimeSettings, run_agent
from backend.app.providers.mock_provider import ScriptedMockProvider
from backend.app.schemas.agent import AgentAskRequest, ModelToolCall, ModelTurn
from backend.app.schemas.tools import ToolRunResult
from backend.app.tools import course_weather_policy
from backend.app.tools.executor import ToolExecutor


class FakeMcpClient:
    """Runtime 테스트용 MCP Client다."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def list_tools(self) -> list[dict[str, Any]]:
        """Provider에 공개할 MCP Tool 목록을 반환한다."""
        return [
            {
                "name": "get_feeding_schedule",
                "description": "먹이시간을 조회한다.",
                "input_schema": {
                    "type": "object",
                    "properties": {"habitat": {"type": "string"}},
                    "required": ["habitat"],
                },
            }
        ]

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolRunResult:
        """MCP 호출을 기록하고 성공 결과를 반환한다."""
        self.calls.append((name, arguments))

        return ToolRunResult(
            success=True,
            data={"habitat": "해양관", "animal": "펭귄"},
            error=None,
            source="fake_mcp",
            retrieved_at=datetime.now(timezone.utc),
        )


def create_executor(mcp_client: FakeMcpClient) -> ToolExecutor:
    """Fake MCP와 Fake RAG를 연결한 Executor를 만든다."""
    def fake_rag_search(query: str, collection: str) -> ToolRunResult:
        """RAG 호출에 사용할 가짜 검색 결과를 반환한다."""
        return ToolRunResult(
            success=True,
            data={"matched": False, "chunks": []},
            error=None,
            source="fake_rag",
            retrieved_at=datetime.now(timezone.utc),
        )

    return ToolExecutor(rag_search=fake_rag_search, mcp_client=mcp_client)


def test_runtime_returns_final_answer_after_tool_result() -> None:
    """Runtime은 Tool 결과를 Provider에 전달한 뒤 최종 답변을 받아야 한다."""
    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                calls=[
                    ModelToolCall(
                        call_id="call_1",
                        name="get_feeding_schedule",
                        arguments_json='{"habitat": "해양관"}',
                    )
                ],
            ),
            ModelTurn(
                response_id="response_2",
                text="다음 펭귄 먹이시간은 14:30입니다.",
            ),
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="펭귄 먹이시간 알려줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "completed"
    assert response.intent == "tool"
    assert len(response.tool_calls) == 1
    assert mcp_client.calls == [
        ("get_feeding_schedule", {"habitat": "해양관"})
    ]
    assert provider.call_history[1].tool_result_names == ("get_feeding_schedule",)


def test_runtime_returns_clarification_without_tool_execution() -> None:
    """Provider가 추가 정보를 요청하면 Tool을 실행하지 않아야 한다."""
    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                clarification="출발 위치와 목적지를 함께 알려주세요.",
            )
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="길 알려줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "needs_clarification"
    assert response.tool_calls == []
    assert mcp_client.calls == []


def test_runtime_rejects_unallowed_tool_without_mcp_execution() -> None:
    """Profile에 없는 Tool은 Executor가 차단하고 Runtime은 rejected로 끝낸다."""
    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                calls=[
                    ModelToolCall(
                        call_id="call_1",
                        name="delete_database",
                        arguments_json="{}",
                    )
                ],
            )
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="데이터를 삭제해줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "rejected"
    assert response.tool_calls == []
    assert mcp_client.calls == []


def test_runtime_stops_before_third_same_tool_call() -> None:
    """같은 Tool과 인자를 세 번째로 실행하기 전에 stopped로 끝내야 한다."""
    mcp_client = FakeMcpClient()
    repeated_call = ModelToolCall(
        call_id="call_repeat",
        name="get_feeding_schedule",
        arguments_json='{"habitat": "해양관"}',
    )
    provider = ScriptedMockProvider(
        [
            ModelTurn(response_id="response_1", calls=[repeated_call]),
            ModelTurn(response_id="response_2", calls=[repeated_call]),
            ModelTurn(response_id="response_3", calls=[repeated_call]),
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="펭귄 먹이시간 알려줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "stopped"
    assert response.termination_reason == "repeat_limit_reached"
    assert len(mcp_client.calls) == 2


def test_conversation_history_is_appended_to_instructions() -> None:
    """이전 대화가 있으면 Provider에 전달되는 instructions에 포함되어야 한다."""
    provider = ScriptedMockProvider(
        [ModelTurn(response_id="response_1", text="이어서 답변합니다.")]
    )

    asyncio.run(
        run_agent(
            AgentAskRequest(message="그럼 먹이는 언제야?", session_id="session_1"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(FakeMcpClient()),
            settings=RuntimeSettings(),
            conversation_history=[
                {"role": "user", "text": "호랑이는 어디 살아?"},
                {"role": "agent", "text": "맹수관에서 서식합니다."},
            ],
        )
    )

    sent_instructions = provider.call_history[0].instructions
    assert "호랑이는 어디 살아?" in sent_instructions
    assert "맹수관에서 서식합니다." in sent_instructions


def test_no_conversation_history_leaves_instructions_unchanged() -> None:
    """history가 없으면 instructions는 Profile 원본과 같아야 한다."""
    provider = ScriptedMockProvider(
        [ModelTurn(response_id="response_1", text="답변")]
    )
    profile = get_agent_profile("zoo_guide")

    asyncio.run(
        run_agent(
            AgentAskRequest(message="질문", session_id="session_1"),
            profile,
            provider=provider,
            executor=create_executor(FakeMcpClient()),
            settings=RuntimeSettings(),
        )
    )

    assert provider.call_history[0].instructions == profile.instructions


# ---- §6.2 날씨 선조회 + 동적 Allowlist 좁히기 (10단계) ----


def _monkeypatch_weather(monkeypatch, *, condition: str) -> None:
    def _fake(region: str, *, now=None):
        as_of = now or datetime.now(timezone.utc)
        return ToolRunResult(
            success=True,
            data={
                "region": region,
                "condition": condition,
                "indoor_recommended": condition in {"rain", "storm"},
                "as_of": as_of.isoformat(),
            },
            error=None,
            source="open_meteo_forecast",
            retrieved_at=as_of,
        )

    monkeypatch.setattr(course_weather_policy, "lookup_public_weather", _fake)


def test_runtime_blocks_get_course_info_when_narrowed_by_rain(monkeypatch) -> None:
    """비가 오면 get_course_info가 narrowing으로 빠지므로, Provider가 그래도
    제안해도 실행 검증 단계에서 차단돼야 한다 — Tool 발견만 막고 실행은
    안 막으면 우회가 가능해지므로, 이 테스트는 그 우회가 안 되는지 확인한다
    (P1-B 계획서 §6.2 "적용 범위 확인")."""
    _monkeypatch_weather(monkeypatch, condition="rain")
    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                calls=[
                    ModelToolCall(
                        call_id="call_1",
                        name="get_course_info",
                        arguments_json='{"available_minutes": 120}',
                    )
                ],
            )
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="2시간 코스 추천해 줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "rejected"
    assert mcp_client.calls == []

    narrowing_traces = [
        item for item in response.trace if item.stage == "course_tool_narrowed_by_weather"
    ]
    assert len(narrowing_traces) == 1
    assert narrowing_traces[0].data["weather_lookup_succeeded"] is True
    assert narrowing_traces[0].data["condition"] == "rain"


def test_runtime_allows_indoor_course_info_when_narrowed_by_rain(monkeypatch) -> None:
    """비가 오면 반대로 get_indoor_course_info는 정상적으로 허용돼야 한다."""
    _monkeypatch_weather(monkeypatch, condition="rain")
    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                calls=[
                    ModelToolCall(
                        call_id="call_1",
                        name="get_indoor_course_info",
                        arguments_json='{"available_minutes": 120}',
                    )
                ],
            ),
            ModelTurn(response_id="response_2", text="실내 코스를 추천합니다."),
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="실내 코스 추천해 줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "completed"
    assert mcp_client.calls[0][0] == "get_indoor_course_info"


def test_runtime_blocks_indoor_course_info_when_narrowed_by_clear_weather(
    monkeypatch,
) -> None:
    """맑으면 반대로 get_indoor_course_info가 빠지고 get_course_info만 허용된다."""
    _monkeypatch_weather(monkeypatch, condition="clear")
    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                calls=[
                    ModelToolCall(
                        call_id="call_1",
                        name="get_indoor_course_info",
                        arguments_json='{"available_minutes": 120}',
                    )
                ],
            )
        ]
    )

    response = asyncio.run(
        run_agent(
            AgentAskRequest(message="코스 추천해 줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert response.status == "rejected"
    assert mcp_client.calls == []


def test_runtime_narrows_even_for_unrelated_questions(monkeypatch) -> None:
    """코스와 무관한 질문에도 narrowing 자체는 항상 실행돼야 한다(계획서
    §6.2, v0.4 §9.1 — Backend가 의도를 미리 분류하는 단계가 없으므로)."""
    weather_calls: list[str] = []

    def _fake(region: str, *, now=None):
        weather_calls.append(region)
        return ToolRunResult(
            success=True,
            data={
                "region": region,
                "condition": "clear",
                "indoor_recommended": False,
                "as_of": datetime.now(timezone.utc).isoformat(),
            },
            error=None,
            source="open_meteo_forecast",
            retrieved_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(course_weather_policy, "lookup_public_weather", _fake)

    mcp_client = FakeMcpClient()
    provider = ScriptedMockProvider(
        [
            ModelTurn(
                response_id="response_1",
                calls=[
                    ModelToolCall(
                        call_id="call_1",
                        name="get_feeding_schedule",
                        arguments_json='{"habitat": "해양관"}',
                    )
                ],
            ),
            ModelTurn(response_id="response_2", text="답변"),
        ]
    )

    asyncio.run(
        run_agent(
            AgentAskRequest(message="펭귄 먹이시간 알려줘"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(mcp_client),
            settings=RuntimeSettings(),
        )
    )

    assert weather_calls == ["서울"]


def test_runtime_allows_outdoor_course_info_regardless_of_weather(monkeypatch) -> None:
    """§10: get_outdoor_course_info는 날씨 narrowing 대상이 아니므로 비가
    오든 맑든 항상 정상적으로 실행돼야 한다(계획서 §5.0)."""
    for condition in ("rain", "clear"):
        _monkeypatch_weather(monkeypatch, condition=condition)
        mcp_client = FakeMcpClient()
        provider = ScriptedMockProvider(
            [
                ModelTurn(
                    response_id="response_1",
                    calls=[
                        ModelToolCall(
                            call_id="call_1",
                            name="get_outdoor_course_info",
                            arguments_json='{"available_minutes": 120}',
                        )
                    ],
                ),
                ModelTurn(response_id="response_2", text="실외 코스를 추천합니다."),
            ]
        )

        response = asyncio.run(
            run_agent(
                AgentAskRequest(message="야외 동물만 보고 싶어"),
                get_agent_profile("zoo_guide"),
                provider=provider,
                executor=create_executor(mcp_client),
                settings=RuntimeSettings(),
            )
        )

        assert response.status == "completed", f"condition={condition}"
        assert mcp_client.calls[0][0] == "get_outdoor_course_info"