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

    def get_auth_session(self, auth_session_id: str) -> dict[str, Any]:
        if not auth_session_id.startswith("auth_fake_"):
            from frontend.clients.agent_client import AgentClientError
            raise AgentClientError("유효하지 않거나 만료된 세션입니다.", kind="http")
        user_id = "admin" if auth_session_id.endswith("admin") else "TEST"
        return {"success": True, "user_id": user_id, "role": "admin" if user_id == "admin" else "user"}

    def ask_stream(
        self, message: str, session_id: str | None = None, *, auth_session_id: str | None = None
    ):
        response = self.ask(message, session_id, auth_session_id=auth_session_id)
        answer = response.get("final_answer", "")
        for start in range(0, len(answer), 12):
            yield {"event": "delta", "data": {"text": answer[start:start + 12]}}
        yield {"event": "done", "data": response}

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
            "session_id": session_id,
            "detail_expired": False,
            "summary": {"session_id": session_id, "status": "completed"},
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

    def list_admin_trace_sessions(self, auth_session_id: str) -> dict[str, Any]:
        return {
            "sessions": [
                {
                    "session_id": "guest-test",
                    "last_run_at": "2026-09-09T03:00:00+00:00",
                    "status": "completed",
                    "question_preview": "펭귄 먹이시간을 알려줘",
                    "tools": ["get_feeding_schedule"],
                }
            ]
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

    def get_public_weather(self, region: str = "서울") -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        samples = [("clear", 27, 18, 10), ("cloudy", 25, 17, 30), ("rain", 22, 16, 70), ("clear", 26, 17, 15)]
        forecast = [
            {
                "date": (now + timedelta(days=offset)).date().isoformat(),
                "condition": condition,
                "temperature_max_c": high,
                "temperature_min_c": low,
                "precipitation_probability_percent": rain,
            }
            for offset, (condition, high, low, rain) in enumerate(samples)
        ]
        return {
            "success": True,
            "data": {
                "region": region,
                "condition": "clear",
                "indoor_recommended": False,
                "current": {
                    "temperature_c": 24.6,
                    "apparent_temperature_c": 25.1,
                    "humidity_percent": 54,
                    "wind_speed_kmh": 7.2,
                    "condition": "clear",
                },
                "forecast": forecast,
                "as_of": now.isoformat(),
            },
            "error": None,
            "source": "open_meteo_forecast",
            "retrieved_at": now.isoformat(),
        }

    _CLOSURES = [
        {"habitat": "정문", "closed": False, "reason": None},
        {"habitat": "호랑이관", "closed": False, "reason": None},
        {"habitat": "해양관", "closed": False, "reason": None},
        {"habitat": "코끼리관", "closed": True, "reason": "시설 점검으로 임시 휴장"},
        {"habitat": "기린관", "closed": False, "reason": None},
    ]

    _ROUTES = {
        ("정문", "호랑이관"): {"path": ["정문", "호랑이관"], "estimated_minutes": 10},
        ("정문", "해양관"): {"path": ["정문", "해양관"], "estimated_minutes": 15},
        ("정문", "코끼리관"): {"path": ["정문", "코끼리관"], "estimated_minutes": 12},
        ("정문", "기린관"): {"path": ["정문", "기린관"], "estimated_minutes": 8},
    }

    def get_habitat_route(self, current: str, destination: str) -> dict[str, Any]:
        """실제 routes.json(정문 기준 4개 구간)과 같은 값을 결정적으로 반환한다."""
        now = datetime.now(timezone.utc)
        if current == destination:
            data = {
                "current": current,
                "destination": destination,
                "path": [current],
                "estimated_minutes": 0,
                "as_of": now.isoformat(),
            }
            return {
                "success": True,
                "data": data,
                "error": None,
                "source": "mock_zoo_operations",
                "retrieved_at": now.isoformat(),
            }
        route = self._ROUTES.get((current, destination))
        if route is None:
            return {
                "success": False,
                "data": {},
                "error": {
                    "code": "ROUTE_NOT_FOUND",
                    "message": f"'{current}'에서 '{destination}'까지의 경로를 찾을 수 없습니다.",
                },
                "source": "mock_zoo_operations",
                "retrieved_at": now.isoformat(),
            }
        return {
            "success": True,
            "data": {
                "current": current,
                "destination": destination,
                "path": route["path"],
                "estimated_minutes": route["estimated_minutes"],
                "as_of": now.isoformat(),
            },
            "error": None,
            "source": "mock_zoo_operations",
            "retrieved_at": now.isoformat(),
        }

    def get_closure_status(self, habitat: str | None = None) -> dict[str, Any]:
        """실제 closures.json(코끼리관만 휴장)과 같은 값을 결정적으로 반환한다."""
        now = datetime.now(timezone.utc)
        if habitat is None:
            items = [dict(row) for row in self._CLOSURES]
        else:
            row = next((row for row in self._CLOSURES if row["habitat"] == habitat), None)
            if row is None:
                return {
                    "success": False,
                    "data": {},
                    "error": {
                        "code": "HABITAT_NOT_FOUND",
                        "message": f"'{habitat}'은(는) 등록된 시설이 아닙니다.",
                    },
                    "source": "mock_zoo_operations",
                    "retrieved_at": now.isoformat(),
                }
            items = [dict(row)]
        return {
            "success": True,
            "data": {"items": items, "as_of": now.isoformat()},
            "error": None,
            "source": "mock_zoo_operations",
            "retrieved_at": now.isoformat(),
        }

    def analyze_animal_image(
        self, image_bytes: bytes, *, filename: str, content_type: str
    ) -> dict[str, Any]:
        """실제 Vision 호출 없이 결정적인 분석 문장을 돌려준다."""
        now = datetime.now(timezone.utc)
        return {
            "success": True,
            "data": {"analysis": "사진 속 동물은 자이언트 판다로 추정됩니다. (Fake 모드)"},
            "error": None,
            "source": "vision_animal_image",
            "retrieved_at": now.isoformat(),
        }

    def get_course_info(
        self,
        *,
        available_minutes: int,
        child_accompanying: bool = False,
        current: str = "정문",
    ) -> dict[str, Any]:
        """GET /api/tools/course-info의 ToolRunResult 계약을 그대로 흉내 낸다.

        UI 시험용으로 결정적인 2정거장 코스를 항상 반환한다(§7 표시 로직을
        Fake 모드에서도 눈으로 확인할 수 있도록).
        """
        now = datetime.now(timezone.utc)
        stops = [
            {
                "habitat": "해양관",
                "travel_minutes": 15,
                "visit_minutes": 25,
                "cumulative_minutes": 40,
            },
            {
                "habitat": "기린관",
                "travel_minutes": 10,
                "visit_minutes": 20,
                "cumulative_minutes": 70,
            },
        ]
        total_minutes = stops[-1]["cumulative_minutes"] if stops else 0
        return {
            "success": True,
            "data": {
                "current": current,
                "available_minutes": available_minutes,
                "facility_scope": "all",
                "stops": stops,
                "total_minutes": total_minutes,
                "remaining_minutes": available_minutes - total_minutes,
                "weather_lookup_succeeded": True,
            },
            "error": None,
            "source": "mock_zoo_operations",
            "retrieved_at": now.isoformat(),
        }


    def ask(
        self,
        message: str,
        session_id: str | None = None,
        *,
        auth_session_id: str | None = None,
    ) -> dict[str, Any]:

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
