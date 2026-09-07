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
                "user_id TEXT PRIMARY KEY, password TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO users(user_id, password) VALUES (?, ?)",
                ("TEST", "1234"),
            )

    def validate_credentials(self, user_id: str, password: str) -> bool:
        with sqlite3.connect(self._db_path) as connection:
            row = connection.execute(
                "SELECT password FROM users WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        return row is not None and hmac.compare_digest(str(row[0]), password)
