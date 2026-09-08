"""data/animal_cards/*.json을 읽어 Postgres(pgvector)에 적재한다.

1회 실행 스크립트다. 카드 파일이 바뀌면 다시 실행한다 (doc_id 기준 upsert).
실행 전 STORAGE_MODE=persistent, DATABASE_URL, OPENAI_API_KEY가 설정돼 있어야 한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import get_settings
from backend.app.core.db import ensure_schema
from backend.app.repositories.document_repository import insert_chunks
from backend.app.schemas.tools import ChunkInput


def _load_cards() -> list[ChunkInput]:
    cards_dir = PROJECT_ROOT / "data" / "animal_cards"
    chunks: list[ChunkInput] = []
    for path in sorted(cards_dir.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            card = json.load(f)
        chunks.append(
            ChunkInput(
                doc_id=card["doc_id"],
                collection=card["collection"],
                title=card["title"],
                page=card.get("page"),
                text=card["text"],
                keywords=card.get("keywords", []),
            )
        )
    return chunks


def main() -> None:
    settings = get_settings()
    if settings.STORAGE_MODE != "persistent":
        raise SystemExit("STORAGE_MODE=persistent로 설정한 뒤 실행하세요.")

    ensure_schema()
    chunks = _load_cards()
    insert_chunks(chunks)
    print(f"{len(chunks)}개 동물 정보카드를 적재했습니다.")


if __name__ == "__main__":
    main()
