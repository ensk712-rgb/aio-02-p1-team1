"""`data/animal_cards/*.json`을 이미 구현된 `document_repository.insert_chunks`로 적재한다.

설계서(docs/superpowers/specs/2026-09-08-pgvector-redis-migration-design.md) 4.3절의
시딩 스크립트다. 스키마 생성·임베딩·upsert는 전부 앱 코드
(`backend/app/core/db.py`, `backend/app/repositories/document_repository.py`,
`backend/app/services/embedding_service.py`)가 담당하고, 여기서는 JSON을 읽어
`ChunkInput`으로 변환해 넘기기만 한다.

필요 환경변수 (.env):
- DATABASE_URL   예) postgresql://zoo:zoo@127.0.0.1:5432/zoo
- OPENAI_API_KEY
- STORAGE_MODE=persistent (이 스크립트 실행 중에만 필요하면 아래처럼 강제로 맞춘다)

실행 (backend/ 디렉토리에서):
    python scripts/seed_animal_cards.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _BACKEND_DIR.parent
sys.path.insert(0, str(_BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(_BACKEND_DIR / ".env")
# document_repository.insert_chunks는 STORAGE_MODE=persistent일 때 db.py의
# 커넥션 풀을 통해 실제 pgvector에 쓴다. 이 스크립트는 시딩이 목적이므로
# .env의 STORAGE_MODE 값과 무관하게 이 프로세스 안에서만 persistent로 강제한다.
os.environ["STORAGE_MODE"] = "persistent"

from backend.app.core.db import ensure_schema  # noqa: E402
from backend.app.repositories.document_repository import insert_chunks  # noqa: E402
from backend.app.schemas.tools import ChunkInput  # noqa: E402

DATA_DIR = _PROJECT_ROOT / "data"
CARDS_DIR = DATA_DIR / "animal_cards"


def load_chunks() -> list[ChunkInput]:
    chunks = []
    for path in sorted(CARDS_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            card = json.load(f)
        chunks.append(
            ChunkInput(
                doc_id=card["doc_id"],
                collection=card["collection"],
                title=card["title"],
                page=card.get("page"),
                text=card["text"],
                keywords=card["keywords"],
            )
        )
    return chunks


def main() -> None:
    if not os.environ.get("DATABASE_URL"):
        raise SystemExit("DATABASE_URL이 설정되지 않았습니다 (.env 확인).")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY가 설정되지 않았습니다 (.env 확인).")

    ensure_schema()

    chunks = load_chunks()
    print(f"data/animal_cards/*.json {len(chunks)}건 로드")

    insert_chunks(chunks)
    print(f"적재 완료: insert_chunks로 {len(chunks)}건 upsert")


if __name__ == "__main__":
    main()
