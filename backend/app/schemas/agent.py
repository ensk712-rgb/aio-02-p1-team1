"""Agent API 요청·응답과 Provider/Runtime 내부 모델을 정의한다."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.common import Source, TraceItem
from backend.app.schemas.tools import ToolCallRecord


AgentStatus = Literal[
    "completed",
    "needs_clarification",
    "confirmation_required",
    "rejected",
    "stopped",
    "error",
]

AgentIntent = Literal["rag", "tool", "both"] | None


class AgentAskRequest(BaseModel):
    """관람객 화면이 POST /api/agent/ask로 보내는 요청이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    message: str = Field(
        min_length=1,
        max_length=2000,
        description="관람객이 입력한 질문",
    )
    session_id: str | None = Field(
        default=None,
        min_length=1,
        description="서버가 이전 요청에서 발급한 대화 세션 ID",
    )


class ModelToolCall(BaseModel):
    """Provider가 제안한 Tool 호출 한 건이다.

    Runtime은 이 값을 신뢰하여 바로 실행하지 않는다.
    반드시 allowlist와 Pydantic 인자 검증을 먼저 수행한다.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    call_id: str = Field(min_length=1, description="Provider가 부여한 호출 ID")
    name: str = Field(min_length=1, description="Provider가 제안한 Tool 이름")
    arguments_json: str = Field(
        min_length=1,
        description="Provider가 문자열로 반환한 JSON Tool 인자",
    )


class ModelTurn(BaseModel):
    """Provider가 Runtime에 반환하는 한 번의 판단 결과다."""

    model_config = ConfigDict(extra="forbid")

    response_id: str = Field(min_length=1)
    calls: list[ModelToolCall] = Field(default_factory=list)
    text: str = Field(default="", description="최종 답변 또는 중간 안내 문장")
    clarification: str | None = Field(
        default=None,
        description="추가 정보가 필요할 때 사용자에게 묻는 질문",
    )


class AgentState(BaseModel):
    """한 번의 Agent 실행 동안 Runtime이 관리하는 내부 상태다.

    reservation_user_id와 reservation_session_id는 예약 Tool 실행에만 사용한다.
    두 값은 외부 API 응답이나 Trace에 포함되지 않아야 한다.
    """

    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_id: str
    session_id: str
    question: str
    status: AgentStatus | None = None
    intent: AgentIntent = None
    termination_reason: str | None = None
    llm_calls: int = 0
    tool_attempts: int = 0
    repeat_counts: dict[str, int] = Field(default_factory=dict)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    trace: list[TraceItem] = Field(default_factory=list)
    answer: str | None = None
    approval: dict[str, Any] | None = None

    # 아래 두 값은 로그인 성공 후 서버가 내부적으로만 주입한다.
    # 클라이언트 요청 JSON으로 받지 않으며, 응답으로도 반환하지 않는다.
    reservation_user_id: str | None = Field(default=None, exclude=True)
    reservation_session_id: str | None = Field(default=None, exclude=True)


class AgentAskResponse(BaseModel):
    """관람객 화면에 반환하는 Agent 실행 결과다."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    agent_id: Literal["zoo_guide"]
    session_id: str
    intent: AgentIntent
    status: AgentStatus
    termination_reason: str
    final_answer: str
    sources: list[Source] = Field(default_factory=list)
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    pending_action: dict[str, Any] | None = None
    trace: list[TraceItem] = Field(default_factory=list)