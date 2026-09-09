"""Provider 판단, Tool 실행, 결과 재전달을 반복하는 Agent Runtime을 구현한다."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Literal
from uuid import uuid4

from backend.app.agents.models import AgentProfile
from backend.app.providers.base import ModelProvider
from backend.app.schemas.agent import (
    AgentAskRequest,
    AgentAskResponse,
    AgentState,
    ModelToolCall,
)
from backend.app.schemas.common import Source, TraceItem
from backend.app.schemas.tools import ToolCallRecord, ToolError, ToolRunResult
from backend.app.tools.course_weather_policy import narrow_course_tools_by_weather
from backend.app.tools.executor import ToolExecutor
from backend.app.tools.policy import detect_forbidden_request

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RuntimeSettings:
    """Runtime의 최대 실행 횟수와 제한 시간을 정의한다."""

    max_agent_steps: int = 6
    run_timeout_seconds: float = 90.0


def _build_instructions(
    base_instructions: str,
    conversation_history: list[dict] | None,
) -> str:
    """최근 대화 기록을 별도 LLM 요약 없이 텍스트로 이어붙인다."""
    if not conversation_history:
        return base_instructions

    lines = ["", "최근 대화:"]
    for message in conversation_history:
        speaker = "사용자" if message["role"] == "user" else "에이전트"
        lines.append(f"{speaker}: {message['text']}")

    return base_instructions + "\n".join(lines)


async def run_agent(
    request: AgentAskRequest,
    profile: AgentProfile,
    *,
    provider: ModelProvider,
    executor: ToolExecutor,
    settings: RuntimeSettings,
    conversation_history: list[dict] | None = None,
    reservation_user_id: str | None = None,
    reservation_session_id: str | None = None,
) -> AgentAskResponse:
    """질문 하나를 안전하게 끝까지 실행하고 API 응답으로 반환한다.

    예약 Tool은 일반 조회 Tool과 다르게 동작한다.
    예약 Tool이 성공하면 실제 예약을 즉시 만들지 않고, 사용자 확인이 필요한
    Pending Action을 만든 뒤 ``confirmation_required`` 상태로 종료한다.

    Args:
        request: 사용자가 보낸 질문과 대화 세션 정보다.
        profile: 허용 Tool과 안전 지침이 담긴 Agent Profile이다.
        provider: 다음 행동을 제안하는 Mock 또는 OpenAI Provider다.
        executor: Tool allowlist와 입력 검증을 담당하는 실행기다.
        settings: 최대 단계 수와 timeout 설정이다.
        reservation_user_id: 로그인으로 확인된 예약 사용자 ID다.
        reservation_session_id: 예약 확인에 사용할 로그인 세션 ID다.
    """
    state = AgentState(
        run_id=f"run_{uuid4().hex}",
        agent_id=profile.agent_id,
        session_id=request.session_id or f"session_{uuid4().hex}",
        question=request.message,
        reservation_user_id=reservation_user_id,
        reservation_session_id=reservation_session_id,
    )
    state.trace.append(
        TraceItem(owner="runtime", stage="run_started", data={})
    )

    forbidden_error = detect_forbidden_request(request.message)

    if forbidden_error is not None:
        state.trace.append(
            TraceItem(
                owner="policy",
                stage="forbidden_request_blocked",
                data={"code": forbidden_error.code},
            )
        )
        return _finish(
            state,
            status="rejected",
            reason=forbidden_error.code.lower(),
            answer=forbidden_error.message,
        )

    try:
        return await asyncio.wait_for(
            _run_loop_with_weather_narrowing(
                request=request,
                profile=profile,
                provider=provider,
                executor=executor,
                settings=settings,
                state=state,
                conversation_history=conversation_history,
            ),
            timeout=settings.run_timeout_seconds,
        )
    except TimeoutError:
        logger.warning("Agent Runtime timeout: run_id=%s", state.run_id)
        return _finish(
            state,
            status="error",
            reason="run_timeout",
            answer="요청 처리 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
        )
    except Exception as error:
        logger.error(
            "Agent Runtime failed: run_id=%s, error_type=%s, "
            "status_code=%s, code=%s, param=%s",
            state.run_id,
            type(error).__name__,
            getattr(error, "status_code", None),
            getattr(error, "code", None),
            getattr(error, "param", None),
            exc_info=True,
        )
        return _finish(
            state,
            status="error",
            reason="runtime_error",
            answer="요청을 처리하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        )


async def _run_loop_with_weather_narrowing(
    *,
    request: AgentAskRequest,
    profile: AgentProfile,
    provider: ModelProvider,
    executor: ToolExecutor,
    settings: RuntimeSettings,
    state: AgentState,
    conversation_history: list[dict] | None = None,
) -> AgentAskResponse:
    """Tool 발견 전에 날씨를 선조회해 코스 Tool을 좁힌 뒤 본 루프를 실행한다.

    P1-B 계획서 §6.2: zoo_guide의 모든 요청에 항상 적용한다(코스와 무관한
    질문이라도 매번 실행) — Backend가 LLM 판단 전에 요청 의도를 미리 분류하는
    단계 자체가 없기 때문이다(v0.4 §9.1). narrowing된 profile을 Tool 발견과
    실행 검증 양쪽에 그대로 흘려보내야 "발견 단계만 막고 실행은 안 막는" 우회가
    생기지 않는다 — 그래서 아래에서 만든 narrowed profile을 _run_loop에 그대로
    전달한다(별도로 원본 profile을 다시 쓰지 않는다).
    """
    narrowing = await narrow_course_tools_by_weather(profile)

    if narrowing.applied:
        weather = narrowing.weather
        state.trace.append(
            TraceItem(
                owner="runtime",
                stage="course_tool_narrowed_by_weather",
                data={
                    "weather_lookup_succeeded": bool(weather and weather.success),
                    "condition": (
                        weather.data.get("condition")
                        if weather and weather.success
                        else None
                    ),
                },
            )
        )

    return await _run_loop(
        request=request,
        profile=narrowing.profile,
        provider=provider,
        executor=executor,
        settings=settings,
        state=state,
        conversation_history=conversation_history,
    )


async def _run_loop(
    *,
    request: AgentAskRequest,
    profile: AgentProfile,
    provider: ModelProvider,
    executor: ToolExecutor,
    settings: RuntimeSettings,
    state: AgentState,
    conversation_history: list[dict] | None = None,
) -> AgentAskResponse:
    """Model 호출, Tool 실행, 결과 재전달을 반복 처리한다."""
    tool_schemas = await executor.get_tool_definitions(profile)
    previous_response_id: str | None = None
    instructions = _build_instructions(profile.instructions, conversation_history)

    # 다음 Provider 호출에는 바로 직전 턴에서 실행한 결과만 전달한다.
    previous_turn_outputs: list[ToolCallRecord] = []

    while True:
        if state.llm_calls >= settings.max_agent_steps:
            return _finish(
                state,
                status="stopped",
                reason="agent_step_limit_reached",
                answer="안전한 안내를 위해 처리 횟수 제한에 도달했습니다.",
            )

        turn = await provider.next_turn(
            question=request.message,
            instructions=instructions,
            tools=tool_schemas,
            previous_response_id=previous_response_id,
            tool_outputs=previous_turn_outputs,
        )
        state.llm_calls += 1
        previous_response_id = turn.response_id

        state.trace.append(
            TraceItem(
                owner="ai_agent",
                stage="model_turn_received",
                data={
                    "response_id": turn.response_id,
                    "call_count": len(turn.calls),
                },
            )
        )

        if turn.clarification is not None:
            state.trace.append(
                TraceItem(
                    owner="ai_agent",
                    stage="clarification_requested",
                    data={},
                )
            )
            return _finish(
                state,
                status="needs_clarification",
                reason="model_requested_clarification",
                answer=turn.clarification,
            )

        if not turn.calls:
            if not turn.text.strip():
                return _finish(
                    state,
                    status="error",
                    reason="empty_model_response",
                    answer="답변을 생성하지 못했습니다. 질문을 다시 입력해 주세요.",
                )

            return _finish(
                state,
                status="completed",
                reason="model_finished",
                answer=turn.text,
            )

        current_turn_outputs: list[ToolCallRecord] = []

        for call in turn.calls:
            result_or_response = await _execute_call(
                call=call,
                profile=profile,
                executor=executor,
                state=state,
            )

            if isinstance(result_or_response, AgentAskResponse):
                return result_or_response

            current_turn_outputs.append(result_or_response)

        previous_turn_outputs = current_turn_outputs


async def _execute_call(
    *,
    call: ModelToolCall,
    profile: AgentProfile,
    executor: ToolExecutor,
    state: AgentState,
) -> ToolCallRecord | AgentAskResponse:
    """Model이 제안한 Tool 호출 한 건을 검증하고 실행한다."""
    try:
        arguments = json.loads(call.arguments_json)
    except json.JSONDecodeError:
        return _finish(
            state,
            status="needs_clarification",
            reason="invalid_tool_arguments_json",
            answer="필요한 정보를 다시 확인해 주세요.",
        )

    if not isinstance(arguments, dict):
        return _finish(
            state,
            status="needs_clarification",
            reason="tool_arguments_not_object",
            answer="필요한 정보를 다시 확인해 주세요.",
        )

    result = await executor.execute_tool_safely(
        call.name,
        arguments,
        profile=profile,
        state=state,
    )

    if not result.success:
        return _finish_from_tool_error(state, result.error)

    risk = _get_risk(call.name, profile)

    # 예약 Tool 결과에는 내부 사용자 정보가 포함될 수 있으므로,
    # API 응답과 Tool 기록에는 공개 가능한 항목만 남긴다.
    if risk == "change":
        pending_action = result.data.get("pending_action")

        if not isinstance(pending_action, dict):
            return _finish(
                state,
                status="error",
                reason="invalid_pending_action",
                answer="예약 확인 정보를 만들지 못했습니다. 다시 시도해 주세요.",
            )

        public_pending_action = _public_pending_action(pending_action)
        state.approval = public_pending_action

        record = ToolCallRecord(
            name=call.name,
            arguments=arguments,
            risk=risk,
            result=ToolRunResult(
                success=True,
                data={"pending_action": public_pending_action},
                error=None,
                source=result.source,
                retrieved_at=result.retrieved_at,
            ),
        )
        state.tool_calls.append(record)
        state.trace.append(
            TraceItem(
                owner="runtime",
                stage="reservation_confirmation_required",
                data={"tool": call.name},
            )
        )

        return _finish(
            state,
            status="confirmation_required",
            reason="reservation_confirmation_required",
            answer="예약 내용을 확인한 뒤 확인 또는 취소를 선택해 주세요.",
        )

    record = ToolCallRecord(
        name=call.name,
        arguments=arguments,
        risk=risk,
        result=result,
    )
    state.tool_calls.append(record)

    if call.name == "retrieve_animal_info":
        chunks = result.data.get("chunks", [])
        if isinstance(chunks, list):
            state.sources.extend(
                Source.model_validate(
                    {
                        "doc_id": chunk.get("doc_id"),
                        "title": chunk.get("title"),
                        "page": chunk.get("page"),
                        "score": chunk.get("score"),
                    }
                )
                for chunk in chunks
                if isinstance(chunk, dict)
            )

    state.trace.append(
        TraceItem(
            owner="rag" if call.name == "retrieve_animal_info" else "mcp",
            stage="tool_executed",
            data={"tool": call.name},
        )
    )
    return record


def _finish_from_tool_error(
    state: AgentState,
    error: ToolError | None,
) -> AgentAskResponse:
    """Executor가 반환한 오류 코드를 Agent 응답 상태로 변환한다."""
    code = error.code if error is not None else "UNKNOWN_TOOL_ERROR"

    if code == "TOOL_NOT_ALLOWED":
        status: Literal[
            "rejected",
            "needs_clarification",
            "stopped",
            "error",
        ] = "rejected"
        reason = "tool_not_allowed"
        answer = "요청한 기능은 사용할 수 없습니다."
    elif code == "INVALID_TOOL_ARGUMENTS":
        status = "needs_clarification"
        reason = "invalid_tool_arguments"
        answer = "예약 또는 조회에 필요한 정보를 다시 확인해 주세요."
    elif code == "AUTHENTICATION_REQUIRED":
        status = "needs_clarification"
        reason = "authentication_required"
        answer = "예약하려면 먼저 로그인해 주세요."
    elif code in {"REPEAT_LIMIT_REACHED", "TOOL_CALL_LIMIT_REACHED"}:
        status = "stopped"
        reason = code.lower()
        answer = "안전한 안내를 위해 Tool 호출을 중단했습니다."
    else:
        status = "error"
        reason = "tool_execution_error"
        answer = "기능 실행 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."

    state.trace.append(
        TraceItem(
            owner="policy",
            stage="tool_blocked_or_failed",
            data={"code": code},
        )
    )
    return _finish(state, status=status, reason=reason, answer=answer)


def _get_risk(
    tool_name: str,
    profile: AgentProfile,
) -> Literal["read", "change", "forbidden"]:
    """Tool 이름에서 응답 기록용 위험도를 찾는다."""
    if tool_name == "retrieve_animal_info":
        return "read"

    for policy in profile.allowed_tools:
        if policy.name == tool_name:
            return policy.risk

    return "forbidden"


def _public_pending_action(pending_action: dict[str, object]) -> dict[str, object]:
    """화면에 공개해도 되는 예약 확인 정보만 골라 반환한다.

    사용자 ID, 예약 실행 인자 전체, 멱등성 키처럼 내부 처리용 값은
    응답에 포함하지 않는다.
    """
    allowed_keys = (
        "action_id",
        "tool_name",
        "summary",
        "approval_status",
        "expires_at",
    )
    return {
        key: pending_action[key]
        for key in allowed_keys
        if key in pending_action
    }


def _finish(
    state: AgentState,
    *,
    status: Literal[
        "completed",
        "needs_clarification",
        "confirmation_required",
        "rejected",
        "stopped",
        "error",
    ],
    reason: str,
    answer: str,
) -> AgentAskResponse:
    """현재 State를 API 응답 형태로 변환하고 종료 Trace를 추가한다."""
    state.status = status
    state.termination_reason = reason
    state.answer = answer

    state.trace.append(
        TraceItem(
            owner="runtime",
            stage="run_finished",
            data={"status": status, "reason": reason},
        )
    )

    return AgentAskResponse(
        run_id=state.run_id,
        agent_id="zoo_guide",
        session_id=state.session_id,
        intent=_calculate_intent(state),
        status=status,
        termination_reason=reason,
        final_answer=answer,
        sources=state.sources,
        tool_calls=state.tool_calls,
        pending_action=state.approval,
        trace=state.trace,
    )


def _calculate_intent(state: AgentState) -> Literal["rag", "tool", "both"] | None:
    """실제로 실행된 Tool 기록으로 intent를 계산한다."""
    if not state.tool_calls:
        return None

    has_rag = any(call.name == "retrieve_animal_info" for call in state.tool_calls)
    has_tool = any(call.name != "retrieve_animal_info" for call in state.tool_calls)

    if has_rag and has_tool:
        return "both"
    if has_rag:
        return "rag"
    return "tool"
