"""Tool allowlist, 입력 검증, 반복 제한, 안전한 실행을 담당한다.

조회 Tool은 MCP 또는 RAG로 실행한다.
예약 Tool은 MCP로 보내지 않고 Backend 내부의 승인 서비스로만 전달한다.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timezone
from typing import Any, Protocol

from pydantic import BaseModel, ValidationError

from backend.app.agents.models import AgentProfile
from backend.app.providers.base import ProviderToolSchema
from backend.app.schemas.agent import AgentState
from backend.app.schemas.rag import RagInput
from backend.app.schemas.tools import (
    ClosureStatusInput,
    CourseInfoInput,
    FeedingScheduleInput,
    HabitatRouteInput,
    PublicWeatherInput,
    ReservationToolInput,
    TicketScopeInput,
    ToolError,
    ToolRunResult,
)
from backend.app.tools.registry import (
    RESERVATION_TOOL_NAME,
    get_tool_definitions,
)


class McpClientProtocol(Protocol):
    """Executor가 MCP Client에 요청하는 최소 기능을 정의한다."""

    async def list_tools(self) -> list[dict[str, Any]]:
        """MCP Server가 제공하는 Tool 목록을 반환한다."""

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
    ) -> ToolRunResult:
        """검증된 MCP Tool 이름과 인자를 받아 실행 결과를 반환한다."""


RagSearchFunction = Callable[[str, str], Awaitable[ToolRunResult]]

ReservationProposalFunction = Callable[..., dict[str, Any]]


class ToolExecutor:
    """허용된 Tool만 검증한 뒤 안전하게 실행하는 Backend 컴포넌트다."""

    def __init__(
        self,
        *,
        rag_search: RagSearchFunction,
        mcp_client: McpClientProtocol,
        reservation_proposer: ReservationProposalFunction | None = None,
        max_same_tool_calls: int = 2,
        max_tool_calls: int = 8,
        mcp_timeout_seconds: float = 10.0,
        mcp_retry_count: int = 1,
    ) -> None:
        self._rag_search = rag_search
        self._mcp_client = mcp_client
        self._reservation_proposer = reservation_proposer
        self._max_same_tool_calls = max_same_tool_calls
        self._max_tool_calls = max_tool_calls
        self._mcp_timeout_seconds = mcp_timeout_seconds
        self._mcp_retry_count = mcp_retry_count

    async def get_tool_definitions(
        self,
        profile: AgentProfile,
    ) -> list[ProviderToolSchema]:
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
        validated_arguments = self._validate_arguments(
            name=name,
            arguments=arguments,
            profile=profile,
        )

        if isinstance(validated_arguments, ToolRunResult):
            return validated_arguments

        repeat_key = self._create_repeat_key(name, validated_arguments)

        if name == "retrieve_animal_info":
            limit_error = self._record_attempt(state, repeat_key)
            if limit_error is not None:
                return limit_error

            rag_input = validated_arguments
            return await self._rag_search(rag_input.query, rag_input.collection)

        if name == RESERVATION_TOOL_NAME:
            limit_error = self._record_attempt(state, repeat_key)
            if limit_error is not None:
                return limit_error

            return self._propose_reservation(
                validated_arguments=validated_arguments,
                state=state,
            )

        for attempt in range(self._mcp_retry_count + 1):
            limit_error = self._record_attempt(state, repeat_key)
            if limit_error is not None:
                return limit_error

            try:
                return await asyncio.wait_for(
                    self._mcp_client.call_tool(
                        name,
                        validated_arguments.model_dump(),
                    ),
                    timeout=self._mcp_timeout_seconds,
                )
            except TimeoutError:
                if attempt < self._mcp_retry_count:
                    continue

                return self._policy_error(
                    code="MCP_TIMEOUT",
                    message="운영 정보 조회 시간이 초과되었습니다.",
                )
            except Exception:
                return self._policy_error(
                    code="MCP_TOOL_ERROR",
                    message="운영 정보 조회 중 오류가 발생했습니다.",
                )

        raise AssertionError("MCP 재시도 루프가 결과 없이 종료되었습니다.")

    def _propose_reservation(
        self,
        *,
        validated_arguments: BaseModel,
        state: AgentState,
    ) -> ToolRunResult:
        if self._reservation_proposer is None:
            return self._policy_error(
                code="RESERVATION_NOT_CONFIGURED",
                message="예약 기능이 아직 준비되지 않았습니다.",
            )

        user_id = getattr(state, "reservation_user_id", None)
        auth_session_id = getattr(state, "reservation_session_id", None)

        if not isinstance(user_id, str) or not isinstance(auth_session_id, str):
            return self._policy_error(
                code="AUTHENTICATION_REQUIRED",
                message="예약하려면 먼저 로그인해 주세요.",
            )

        reservation_input = validated_arguments.model_dump()

        try:
            pending_action = self._reservation_proposer(
                session_id=auth_session_id,
                user_id=user_id,
                program=reservation_input["program"],
                visit_time=reservation_input["visit_time"],
                headcount=reservation_input["headcount"],
            )
        except Exception:
            return self._policy_error(
                code="RESERVATION_PROPOSAL_FAILED",
                message="예약 확인 정보를 만드는 중 문제가 발생했습니다.",
            )

        return ToolRunResult(
            success=True,
            data={"pending_action": pending_action},
            error=None,
            source="backend_approval",
            retrieved_at=datetime.now(timezone.utc),
        )

    def _record_attempt(
        self,
        state: AgentState,
        repeat_key: str,
    ) -> ToolRunResult | None:
        if state.repeat_counts.get(repeat_key, 0) >= self._max_same_tool_calls:
            return self._policy_error(
                code="REPEAT_LIMIT_REACHED",
                message="같은 조회 요청이 반복되어 안전하게 중단했습니다.",
            )

        if state.tool_attempts >= self._max_tool_calls:
            return self._policy_error(
                code="TOOL_CALL_LIMIT_REACHED",
                message="Tool 호출 시도 횟수를 초과하여 안전하게 중단했습니다.",
            )

        state.repeat_counts[repeat_key] = state.repeat_counts.get(repeat_key, 0) + 1
        state.tool_attempts += 1
        return None

    def _validate_arguments(
        self,
        *,
        name: str,
        arguments: Mapping[str, Any],
        profile: AgentProfile,
    ) -> BaseModel | ToolRunResult:
        if name == "retrieve_animal_info":
            if "animal_cards" not in profile.allowed_rag_collections:
                return self._policy_error(
                    code="TOOL_NOT_ALLOWED",
                    message="요청한 검색 기능은 허용되지 않습니다.",
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
                "get_course_info": CourseInfoInput,
                "get_indoor_course_info": CourseInfoInput,
                "get_outdoor_course_info": CourseInfoInput,
                "lookup_public_weather": PublicWeatherInput,
                RESERVATION_TOOL_NAME: ReservationToolInput,
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
                message="Tool 실행에 필요한 입력값을 다시 확인해 주세요.",
            )

    @staticmethod
    def _create_repeat_key(name: str, arguments: BaseModel) -> str:
        normalized_arguments = json.dumps(
            arguments.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"{name}:{normalized_arguments}"

    @staticmethod
    def _policy_error(code: str, message: str) -> ToolRunResult:
        return ToolRunResult(
            success=False,
            data={},
            error=ToolError(code=code, message=message),
            source="backend_policy",
            retrieved_at=datetime.now(timezone.utc),
        )