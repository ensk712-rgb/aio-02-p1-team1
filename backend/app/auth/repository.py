"""SQLite 사용자 저장소와 PBKDF2 비밀번호 검증."""

import hashlib
import hmac
import os
import sqlite3
from pathlib import Path

_TEST_USER_ID = "TEST"
_TEST_SALT = "4a8f1d2c7390b5e6a1d4c8f29b734e55"
_TEST_PASSWORD_HASH = "2a5e1ee637b24f1012a16769fd21268b1bc0dc83062d865e234fc37c141eeff6"
_ITERATIONS = 210_000


class UserRepository:
    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS users (id TEXT PRIMARY KEY, password_salt TEXT NOT NULL, password_hash TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT OR IGNORE INTO users(id, password_salt, password_hash) VALUES (?, ?, ?)",
                (_TEST_USER_ID, _TEST_SALT, _TEST_PASSWORD_HASH),
            )

    def authenticate(self, user_id: str, password: str) -> bool:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT password_salt, password_hash FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if row is None:
            self._dummy_verify(password)
            return False
        salt, stored_hash = row
        candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), _ITERATIONS).hex()
        return hmac.compare_digest(candidate, stored_hash)

    @staticmethod
    def _dummy_verify(password: str) -> None:
        hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(_TEST_SALT), _ITERATIONS)


def default_repository() -> UserRepository:
    default_path = Path(__file__).resolve().parents[2] / ".data" / "auth.sqlite3"
    return UserRepository(os.getenv("AUTH_DATABASE_PATH", str(default_path)))
