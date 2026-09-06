"""Streamlit에서 사용하는 동기 Backend HTTP Client."""

import os
from typing import Any

import httpx


class AgentClientError(RuntimeError):
    """사용자 화면에 안전한 Backend 연결 오류."""


class AgentClient:
    def __init__(self, base_url: str | None = None, *, timeout_seconds: float | None = None) -> None:
        self.base_url = (base_url or os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000")).rstrip("/")
        self.timeout_seconds = timeout_seconds or float(os.getenv("REQUEST_TIMEOUT_SECONDS", "60"))

    def ask(self, message: str, session_id: str | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {"message": message}
        if session_id is not None:
            payload["session_id"] = session_id
        return self._request("POST", "/api/agent/ask", json=payload)

    def login(self, user_id: str, password: str) -> dict[str, Any]:
        """비밀번호를 보관하거나 오류 메시지에 포함하지 않고 인증합니다."""
        return self._request(
            "POST",
            "/api/auth/login",
            json={"user_id": user_id, "password": password},
        )

    def get_health(self) -> dict[str, Any]:
        return self._request("GET", "/api/health")

    def _request(self, method: str, path: str, **kwargs: Any) -> dict[str, Any]:
        try:
            response = httpx.request(method, f"{self.base_url}{path}", timeout=self.timeout_seconds, **kwargs)
            response.raise_for_status()
            payload = response.json()
        except httpx.HTTPStatusError as error:
            raise AgentClientError(f"백엔드 요청 처리에 실패했습니다. (HTTP {error.response.status_code})") from error
        except (httpx.RequestError, ValueError) as error:
            raise AgentClientError("백엔드에 연결할 수 없습니다. 서버 상태를 확인해 주세요.") from error
        if not isinstance(payload, dict):
            raise AgentClientError("백엔드 응답 형식이 올바르지 않습니다.")
        return payload
