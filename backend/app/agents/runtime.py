"""Provider 판단, Tool 실행, 결과 재전달을 반복하는 Agent Runtime을 구현한다."""

import asyncio
import json
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
from backend.app.schemas.common import TraceItem
from backend.app.schemas.tools import ToolCallRecord, ToolError
from backend.app.tools.executor import ToolExecutor
from backend.app.tools.policy import detect_forbidden_request

@dataclass(frozen=True)
class RuntimeSettings:
    """P0 Runtime의 실행 한도를 담는 테스트 가능 설정이다."""

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
) -> AgentAskResponse:
    """Provider와 Executor를 연결해 Agent 질문 하나를 끝까지 처리한다."""
    state = AgentState(
        run_id=f"run_{uuid4().hex}",
        agent_id=profile.agent_id,
        session_id=request.session_id or f"session_{uuid4().hex}",
        question=request.message,
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
            _run_loop(
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
        return _finish(
            state,
            status="error",
            reason="run_timeout",
            answer="요청 처리 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
        )
    except Exception:
        return _finish(
            state,
            status="error",
            reason="runtime_error",
            answer="요청을 처리하는 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요.",
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
    """Model 호출, Tool 실행, 결과 재전달의 반복 처리를 수행한다."""
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
    record = ToolCallRecord(
        name=call.name,
        arguments=arguments,
        risk=risk,
        result=result,
    )
    state.tool_calls.append(record)

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
        status: Literal["rejected", "needs_clarification", "stopped", "error"] = "rejected"
        reason = "tool_not_allowed"
        answer = "요청한 기능은 사용할 수 없습니다."
    elif code == "INVALID_TOOL_ARGUMENTS":
        status = "needs_clarification"
        reason = "invalid_tool_arguments"
        answer = "도구 실행에 필요한 정보를 다시 확인해 주세요."
    elif code in {"REPEAT_LIMIT_REACHED", "TOOL_CALL_LIMIT_REACHED"}:
        status = "stopped"
        reason = code.lower()
        answer = "안전한 안내를 위해 도구 호출을 중단했습니다."
    else:
        status = "error"
        reason = "tool_execution_error"
        answer = "조회 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."

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


def _finish(
    state: AgentState,
    *,
    status: Literal[
        "completed",
        "needs_clarification",
        "rejected",
        "stopped",
        "error",
    ],
    reason: str,
    answer: str,
) -> AgentAskResponse:
    """내부 State를 API 응답 형태로 변환하고 종료 Trace를 추가한다."""
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
        pending_action=None,
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