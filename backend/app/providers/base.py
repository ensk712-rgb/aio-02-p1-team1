"""모든 Model Provider가 지켜야 하는 공통 인터페이스를 정의한다."""

from collections.abc import Sequence
from typing import Any, Protocol, TypedDict, runtime_checkable

from backend.app.schemas.agent import ModelTurn
from backend.app.schemas.tools import ToolCallRecord


class ProviderToolSchema(TypedDict):
    """Provider에 전달하는 Tool Schema의 표준 형태다."""

    name: str
    description: str
    input_schema: dict[str, Any]


@runtime_checkable
class ModelProvider(Protocol):
    """Mock과 OpenAI Provider를 같은 방식으로 호출하기 위한 약속이다.

    Provider는 다음 행동만 제안한다.
    Tool 실행, allowlist 검사, 인자 검증, 반복 제한은 Runtime과 Executor의 책임이다.
    """

    async def next_turn(
        self,
        *,
        question: str,
        instructions: str,
        tools: Sequence[ProviderToolSchema],
        previous_response_id: str | None,
        tool_outputs: Sequence[ToolCallRecord],
    ) -> ModelTurn:
        """질문과 이전 Tool 결과를 바탕으로 다음 ModelTurn을 반환한다."""