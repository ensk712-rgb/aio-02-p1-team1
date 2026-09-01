"""RAG 경로와 Tool 경로를 하나로 묶는 단일 진입점입니다.

`routers/agent_router.py`가 이 서비스만 호출합니다. 실행 순서와 정책(승인 필요 여부,
최종 답변 문구)은 여기서 소유하고, 자연어 해석은 `agents.routing_agent`에,
Tool 실행은 `tools.executor`에 위임합니다.
"""

import json

from app.agents.routing_agent import select_tool
from app.repositories import pending_action_repository, session_repository
from app.services import rag_service
from app.tools.executor import ToolRunResult, execute_tool_safely
from app.tools.registry import TOOL_REGISTRY


def handle_ask(message: str, session_id: str) -> dict:
    session_repository.append_message(session_id, "user", message)

    tool_name, arguments = select_tool(message)

    if tool_name is None:
        chunks = rag_service.retrieve_chunks(message)
        result = rag_service.answer_with_citations(message, chunks)
        session_repository.append_message(session_id, "assistant", result["answer"])
        return {
            "intent": "rag",
            "status": "completed",
            "final_answer": result["answer"],
            "sources": result["sources"],
            "tool_call": None,
            "pending_action": None,
        }

    spec = TOOL_REGISTRY.get(tool_name)
    if spec is not None and spec.requires_approval:
        summary = _summarize_reservation(arguments)
        action = pending_action_repository.create(tool_name, arguments, summary)
        return {
            "intent": "tool",
            "status": "confirmation_required",
            "final_answer": summary,
            "sources": [],
            "tool_call": {"name": tool_name, "arguments": arguments},
            "pending_action": action,
        }

    tool_result = execute_tool_safely(tool_name, arguments)
    final_answer = _explain_tool_result(tool_name, tool_result)
    session_repository.append_message(session_id, "assistant", final_answer)
    return {
        "intent": "tool",
        "status": "completed" if tool_result.success else "error",
        "final_answer": final_answer,
        "sources": [],
        "tool_call": {"name": tool_name, "arguments": arguments, "result": tool_result.data},
        "pending_action": None,
    }


def confirm_pending_action(action_id: str, session_id: str) -> dict:
    action = pending_action_repository.consume(action_id)
    if action is None:
        return {
            "intent": "tool",
            "status": "rejected",
            "final_answer": "확인 시간이 지났어요. 다시 요청해 주세요.",
            "sources": [],
            "tool_call": None,
            "pending_action": None,
        }

    tool_result = execute_tool_safely(action["tool_name"], action["arguments"])
    final_answer = _explain_tool_result(action["tool_name"], tool_result)
    session_repository.append_message(session_id, "assistant", final_answer)
    return {
        "intent": "tool",
        "status": "completed" if tool_result.success else "error",
        "final_answer": final_answer,
        "sources": [],
        "tool_call": {"name": action["tool_name"], "arguments": action["arguments"], "result": tool_result.data},
        "pending_action": None,
    }


def _summarize_reservation(arguments: dict) -> str:
    program = arguments.get("program", "체험 프로그램")
    time = arguments.get("time", "")
    headcount = arguments.get("headcount", "")
    return f"{time} {program} · {headcount}명으로 예약할까요? 확인을 누르면 진행돼요."


def _explain_tool_result(tool_name: str, tool_result: ToolRunResult) -> str:
    """Backend 정책이 최종 문구를 결정합니다 — LLM이 아니라 코드가 답을 씁니다."""
    if not tool_result.success:
        detail = (tool_result.error or {}).get("message", "알 수 없는 오류")
        return f"요청을 처리하지 못했어요: {detail}"

    data = tool_result.data

    if tool_name == "get_feeding_schedule":
        if not data.get("found"):
            return data.get("message", "해당 동물사를 찾을 수 없어요.")
        return f"다음 {data['animal']} 먹이시간은 {data['time']}, {data['location']}이에요."

    if tool_name == "check_closure_status":
        if "closed_habitats" in data:
            closed = data["closed_habitats"]
            if not closed:
                return "오늘은 임시 휴장한 동물사가 없어요."
            lines = ", ".join(f"{h}({reason})" for h, reason in closed.items())
            return f"현재 임시 휴장 중: {lines}"
        if data["closed"]:
            return f"{data['habitat']}은(는) 휴장 중이에요 — {data['reason']}"
        return f"{data['habitat']}은(는) 정상 운영 중이에요."

    if tool_name == "find_habitat_route":
        if not data.get("found"):
            return data.get("message", "경로 정보를 찾을 수 없어요.")
        base = f"{data['from']}에서 {data['to']}까지 약 {data['estimated_minutes']}분 걸려요."
        return f"{base} {data['note']}".strip() if data.get("note") else base

    if tool_name == "lookup_ticket_scope":
        if not data.get("found"):
            return data.get("message", "해당 티켓 정보를 찾을 수 없어요.")
        night = "야간개장 포함" if data["night_open"] else "야간개장 미포함"
        experience = "체험 프로그램 포함" if data["experience_included"] else "체험 프로그램 미포함"
        return f"{data['ticket_type']}은 {night}, {experience}이에요."

    if tool_name == "reserve_experience_program":
        if data.get("success"):
            return f"예약이 확정됐어요. 예약번호는 {data['reservation_id']}입니다."
        return data.get("message", "예약에 실패했어요.")

    return json.dumps(data, ensure_ascii=False)
