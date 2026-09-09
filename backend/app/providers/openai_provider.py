"""OpenAI Responses API 결과를 프로젝트 ModelTurn으로 변환하는 Provider를 구현한다."""

import json
from collections.abc import Sequence
from typing import Any, Protocol

from openai import AsyncOpenAI

from backend.app.providers.base import ProviderToolSchema
from backend.app.schemas.agent import ModelToolCall, ModelTurn
from backend.app.schemas.tools import ToolCallRecord


class ResponsesApiProtocol(Protocol):
    """OpenAI Client의 responses API에 필요한 최소 기능이다."""

    async def create(self, **kwargs: Any) -> Any:
        """Responses API 요청을 보내고 응답 객체를 반환한다."""


class OpenAIClientProtocol(Protocol):
    """OpenAIProvider가 사용하는 최소 Client 구조다."""

    responses: ResponsesApiProtocol


class OpenAIProvider:
    """OpenAI Responses API를 ModelProvider 계약으로 변환하는 Provider다."""

    def __init__(
        self,
        *,
        model: str,
        api_key: str | None = None,
        client: OpenAIClientProtocol | None = None,
        timeout_seconds: float = 30.0,
    ) -> None:
        """OpenAI Client 또는 테스트용 Fake Client를 주입한다.

        Args:
            model: 사용할 OpenAI 모델 이름.
            api_key: 실제 OpenAI API Key. Fake Client 테스트에서는 필요 없다.
            client: 테스트 또는 DI를 위해 직접 넣는 OpenAI Client.
            timeout_seconds: OpenAI 호출 한 번의 제한 시간.
        """
        if client is None:
            if not api_key:
                raise ValueError(
                    "실제 OpenAIProvider 생성에는 api_key가 필요합니다."
                )

            client = AsyncOpenAI(
                api_key=api_key,
                timeout=timeout_seconds,
                max_retries=0,
            )

        self._client = client
        self._model = model

        # previous_response_id별 Function Call ID를 보관한다.
        # 다음 요청에서 Tool 결과를 올바른 call_id와 연결하기 위해 필요하다.
        self._response_call_ids: dict[str, list[str]] = {}

    async def next_turn(
        self,
        *,
        question: str,
        instructions: str,
        tools: Sequence[ProviderToolSchema],
        previous_response_id: str | None,
        tool_outputs: Sequence[ToolCallRecord],
    ) -> ModelTurn:
        """OpenAI에 다음 행동 판단을 요청하고 ModelTurn으로 변환한다."""
        openai_tools = [
            self._to_openai_tool_schema(tool)
            for tool in tools
        ]
        openai_tools.append(self._clarification_tool_schema())

        request_input = self._build_input(
            question=question,
            previous_response_id=previous_response_id,
            tool_outputs=tool_outputs,
        )

        response = await self._client.responses.create(
            model=self._model,
            instructions=instructions,
            input=request_input,
            tools=openai_tools,
            parallel_tool_calls=False,
            previous_response_id=previous_response_id,
        )

        return self._to_model_turn(response)

    @staticmethod
    def _to_openai_tool_schema(
        tool: ProviderToolSchema,
    ) -> dict[str, Any]:
        """프로젝트 Tool Schema를 OpenAI Function Tool 형식으로 변환한다.

        MCP가 제공하는 JSON Schema에는 OpenAI strict 모드가 허용하지 않는
        선택 필드 또는 제약 표현이 포함될 수 있다. 따라서 OpenAI에는
        strict 모드를 강제하지 않고, 실제 Tool 인자 검증은 Backend Executor의
        Pydantic 모델이 담당한다.
        """
        return {
            "type": "function",
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
            "strict": False,
        }

    @staticmethod
    def _clarification_tool_schema() -> dict[str, Any]:
        """추가 질문을 구조적으로 표현하는 내부 제어 Tool Schema를 반환한다.

        이 Tool은 MCP 또는 Executor에서 실행하지 않는다.
        OpenAIProvider가 clarification 문자열로 변환한 뒤 Runtime을 종료한다.
        """
        return {
            "type": "function",
            "name": "request_clarification",
            "description": "필수 정보가 부족할 때 사용자에게 추가 정보를 요청한다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "minLength": 1,
                        "description": "사용자에게 보여 줄 추가 질문",
                    }
                },
                "required": ["question"],
                "additionalProperties": False,
            },
            "strict": True,
        }

    def _build_input(
        self,
        *,
        question: str,
        previous_response_id: str | None,
        tool_outputs: Sequence[ToolCallRecord],
    ) -> str | list[dict[str, str]]:
        """첫 질문 또는 직전 Tool 결과 목록을 Responses API 입력으로 만든다."""
        if previous_response_id is None:
            return question

        call_ids = self._response_call_ids.get(previous_response_id)

        if call_ids is None:
            raise ValueError("이전 OpenAI 응답의 Tool Call 정보를 찾을 수 없습니다.")

        if len(call_ids) != len(tool_outputs):
            raise ValueError(
                "이전 Function Call 수와 Tool 실행 결과 수가 일치하지 않습니다."
            )

        return [
            {
                "type": "function_call_output",
                "call_id": call_id,
                "output": json.dumps(
                    record.result.model_dump(mode="json"),
                    ensure_ascii=False,
                ),
            }
            for call_id, record in zip(call_ids, tool_outputs, strict=True)
        ]

    def _to_model_turn(self, response: Any) -> ModelTurn:
        """OpenAI Responses API 응답 객체를 프로젝트 ModelTurn으로 변환한다."""
        response_id = str(response.id)
        function_calls: list[ModelToolCall] = []

        for item in getattr(response, "output", []):
            if getattr(item, "type", None) != "function_call":
                continue

            name = str(getattr(item, "name", ""))
            call_id = str(getattr(item, "call_id", ""))
            arguments_json = str(getattr(item, "arguments", ""))

            if name == "request_clarification":
                clarification = self._extract_clarification(arguments_json)

                return ModelTurn(
                    response_id=response_id,
                    calls=[],
                    text="",
                    clarification=clarification,
                )

            function_calls.append(
                ModelToolCall(
                    call_id=call_id,
                    name=name,
                    arguments_json=arguments_json,
                )
            )

        self._response_call_ids[response_id] = [
            call.call_id for call in function_calls
        ]

        return ModelTurn(
            response_id=response_id,
            calls=function_calls,
            text=str(getattr(response, "output_text", "")),
            clarification=None,
        )

    @staticmethod
    def _extract_clarification(arguments_json: str) -> str:
        """request_clarification의 JSON 인자에서 사용자 질문을 꺼낸다."""
        try:
            arguments = json.loads(arguments_json)
        except json.JSONDecodeError as error:
            raise ValueError("추가 질문 Tool 인자가 올바른 JSON이 아닙니다.") from error

        question = arguments.get("question")

        if not isinstance(question, str) or not question.strip():
            raise ValueError("추가 질문에는 비어 있지 않은 question 값이 필요합니다.")

        return question.strip()
