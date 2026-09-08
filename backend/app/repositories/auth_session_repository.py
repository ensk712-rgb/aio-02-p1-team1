"""JWT 없이 사용하는 로컬 인메모리 로그인 세션 저장소."""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from threading import Lock


class AuthSessionRepository:
    def __init__(self, ttl_seconds: int = 7200) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._sessions: dict[str, tuple[str, str, datetime]] = {}
        self._lock = Lock()

    def create(self, user_id: str, role: str = "user") -> str:
        session_id = f"auth-{secrets.token_urlsafe(24)}"
        with self._lock:
            self._sessions[session_id] = (
                user_id,
                role,
                datetime.now(timezone.utc) + self._ttl,
            )
        return session_id

    def get_user_id(self, session_id: str | None) -> str | None:
        if not session_id:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            user_id, _, expires_at = record
            if expires_at <= now:
                self._sessions.pop(session_id, None)
                return None
            return user_id

    def get_role(self, session_id: str | None) -> str | None:
        if not session_id:
            return None
        now = datetime.now(timezone.utc)
        with self._lock:
            record = self._sessions.get(session_id)
            if record is None:
                return None
            _, role, expires_at = record
            if expires_at <= now:
                self._sessions.pop(session_id, None)
                return None
            return role

    def is_admin(self, session_id: str | None) -> bool:
        return self.get_role(session_id) == "admin"

    def delete(self, session_id: str | None) -> None:
        if not session_id:
            return
        with self._lock:
            self._sessions.pop(session_id, None)
