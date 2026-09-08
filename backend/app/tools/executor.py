"""Tool allowlist, 인자 검증, 반복 제한을 적용한 실행기를 구현한다."""

import json
from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from backend.app.agents.models import AgentProfile
from backend.app.providers.base import ProviderToolSchema
from backend.app.schemas.agent import AgentState
from backend.app.schemas.rag import RagInput
from backend.app.schemas.tools import (
    ClosureStatusInput,
    FeedingScheduleInput,
    HabitatRouteInput,
    TicketScopeInput,
    ToolError,
    ToolRunResult,
)
from backend.app.tools.registry import get_tool_definitions


class McpClientProtocol(Protocol):
    """Executor가 MCP Client에 요구하는 최소 기능이다."""

    async def list_tools(self) -> list[dict[str, Any]]:
        """MCP Server가 제공하는 Tool 목록을 표준 dict 목록으로 반환한다."""

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolRunResult:
        """검증된 MCP Tool 이름과 인자를 받아 실행 결과를 반환한다."""


RagSearchFunction = Callable[[str, str], ToolRunResult]


class ToolExecutor:
    """허용된 Tool만 안전하게 실행하는 P0 Backend 정책 컴포넌트다."""

    def __init__(
        self,
        *,
        rag_search: RagSearchFunction,
        mcp_client: McpClientProtocol,
        max_same_tool_calls: int = 2,
        max_tool_calls: int = 8,
    ) -> None:
        """실제 의존성을 생성자에서 주입한다."""
        self._rag_search = rag_search
        self._mcp_client = mcp_client
        self._max_same_tool_calls = max_same_tool_calls
        self._max_tool_calls = max_tool_calls

    async def get_tool_definitions(
        self,
        profile: AgentProfile,
    ) -> list[ProviderToolSchema]:
        """Profile과 MCP 발견 결과의 교집합을 Provider용 Tool 목록으로 만든다."""
        discovered_tools = await self._mcp_client.list_tools()
        return get_tool_definitions(profile, discovered_tools)

    async def execute_tool_safely(
        self,
        name: str,
        arguments: Mapping[str, Any],
        *,
        profile: AgentProfile,
        state: AgentState,
    ) -> ToolRunResult:
        """Tool 이름과 인자를 검증한 뒤에만 RAG 또는 MCP Tool을 실행한다."""
        validated_arguments = self._validate_arguments(
            name=name,
            arguments=arguments,
            profile=profile,
        )

        if isinstance(validated_arguments, ToolRunResult):
            return validated_arguments

        repeat_key = self._create_repeat_key(name, validated_arguments)

        if state.repeat_counts.get(repeat_key, 0) >= self._max_same_tool_calls:
            return self._policy_error(
                code="REPEAT_LIMIT_REACHED",
                message="같은 조회 요청이 반복되어 안전하게 중단했습니다.",
            )

        if state.tool_attempts >= self._max_tool_calls:
            return self._policy_error(
                code="TOOL_CALL_LIMIT_REACHED",
                message="도구 호출 한도를 초과하여 안전하게 중단했습니다.",
            )

        state.repeat_counts[repeat_key] = state.repeat_counts.get(repeat_key, 0) + 1
        state.tool_attempts += 1

        if name == "retrieve_animal_info":
            rag_input = validated_arguments
            return self._rag_search(rag_input.query, rag_input.collection)

        return await self._mcp_client.call_tool(
            name,
            validated_arguments.model_dump(),
        )

    def _validate_arguments(
        self,
        *,
        name: str,
        arguments: Mapping[str, Any],
        profile: AgentProfile,
    ) -> BaseModel | ToolRunResult:
        """Tool 권한과 Pydantic 입력 모델을 검사한다."""
        if name == "retrieve_animal_info":
            if "animal_cards" not in profile.allowed_rag_collections:
                return self._policy_error(
                    code="TOOL_NOT_ALLOWED",
                    message="이 요청에 필요한 검색 기능은 허용되지 않았습니다.",
                )
            input_model: type[BaseModel] = RagInput
        else:
            allowed_tool_names = {tool.name for tool in profile.allowed_tools}

            if name not in allowed_tool_names:
                return self._policy_error(
                    code="TOOL_NOT_ALLOWED",
                    message="요청한 기능은 사용할 수 없습니다.",
                )

            input_models: dict[str, type[BaseModel]] = {
                "get_feeding_schedule": FeedingScheduleInput,
                "check_closure_status": ClosureStatusInput,
                "find_habitat_route": HabitatRouteInput,
                "lookup_ticket_scope": TicketScopeInput,
            }
            input_model = input_models.get(name)

            if input_model is None:
                return self._policy_error(
                    code="TOOL_NOT_ALLOWED",
                    message="요청한 기능은 사용할 수 없습니다.",
                )

        try:
            return input_model.model_validate(dict(arguments), strict=True)
        except ValidationError:
            return self._policy_error(
                code="INVALID_TOOL_ARGUMENTS",
                message="도구 실행에 필요한 입력을 다시 확인해 주세요.",
            )

    @staticmethod
    def _create_repeat_key(name: str, arguments: BaseModel) -> str:
        """같은 Tool과 인자를 안정적으로 비교할 반복 제한 키를 만든다."""
        normalized_arguments = json.dumps(
            arguments.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"{name}:{normalized_arguments}"

    @staticmethod
    def _policy_error(code: str, message: str) -> ToolRunResult:
        """실행하지 않고 정책 차단 결과를 만드는 공통 함수다."""
        return ToolRunResult(
            success=False,
            data={},
            error=ToolError(code=code, message=message),
            source="backend_policy",
            retrieved_at=datetime.now(timezone.utc),
        )