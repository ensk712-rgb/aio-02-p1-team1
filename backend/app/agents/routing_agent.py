"""자연어 요청에서 실행할 Tool을 고르기만 합니다.

Tool을 하나도 고르지 않으면 지식 질문(RAG)으로 간주합니다 — `agent_orchestration_service`가
이 결과를 보고 RAG 또는 Tool 경로로 분기합니다. 이 파일은 승인 여부·정책·실행을 결정하지
않습니다.
"""

import json

from app.core.config import settings
from app.tools.registry import get_tool_definitions

_INSTRUCTIONS = (
    "너는 동물원 안내 에이전트의 라우팅 담당이야. "
    "먹이시간, 임시휴장, 길찾기, 티켓 범위, 체험 프로그램 예약처럼 실시간·상태 정보가 필요한 "
    "질문이면 알맞은 Tool을 정확히 하나 선택해서 호출해. "
    "동물의 생태, 나이, 출신, 서식지처럼 문서에서 찾아야 하는 지식 질문이거나 애매하면 "
    "Tool을 호출하지 마."
)


def select_tool(message: str) -> tuple[str | None, dict]:
    """OpenAI Tool Calling으로 Tool 이름과 arguments를 고릅니다. 실행은 하지 않습니다."""
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")

    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key)
    tools = [
        {"type": "function", "name": tool["name"], "description": tool["description"], "parameters": tool["input_schema"]}
        for tool in get_tool_definitions()
    ]

    response = client.responses.create(
        model=settings.openai_model,
        instructions=_INSTRUCTIONS,
        input=message,
        tools=tools,
        tool_choice="auto",
    )

    call = next((item for item in response.output if item.type == "function_call"), None)
    if call is None:
        return None, {}
    return call.name, json.loads(call.arguments or "{}")
