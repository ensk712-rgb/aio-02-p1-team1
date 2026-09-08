"""Provider에 공개할 RAG, MCP, 로컬 Tool의 정책 정보를 등록한다."""

from collections.abc import Mapping, Sequence
from typing import Any

from backend.app.agents.models import AgentProfile
from backend.app.providers.base import ProviderToolSchema


RAG_TOOL_NAME = "retrieve_animal_info"
RESERVATION_TOOL_NAME = "reserve_experience_program"

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
                "description": "허용하는 동물 정보카드 컬렉션",
            },
        },
        "required": ["query", "collection"],
        "additionalProperties": False,
    },
}

RESERVATION_TOOL_SCHEMA: ProviderToolSchema = {
    "name": RESERVATION_TOOL_NAME,
    "description": (
        "체험 프로그램 예약을 제안한다. "
        "이 Tool은 사용자 확인 전에는 실제 예약을 생성하지 않는다."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "program": {
                "type": "string",
                "minLength": 1,
                "maxLength": 100,
                "description": "예약할 체험 프로그램 이름",
            },
            "visit_time": {
                "type": "string",
                "minLength": 1,
                "maxLength": 50,
                "description": "시간대를 포함한 예약 희망 시각",
            },
            "headcount": {
                "type": "integer",
                "minimum": 1,
                "maximum": 10,
                "description": "예약 인원 수",
            },
        },
        "required": ["program", "visit_time", "headcount"],
        "additionalProperties": False,
    },
}

LOCAL_TOOL_SCHEMAS: dict[str, ProviderToolSchema] = {
    RESERVATION_TOOL_NAME: RESERVATION_TOOL_SCHEMA,
}


def _normalize_discovered_tool(
    discovered_tool: Mapping[str, Any],
) -> ProviderToolSchema | None:
    """MCP Client가 발견한 Tool 정보를 Provider용 표준 형태로 검증한다."""
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
    """Profile 정책에 맞는 RAG·MCP·로컬 Tool Schema만 반환한다.

    RAG는 Backend 내부 검색 기능이고, 예약은 Backend 내부 변경 기능이다.
    두 Tool은 MCP Server의 발견 목록에 없어도 Profile이 허용하면 Provider에 공개한다.
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
        local_tool = LOCAL_TOOL_SCHEMAS.get(policy.name)

        if local_tool is not None:
            definitions.append(local_tool)
            continue

        discovered_tool = normalized_by_name.get(policy.name)

        if discovered_tool is not None:
            definitions.append(discovered_tool)

    return definitions