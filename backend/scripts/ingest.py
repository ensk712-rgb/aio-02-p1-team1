"""`data/`의 문서 3종을 chunk·임베딩해 pgvector `documents` 테이블에 색인합니다.

실행 (backend/ 디렉토리에서):
    python scripts/ingest.py
"""

import sys
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_BACKEND_DIR))

from app.repositories import document_repository  # noqa: E402
from app.services import rag_service  # noqa: E402

DATA_DIR = _BACKEND_DIR.parent / "data"

DOCS = [
    ("animal_card_tiger.md", "동물 정보카드"),
    ("habitat_marine.md", "서식지 설명"),
    ("faq.md", "FAQ"),
]


def main() -> None:
    cleared = document_repository.clear_collection()
    print(f"기존 색인 {cleared}건 삭제")

    total = 0
    for filename, doc_type in DOCS:
        path = DATA_DIR / filename
        text = path.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()

        chunks = rag_service.chunk_document(text, title=title, source=filename)
        for chunk in chunks:
            chunk.metadata["doc_type"] = doc_type

        count = rag_service.embed_and_store(chunks)
        print(f"{filename}: {count}개 chunk 색인")
        total += count

    print(f"총 {total}개 chunk 색인 완료 (collection={document_repository.settings.ranger_collection})")


if __name__ == "__main__":
    main()
