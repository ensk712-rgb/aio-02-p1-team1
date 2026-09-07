"""화면 단위 시험과 로컬 UI 확인을 위한 결정적 Fake Client."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any


class FakeAgentClient:
    def __init__(self) -> None:
        self._reservations = [
            {
                "action_id": "action_fake_001",
                "user_id": "TEST",
                "program": "사육사 체험",
                "visit_time": "15:00",
                "headcount": 2,
                "status": "pending",
                "created_at": "2026-09-07T12:00:00+00:00",
                "decided_at": None,
            }
        ]
        self._pending_action: dict[str, Any] | None = None

    def login(self, user_id: str, password: str) -> dict[str, Any]:
        identities = {"TEST": "user", "admin": "admin"}
        if user_id not in identities or password != "1234":
            from frontend.clients.agent_client import AgentClientError
            raise AgentClientError("아이디 또는 비밀번호가 올바르지 않습니다.", kind="http")
        return {
            "success": True,
            "user_id": user_id,
            "role": identities[user_id],
            "auth_session_id": f"auth_fake_{identities[user_id]}",
        }

    def logout(self, auth_session_id: str) -> None:
        return None

    def create_reservation(self, auth_session_id: str, **payload: Any) -> dict[str, Any]:
        created_at = datetime.now(timezone.utc)
        item = {
            "action_id": f"action_fake_{len(self._reservations) + 1:03d}",
            "user_id": "TEST",
            "approval_status": "pending",
            "created_at": created_at.isoformat(),
            "expires_at": (created_at + timedelta(seconds=120)).isoformat(),
            "tool_name": "reserve_experience_program",
            "summary": f"{payload['visit_time']} {payload['program']} · {payload['headcount']}명",
            "arguments": {"user_id": "TEST", **payload},
            **payload,
        }
        self._pending_action = item
        return {
            "status": "confirmation_required",
            "message": "예약 내용을 확인해 주세요.",
            "pending_action": dict(item),
        }

    def confirm_reservation(
        self, auth_session_id: str, action_id: str, decision: str
    ) -> dict[str, Any]:
        from frontend.clients.agent_client import AgentClientError

        if self._pending_action is None or self._pending_action["action_id"] != action_id:
            raise AgentClientError("이미 처리된 예약 요청입니다.", kind="http")
        action = self._pending_action
        self._pending_action = None
        if decision == "cancel":
            action["approval_status"] = "cancelled"
            return {"status": "rejected", "message": "예약 요청을 취소했습니다.", "pending_action": action}
        reservation = {
            key: action[key]
            for key in ("action_id", "user_id", "program", "visit_time", "headcount", "created_at")
        }
        reservation.update({"status": "pending", "decided_at": None})
        self._reservations.append(reservation)
        action["approval_status"] = "completed"
        return {
            "status": "completed",
            "message": "예약 승인 요청을 관리자에게 전달했습니다.",
            "pending_action": action,
            "reservation": reservation,
        }

    def get_my_reservations(self, auth_session_id: str) -> dict[str, Any]:
        return {"items": [dict(item) for item in self._reservations]}

    def get_pending_reservations(self, auth_session_id: str) -> dict[str, Any]:
        return {"items": [dict(item) for item in self._reservations if item["status"] == "pending"]}

    def get_admin_trace(self, auth_session_id: str, session_id: str) -> dict[str, Any]:
        return {
            "runs": [
                {
                    "run_id": "run_fake_001",
                    "status": "completed",
                    "trace": [
                        {"event": "request_received", "session_id": session_id},
                        {"event": "tool_completed", "tool_name": "get_feeding_schedule"},
                    ],
                }
            ] if session_id else []
        }

    def decide_reservation(self, auth_session_id: str, action_id: str, decision: str) -> dict[str, Any]:
        item = next(item for item in self._reservations if item["action_id"] == action_id)
        item["status"] = "approved" if decision == "approve" else "rejected"
        return dict(item)

    def get_health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "backend": "ok",
            "mcp": "ok",
            "storage": "memory",
            "app_mode": "mock",
        }

    def ask(self, message: str, session_id: str | None = None) -> dict[str, Any]:
        client_error_kinds = {
            "client_connection": ("안내 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요.", "connection"),
            "client_timeout": ("응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.", "timeout"),
            "client_http": ("안내 서버가 요청을 처리하지 못했습니다.", "http"),
            "client_invalid_response": ("안내 서버의 응답 형식이 올바르지 않습니다.", "invalid_response"),
        }
        if message in client_error_kinds:
            from frontend.clients.agent_client import AgentClientError

            error_message, kind = client_error_kinds[message]
            raise AgentClientError(error_message, kind=kind)
        status = self._status_from(message)
        answer = {
            "completed": "교육용 운영 데이터 기준으로 해양관의 다음 펭귄 먹이시간은 14:30입니다.",
            "needs_clarification": "출발 위치와 목적지를 함께 알려 주세요.",
            "rejected": "이 요청은 안전 정책에 따라 실행할 수 없습니다.",
            "stopped": "동일한 조회가 반복되어 안전하게 중단했습니다.",
            "error": "운영 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.",
        }[status]
        tool_calls = [] if status != "completed" else [self._tool_call()]
        return {
            "run_id": "run_fake_001",
            "agent_id": "zoo_guide",
            "session_id": session_id or "session_fake_001",
            "intent": "tool" if tool_calls else None,
            "status": status,
            "termination_reason": "model_finished" if status == "completed" else status,
            "final_answer": answer,
            "sources": [
                {
                    "doc_id": "animal_penguin",
                    "title": "펭귄 동물 정보카드",
                    "page": 1,
                    "score": 0.82,
                }
            ] if status == "completed" else [],
            "tool_calls": tool_calls,
            "pending_action": None,
            "trace": [],
        }

    @staticmethod
    def _status_from(message: str) -> str:
        for status in ("needs_clarification", "rejected", "stopped", "error"):
            if status in message:
                return status
        return "completed"

    @staticmethod
    def _tool_call() -> dict[str, Any]:
        return {
            "name": "get_feeding_schedule",
            "arguments": {"habitat": "해양관"},
            "risk": "read",
            "result": {
                "success": True,
                "data": {
                    "habitat": "해양관",
                    "animal": "펭귄",
                    "next_feeding_at": "2026-09-07T14:30:00+09:00",
                    "location": "해양관 관람대",
                    "as_of": "2026-09-07T12:00:00+09:00",
                },
                "error": None,
                "source": "mock_zoo_operations",
                "retrieved_at": "2026-09-07T12:00:00+09:00",
            },
        }
