"""C2/C4 확인 테스트: 동물 카드 키워드 RAG (최두나 소유).

대표 질문 5개로 튜닝한 결과를 기록한다 (작업지시서 v1.1 4.3.4절).
- 4개는 실제 매치되어야 하고(score >= RAG_MIN_SCORE=0.5), 1개는 카드가 없어
  매치되지 않아야 한다 (근거 없음 안내로 이어지는 실패 예).
"""

import pytest

from backend.app.services import rag_service

REPRESENTATIVE_MATCHING_QUERIES = [
    ("호랑이는 어디에서 살고 무엇을 먹어?", "ANIMAL-TIGER"),
    ("펭귄은 무엇을 먹어?", "ANIMAL-PENGUIN"),
    ("코끼리는 무엇을 먹어?", "ANIMAL-ELEPHANT"),
    ("기린은 무엇을 먹어?", "ANIMAL-GIRAFFE"),
]


@pytest.mark.parametrize("query,expected_doc_id", REPRESENTATIVE_MATCHING_QUERIES)
def test_representative_question_matches_expected_card(query, expected_doc_id):
    result = rag_service.retrieve_animal_info(query)

    assert result.success is True
    assert result.data["matched"] is True
    top_chunk = result.data["chunks"][0]
    assert top_chunk["doc_id"] == expected_doc_id
    assert top_chunk["score"] >= 0.5


def test_representative_failure_example_unregistered_animal_has_no_card():
    # 5번째 대표 질문(실패 예): 카드가 없는 동물 -> 확인 불가로 이어져야 함
    # (참고: "사자"는 이후 데이터셋에 ANIMAL-LION 카드가 추가되어 더 이상
    #  실패 예로 쓸 수 없다. 카드가 없는 "유니콘"으로 대체한다.)
    result = rag_service.retrieve_animal_info("유니콘은 어디서 살아?")

    assert result.success is True
    assert result.data["matched"] is False
    assert result.data["chunks"] == []


def test_below_threshold_chunks_are_excluded_from_evidence():
    # 카드에 없는 정보(나이/이송 이력)를 묻는 질문 -> 근거로 채택되면 안 됨
    result = rag_service.retrieve_animal_info("이 호랑이는 몇 살이고 어디서 왔어?")

    for chunk in result.data["chunks"]:
        assert chunk["score"] >= 0.5  # 임계값 미만은 애초에 포함되지 않아야 함


def test_empty_query_does_not_match_anything():
    result = rag_service.retrieve_animal_info("")

    assert result.success is True
    assert result.data["matched"] is False
    assert result.data["chunks"] == []


def test_tie_break_is_doc_id_ascending():
    chunks = rag_service.retrieve_chunks("먹이", top_k=4)
    scores = [c.score for c in chunks]
    # 동점 구간에서 doc_id가 오름차순인지 확인
    tied_groups: dict[float, list[str]] = {}
    for chunk in chunks:
        tied_groups.setdefault(chunk.score, []).append(chunk.doc_id)
    for doc_ids in tied_groups.values():
        assert doc_ids == sorted(doc_ids)
