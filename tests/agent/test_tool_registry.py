"""Tool Registry가 허용된 Tool만 Provider에 전달하는지 검증한다."""

from backend.app.agents.registry import get_agent_profile
from backend.app.tools.registry import RAG_TOOL_NAME, get_tool_definitions


DISCOVERED_TOOLS = [
    {
        "name": "get_feeding_schedule",
        "description": "먹이시간을 조회한다.",
        "input_schema": {
            "type": "object",
            "properties": {"habitat": {"type": "string"}},
            "required": ["habitat"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_closure_status",
        "description": "휴장 상태를 조회한다.",
        "input_schema": {
            "type": "object",
            "properties": {"habitat": {"type": ["string", "null"]}},
            "additionalProperties": False,
        },
    },
    {
        "name": "find_habitat_route",
        "description": "관람 경로를 조회한다.",
        "input_schema": {
            "type": "object",
            "properties": {
                "current": {"type": "string"},
                "destination": {"type": "string"},
            },
            "required": ["current", "destination"],
            "additionalProperties": False,
        },
    },
    {
        "name": "delete_database",
        "description": "데이터를 삭제한다.",
        "input_schema": {
            "type": "object",
            "properties": {},
        },
    },
]


def test_registry_returns_rag_and_allowed_mcp_tools() -> None:
    """RAG Tool과 Profile에서 허용된 세 MCP Tool만 반환해야 한다."""
    profile = get_agent_profile("zoo_guide")

    tools = get_tool_definitions(profile, DISCOVERED_TOOLS)

    assert [tool["name"] for tool in tools] == [
        RAG_TOOL_NAME,
        "get_feeding_schedule",
        "check_closure_status",
        "find_habitat_route",
    ]


def test_registry_does_not_expose_unallowed_discovered_tool() -> None:
    """MCP가 발견했더라도 허용되지 않은 Tool은 Provider에 보이면 안 된다."""
    profile = get_agent_profile("zoo_guide")

    tools = get_tool_definitions(profile, DISCOVERED_TOOLS)

    assert "delete_database" not in [tool["name"] for tool in tools]


def test_registry_skips_malformed_discovered_tool() -> None:
    """필수 Tool Schema가 잘못된 MCP 결과는 Provider에 전달하지 않는다."""
    profile = get_agent_profile("zoo_guide")
    malformed_tools = [
        {
            "name": "get_feeding_schedule",
            "description": "먹이시간을 조회한다.",
            "input_schema": "JSON Schema가 아닌 문자열",
        }
    ]

    tools = get_tool_definitions(profile, malformed_tools)

    assert [tool["name"] for tool in tools] == [RAG_TOOL_NAME]


def test_registry_keeps_profile_tool_order() -> None:
    """MCP 발견 순서와 관계없이 Profile에 정의된 Tool 순서를 유지해야 한다."""
    profile = get_agent_profile("zoo_guide")
    reverse_order_tools = list(reversed(DISCOVERED_TOOLS))

    tools = get_tool_definitions(profile, reverse_order_tools)

    assert [tool["name"] for tool in tools] == [
        RAG_TOOL_NAME,
        "get_feeding_schedule",
        "check_closure_status",
        "find_habitat_route",
    ]