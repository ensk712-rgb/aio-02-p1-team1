"""Tool allowlist, 입력 검증, 반복 제한, 안전한 실행을 담당한다.

조회 Tool은 MCP 또는 RAG로 실행한다.
예약 Tool은 MCP로 보내지 않고 Backend 내부의 승인 서비스로만 전달한다.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable, Mapping, Sequence
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

# ApprovalService.propose_reservation()과 같은 형태의 함수만 받는다.
ReservationProposalFunction = Callable[..., dict[str, Any]]


class ToolExecutor:
    """허용된 Tool만 검증한 뒤 안전하게 실행하는 Backend 컴포넌트다.

    - RAG Tool: Backend 내부 검색 함수를 호출한다.
    - 조회 Tool: MCP Server로 호출한다.
    - 예약 Tool: MCP가 아닌 Backend 내부 승인 서비스로 전달한다.
    """

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
        """실제 기능을 생성자가 주입받아 테스트와 운영 환경을 분리한다.

        Args:
            rag_search: 동물 정보 검색 함수다.
            mcp_client: 먹이시간·휴장·경로·코스 조회를 담당하는 MCP Client다.
            reservation_proposer: 예약 확인 대기 정보를 만드는 Backend 함수다.
            max_same_tool_calls: 같은 Tool과 같은 인자의 최대 실행 횟수다.
            max_tool_calls: 한 Agent 실행에서 허용하는 전체 Tool 실행 횟수다.
            mcp_timeout_seconds: MCP 응답을 기다리는 최대 시간이다.
            mcp_retry_count: MCP timeout 발생 시 재시도 횟수다.
        """
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
        """Profile 정책과 MCP 발견 결과를 합쳐 Provider용 Tool 목록을 만든다."""
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
        """Tool 이름과 인자를 검증한 뒤에만 실제 기능을 실행한다.

        잘못된 Tool 이름, 허용되지 않은 Tool, 잘못된 인자는 외부 시스템을
        호출하기 전에 정책 오류로 반환한다.
        """
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
        """예약을 생성하지 않고 사용자 확인용 Pending Action만 만든다.

        실제 예약은 사용자가 확인 버튼을 누른 뒤 별도 승인 흐름에서 처리한다.
        따라서 이 함수는 예약 번호나 완료 결과를 만들지 않는다.
        """
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
        """반복 실행 제한과 전체 Tool 실행 제한을 적용한다."""
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
        """Tool 권한과 Pydantic 입력 모델을 검사한다.

        각 허용 Tool 이름을 Pydantic 입력 모델에 명시적으로 연결한다.
        이 연결이 없으면 Tool이 Profile에 있더라도 실행하지 않아야 한다.
        """
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
        """같은 Tool과 같은 인자를 안정적으로 비교할 반복 제한 키를 만든다."""
        normalized_arguments = json.dumps(
            arguments.model_dump(mode="json"),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return f"{name}:{normalized_arguments}"

    @staticmethod
    def _policy_error(code: str, message: str) -> ToolRunResult:
        """외부 Tool을 실행하지 않고 정책 차단 결과를 만든다."""
        return ToolRunResult(
            success=False,
            data={},
            error=ToolError(code=code, message=message),
            source="backend_policy",
            retrieved_at=datetime.now(timezone.utc),
        )