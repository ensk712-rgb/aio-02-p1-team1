"""SQLite 기반 최소 로그인 사용자 저장소."""

from __future__ import annotations

import hmac
import sqlite3
from pathlib import Path

from backend.app.core.config import DATA_DIR


class UserRepository:
    def __init__(self, db_path: Path | None = None) -> None:
        self._db_path = db_path or DATA_DIR / "zoo_auth.db"

    def initialize(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self._db_path) as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users ("
                "user_id TEXT PRIMARY KEY, password TEXT NOT NULL, "
                "role TEXT NOT NULL DEFAULT 'user')"
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()
            }
            if "role" not in columns:
                connection.execute(
                    "ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'user'"
                )
            connection.execute(
                "INSERT OR IGNORE INTO users(user_id, password, role) VALUES (?, ?, ?)",
                ("TEST", "1234", "user"),
            )
            connection.execute(
                "INSERT OR IGNORE INTO users(user_id, password, role) VALUES (?, ?, ?)",
                ("admin", "1234", "admin"),
            )

    def validate_credentials(self, user_id: str, password: str) -> bool:
        return self.authenticate(user_id, password) is not None

    def authenticate(self, user_id: str, password: str) -> dict[str, str] | None:
        with sqlite3.connect(self._db_path) as connection:
            row = connection.execute(
                "SELECT password, role FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None or not hmac.compare_digest(str(row[0]), password):
            return None
        return {"user_id": user_id, "role": str(row[1])}
