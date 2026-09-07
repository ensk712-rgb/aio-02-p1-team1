"""P0에서 허용되는 RAG 및 MCP Tool의 정책 정보를 등록한다."""

from collections.abc import Mapping, Sequence
from typing import Any

from backend.app.agents.models import AgentProfile
from backend.app.providers.base import ProviderToolSchema


RAG_TOOL_NAME = "retrieve_animal_info"

RAG_TOOL_SCHEMA: ProviderToolSchema = {
    "name": RAG_TOOL_NAME,
    "description": "동물 정보카드에서 동물의 특징, 서식지, 먹이 관련 근거를 검색한다.",
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "minLength": 1,
                "maxLength": 500,
                "description": "검색할 동물 또는 특징",
            },
            "collection": {
                "type": "string",
                "enum": ["animal_cards"],
                "description": "P0에서 허용하는 동물 정보카드 컬렉션",
            },
        },
        "required": ["query", "collection"],
        "additionalProperties": False,
    },
}


def _normalize_discovered_tool(
    discovered_tool: Mapping[str, Any],
) -> ProviderToolSchema | None:
    """MCP Client가 발견한 Tool 정보를 Provider용 표준 형태로 검증한다.

    MCP SDK의 객체나 예상하지 못한 형태의 데이터가 Provider에 전달되지 않도록
    `name`, `description`, `input_schema` 세 필드가 올바른 경우에만 반환한다.
    """
    name = discovered_tool.get("name")
    description = discovered_tool.get("description")
    input_schema = discovered_tool.get("input_schema")

    if not isinstance(name, str) or not name.strip():
        return None

    if not isinstance(description, str) or not description.strip():
        return None

    if not isinstance(input_schema, dict):
        return None

    return {
        "name": name.strip(),
        "description": description.strip(),
        "input_schema": input_schema,
    }


def get_tool_definitions(
    profile: AgentProfile,
    discovered_tools: Sequence[Mapping[str, Any]],
) -> list[ProviderToolSchema]:
    """Profile 정책과 MCP 발견 목록의 교집합만 Provider에 반환한다.

    반환 순서는 항상 일정하다.

    1. Profile이 허용한 RAG 컬렉션이 있으면 로컬 RAG Tool을 먼저 추가한다.
    2. Profile의 allowed_tools 순서대로 MCP Tool을 추가한다.

    따라서 MCP Server가 예상하지 못한 Tool을 공개해도 Provider는 해당 Tool을
    선택할 수 없다.
    """
    definitions: list[ProviderToolSchema] = []

    if "animal_cards" in profile.allowed_rag_collections:
        definitions.append(RAG_TOOL_SCHEMA)

    normalized_by_name: dict[str, ProviderToolSchema] = {}

    for discovered_tool in discovered_tools:
        normalized_tool = _normalize_discovered_tool(discovered_tool)

        if normalized_tool is not None:
            normalized_by_name[normalized_tool["name"]] = normalized_tool

    for policy in profile.allowed_tools:
        discovered_tool = normalized_by_name.get(policy.name)

        if discovered_tool is not None:
            definitions.append(discovered_tool)

    return definitions
