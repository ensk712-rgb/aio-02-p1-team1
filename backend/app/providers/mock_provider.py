"""외부 API 없이 결정적인 테스트를 수행하는 Scripted Mock Provider를 구현한다."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from backend.app.providers.base import ModelProvider, ProviderToolSchema
from backend.app.schemas.agent import ModelTurn
from backend.app.schemas.agent import ModelToolCall
from backend.app.schemas.tools import ToolCallRecord


@dataclass(frozen=True)
class ProviderCall:
    """Provider가 받은 한 번의 판단 요청 기록이다."""

    question: str
    instructions: str
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
        if self._next_turn_index >= len(self._turns):
            raise RuntimeError(
                "ScriptedMockProvider의 응답이 모두 소진되었습니다. "
                "테스트 시나리오에 필요한 ModelTurn을 추가하세요."
            )

        self._call_history.append(
            ProviderCall(
                question=question,
                instructions=instructions,
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


class ZooMockProvider:
    """N-01~N-04를 반복 가능하게 실행하는 로컬 시연 Provider."""

    async def next_turn(
        self,
        *,
        question: str,
        instructions: str,
        tools: Sequence[ProviderToolSchema],
        previous_response_id: str | None,
        tool_outputs: Sequence[ToolCallRecord],
    ) -> ModelTurn:
        del instructions
        response_id = f"mock_{abs(hash((question, previous_response_id))) & 0xFFFFFFFF:x}"

        if tool_outputs:
            return ModelTurn(
                response_id=response_id,
                text=self._answer_from_result(tool_outputs[-1]),
            )

        available = {tool["name"] for tool in tools}
        selected = self._select_tool(question)
        if selected is None:
            return ModelTurn(
                response_id=response_id,
                text="동물 정보, 먹이시간, 휴장 상태 또는 관람 경로를 질문해 주세요.",
            )

        name, arguments = selected
        if name not in available:
            raise RuntimeError("필요한 조회 Tool을 MCP Server에서 찾을 수 없습니다.")
        if name == "find_habitat_route" and not arguments:
            return ModelTurn(
                response_id=response_id,
                clarification="출발 위치와 목적지를 함께 알려 주세요.",
            )
        import json

        return ModelTurn(
            response_id=response_id,
            calls=[
                ModelToolCall(
                    call_id=f"call_{response_id}",
                    name=name,
                    arguments_json=json.dumps(arguments, ensure_ascii=False),
                )
            ],
        )

    @staticmethod
    def _select_tool(question: str) -> tuple[str, dict[str, str]] | None:
        normalized = question.replace(" ", "")
        habitats = ["정문", "해양관", "맹수관", "초식동물관", "열대관"]
        mentioned = [name for name in habitats if name in question]
        if "먹이" in normalized:
            return "get_feeding_schedule", {"habitat": mentioned[-1] if mentioned else "해양관"}
        if "휴장" in normalized or "쉬는" in normalized or "닫" in normalized:
            return "check_closure_status", ({"habitat": mentioned[0]} if mentioned else {})
        if "경로" in normalized or "가는길" in normalized or "어떻게가" in normalized:
            if len(mentioned) < 2:
                return "find_habitat_route", {}
            return "find_habitat_route", {"current": mentioned[0], "destination": mentioned[1]}
        if any(animal in normalized for animal in ("호랑이", "펭귄", "판다", "기린", "사자", "동물")):
            return "retrieve_animal_info", {"query": question, "collection": "animal_cards"}
        return None

    @staticmethod
    def _answer_from_result(record: ToolCallRecord) -> str:
        data = record.result.data
        if record.name == "get_feeding_schedule":
            when = data.get("next_feeding_at") or "오늘 남은 일정 없음"
            return f"{data.get('habitat')}의 {data.get('animal')} 다음 먹이시간은 {when}입니다."
        if record.name == "check_closure_status":
            items = data.get("items", [])
            closed = [item["habitat"] for item in items if item.get("closed")]
            return "현재 휴장 시설: " + (", ".join(closed) if closed else "없음") + "."
        if record.name == "find_habitat_route":
            path = " → ".join(data.get("path", []))
            return f"관람 경로는 {path}이며 예상 시간은 {data.get('estimated_minutes')}분입니다."
        chunks = data.get("chunks", [])
        if not chunks:
            return "제공된 동물 정보카드에서 확인할 수 없습니다."
        first = chunks[0]
        return f"{first.get('text', '')} (출처: {first.get('title', '동물 정보카드')})"
