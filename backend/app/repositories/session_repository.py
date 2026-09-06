"""대화 기록 저장소입니다. `conversation_messages` 공용 테이블을 사용합니다.

MVP는 로그인이 없으므로 게스트 `session_id`를 `user_id`로도 사용합니다. 로그인이
추가되면 `user_id`만 실제 사용자 ID로 바꿔 끼우면 됩니다.
"""

from uuid import uuid4

import psycopg

from app.core.config import settings


def append_message(session_id: str, role: str, content: str) -> None:
    with psycopg.connect(settings.database_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "INSERT INTO conversation_messages (id, user_id, session_id, role, content) VALUES (%s, %s, %s, %s, %s)",
            (str(uuid4()), session_id, session_id, role, content),
        )


def get_recent_messages(session_id: str, limit: int = 10) -> list[dict]:
    with psycopg.connect(settings.database_url, autocommit=True) as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT role, content FROM conversation_messages WHERE session_id = %s ORDER BY created_at DESC LIMIT %s",
            (session_id, limit),
        )
        rows = cur.fetchall()
    return [{"role": role, "content": content} for role, content in reversed(rows)]
