"""외부 API 없이 결정적인 테스트를 수행하는 Scripted Mock Provider를 구현한다."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from backend.app.providers.base import ModelProvider, ProviderToolSchema
from backend.app.schemas.agent import ModelTurn
from backend.app.schemas.tools import ToolCallRecord


@dataclass(frozen=True)
class ProviderCall:
    """Provider가 받은 한 번의 판단 요청 기록이다."""

    question: str
    previous_response_id: str | None
    tool_names: tuple[str, ...]
    tool_result_names: tuple[str, ...]


class ScriptedMockProvider:
    """미리 준비된 ModelTurn을 순서대로 반환하는 테스트용 Provider다."""

    def __init__(self, turns: Sequence[ModelTurn]) -> None:
        """반환할 응답 목록을 저장한다."""
        if not turns:
            raise ValueError("ScriptedMockProvider에는 최소 한 개의 ModelTurn이 필요합니다.")

        self._turns = list(turns)
        self._next_turn_index = 0
        self._call_history: list[ProviderCall] = []

    @property
    def call_history(self) -> tuple[ProviderCall, ...]:
        """Provider 호출 기록을 읽기 전용 튜플로 반환한다."""
        return tuple(self._call_history)

    @property
    def remaining_turns(self) -> int:
        """아직 반환하지 않은 응답 수를 반환한다."""
        return len(self._turns) - self._next_turn_index

    async def next_turn(
        self,
        *,
        question: str,
        instructions: str,
        tools: Sequence[ProviderToolSchema],
        previous_response_id: str | None,
        tool_outputs: Sequence[ToolCallRecord],
    ) -> ModelTurn:
        """다음에 준비된 ModelTurn을 반환하고 호출 정보를 기록한다."""
        del instructions

        if self._next_turn_index >= len(self._turns):
            raise RuntimeError(
                "ScriptedMockProvider의 응답이 모두 소진되었습니다. "
                "테스트 시나리오에 필요한 ModelTurn을 추가하세요."
            )

        self._call_history.append(
            ProviderCall(
                question=question,
                previous_response_id=previous_response_id,
                tool_names=tuple(schema["name"] for schema in tools),
                tool_result_names=tuple(record.name for record in tool_outputs),
            )
        )

        turn = self._turns[self._next_turn_index]
        self._next_turn_index += 1
        return turn


def is_model_provider(provider: Any) -> bool:
    """객체가 Runtime에서 사용할 Provider 인터페이스를 만족하는지 확인한다."""
    return isinstance(provider, ModelProvider)