"""Streamlit이 사용하는 동기 Backend HTTP Client."""

from __future__ import annotations

from typing import Any

import httpx


class AgentClientError(RuntimeError):
    """화면에 안전하게 표시할 Backend 연결 오류."""

    def __init__(self, message: str, *, kind: str) -> None:
        super().__init__(message)
        self.kind = kind


class AgentClient:
    def __init__(self, base_url: str, *, timeout_seconds: float = 95) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds

    def ask(
        self,
        message: str,
        session_id: str | None = None,
        *,
        auth_session_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": message}
        if session_id:
            payload["session_id"] = session_id
        headers = {"X-Auth-Session": auth_session_id} if auth_session_id else {}
        return self._request("POST", "/api/agent/ask", json=payload, headers=headers)

    def get_health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def login(self, user_id: str, password: str) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/auth/login",
            json={"user_id": user_id, "password": password},
        )

    def logout(self, auth_session_id: str) -> None:
        self._request(
            "POST",
            "/api/auth/logout",
            headers={"X-Auth-Session": auth_session_id},
            allow_empty=True,
        )

    def create_reservation(
        self,
        auth_session_id: str,
        *,
        program: str,
        visit_time: str,
        headcount: int,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/reservations",
            headers={"X-Auth-Session": auth_session_id},
            json={"program": program, "visit_time": visit_time, "headcount": headcount},
        )

    def get_my_reservations(self, auth_session_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/reservations/mine",
            headers={"X-Auth-Session": auth_session_id},
        )

    def confirm_reservation(
        self,
        auth_session_id: str,
        action_id: str,
        decision: str,
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            "/api/agent/confirm",
            headers={"X-Auth-Session": auth_session_id},
            json={
                "action_id": action_id,
                "session_id": auth_session_id,
                "decision": decision,
            },
        )

    def get_pending_reservations(self, auth_session_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/admin/reservations/pending",
            headers={"X-Auth-Session": auth_session_id},
        )

    def get_admin_trace(self, auth_session_id: str, session_id: str) -> dict[str, Any]:
        return self._request(
            "GET",
            "/api/admin/trace",
            headers={"X-Auth-Session": auth_session_id},
            params={"session_id": session_id},
        )

    def decide_reservation(
        self, auth_session_id: str, action_id: str, decision: str
    ) -> dict[str, Any]:
        return self._request(
            "POST",
            f"/api/admin/reservations/{action_id}/decision",
            headers={"X-Auth-Session": auth_session_id},
            json={"decision": decision},
        )

    def _request(
        self, method: str, path: str, *, allow_empty: bool = False, **kwargs: Any
    ) -> dict[str, Any]:
        try:
            response = httpx.request(
                method,
                f"{self._base_url}{path}",
                timeout=self._timeout,
                **kwargs,
            )
        except httpx.TimeoutException as error:
            raise AgentClientError(
                "응답 시간이 초과되었습니다. 잠시 후 다시 시도해 주세요.",
                kind="timeout",
            ) from error
        except httpx.RequestError as error:
            raise AgentClientError(
                "안내 서버에 연결할 수 없습니다. 서버 실행 상태를 확인해 주세요.",
                kind="connection",
            ) from error

        if not response.is_success:
            detail = None
            try:
                error_payload = response.json()
                if isinstance(error_payload, dict) and isinstance(error_payload.get("detail"), str):
                    detail = error_payload["detail"]
            except ValueError:
                pass
            raise AgentClientError(
                detail or f"안내 서버가 요청을 처리하지 못했습니다. (HTTP {response.status_code})",
                kind="http",
            )

        if allow_empty and not response.content:
            return {}
        try:
            payload = response.json()
        except ValueError as error:
            raise AgentClientError(
                "안내 서버의 응답 형식이 올바르지 않습니다.",
                kind="invalid_response",
            ) from error

        if not isinstance(payload, dict):
            raise AgentClientError(
                "안내 서버의 응답 형식이 올바르지 않습니다.",
                kind="invalid_response",
            )
        return payload
