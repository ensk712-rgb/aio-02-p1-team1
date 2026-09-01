"""챗봇 진입점(`/api/agent/*`)이 사용하는 요청·응답 계약입니다.

Frontend와 backend 사이의 유일한 접점이므로, 필드를 바꾸면 두 쪽 모두 함께 고쳐야 합니다.
"""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class AgentAskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2000)
    session_id: str = Field(default="guest", min_length=1, max_length=100)


class AgentConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1, max_length=64)
    session_id: str = Field(default="guest", min_length=1, max_length=100)


class PendingAction(BaseModel):
    action_id: str
    tool_name: str
    summary: str
    arguments: dict[str, Any] = Field(default_factory=dict)


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] | None = None


class Source(BaseModel):
    title: str
    source: str


class AgentAskResponse(BaseModel):
    intent: Literal["rag", "tool"]
    status: Literal["completed", "confirmation_required", "rejected", "error"]
    final_answer: str
    sources: list[Source] = Field(default_factory=list)
    tool_call: ToolCall | None = None
    pending_action: PendingAction | None = None
