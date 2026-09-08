"""C1 확인 테스트: Settings 로딩과 데이터 경로/형식 검증 (최두나 소유).

작업지시서 v1.1 8.2절 C1 확인 방법: "전원 같은 Python 버전, 다른 현재 디렉토리에서도
경로 로딩 정상"을 재현하기 위해 os.chdir로 작업 디렉토리를 바꾼 뒤에도
PROJECT_ROOT/DATA_DIR이 절대경로로 정상 계산되는지 확인한다.
"""

import json
import os

import pytest

from backend.app.core.config import Settings, get_settings


@pytest.fixture(autouse=True)
def _restore_cwd():
    original = os.getcwd()
    yield
    os.chdir(original)


def test_settings_defaults_match_contract():
    settings = Settings(_env_file=None)  # .env 무시하고 순수 기본값만 확인

    assert settings.APP_MODE == "mock"
    assert settings.STORAGE_MODE == "memory"
    assert settings.RAG_TOP_K == 3
    assert settings.RAG_MIN_SCORE == 0.5
    assert settings.MAX_AGENT_STEPS == 6
    assert settings.MAX_SAME_TOOL_CALLS == 2
    assert settings.MAX_TOOL_CALLS == 8
    assert settings.RUN_TIMEOUT_SECONDS == 90
    assert settings.MCP_TIMEOUT_SECONDS == 10
    assert settings.MCP_RETRY_COUNT == 1
    assert settings.PENDING_TTL_SECONDS == 120
    assert settings.SESSION_TTL_SECONDS == 7200


def test_project_root_and_data_dir_are_absolute_regardless_of_cwd(tmp_path):
    os.chdir(tmp_path)  # 다른 현재 디렉토리에서 실행해도 경로가 깨지지 않아야 한다
    settings = Settings(_env_file=None)  # 캐시를 우회한 새 인스턴스

    assert settings.project_root.is_absolute()
    assert settings.data_dir.is_absolute()
    assert settings.data_dir == settings.project_root / "data"
    assert (settings.data_dir / "animal_cards").is_dir()
    assert (settings.data_dir / "operations").is_dir()


def test_demo_now_parses_to_timezone_aware_datetime():
    settings = Settings(_env_file=None, DEMO_NOW="2026-09-05T13:00:00+09:00")
    parsed = settings.demo_now_datetime()

    assert parsed is not None
    assert parsed.tzinfo is not None
    assert parsed.isoformat() == "2026-09-05T13:00:00+09:00"


def test_demo_now_empty_returns_none():
    settings = Settings(_env_file=None, DEMO_NOW="")
    assert settings.demo_now_datetime() is None


ANIMAL_CARD_FILES = ["tiger.json", "penguin.json", "elephant.json", "giraffe.json"]
REQUIRED_CARD_FIELDS = {"doc_id", "title", "collection", "page", "text", "keywords"}


@pytest.mark.parametrize("filename", ANIMAL_CARD_FILES)
def test_animal_card_has_required_fields(filename):
    settings = Settings(_env_file=None)
    path = settings.data_dir / "animal_cards" / filename
    card = json.loads(path.read_text(encoding="utf-8"))

    assert REQUIRED_CARD_FIELDS.issubset(card.keys())
    assert card["collection"] == "animal_cards"
    assert isinstance(card["keywords"], list) and len(card["keywords"]) > 0
    assert len(card["text"]) > 0


def test_animal_cards_have_unique_doc_ids():
    settings = Settings(_env_file=None)
    doc_ids = []
    for filename in ANIMAL_CARD_FILES:
        path = settings.data_dir / "animal_cards" / filename
        card = json.loads(path.read_text(encoding="utf-8"))
        doc_ids.append(card["doc_id"])

    assert len(doc_ids) == len(set(doc_ids))


def test_habitats_json_defines_canonical_names_and_aliases():
    settings = Settings(_env_file=None)
    path = settings.data_dir / "operations" / "habitats.json"
    payload = json.loads(path.read_text(encoding="utf-8"))

    names = {h["name"] for h in payload["habitats"]}
    assert names == {"정문", "호랑이관", "해양관", "코끼리관", "기린관"}
    for habitat in payload["habitats"]:
        assert habitat["name"] in habitat["aliases"]


def test_routes_json_has_reverse_route_for_every_route():
    settings = Settings(_env_file=None)
    path = settings.data_dir / "operations" / "routes.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    pairs = {(r["current"], r["destination"]) for r in payload["routes"]}

    for current, destination in pairs:
        assert (destination, current) in pairs, f"{destination}->{current} 역방향 경로 누락"


def test_closures_json_lists_all_habitats():
    settings = Settings(_env_file=None)
    path = settings.data_dir / "operations" / "closures.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    names = {c["habitat"] for c in payload["closures"]}

    assert names == {"정문", "호랑이관", "해양관", "코끼리관", "기린관"}


def test_feeding_json_covers_all_habitats():
    settings = Settings(_env_file=None)
    path = settings.data_dir / "operations" / "feeding.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    habitats = {s["habitat"] for s in payload["schedules"]}

    assert habitats == {"정문", "호랑이관", "해양관", "코끼리관", "기린관"} - {"정문"}


def test_storage_and_persistence_defaults() -> None:
    settings = Settings(_env_file=None)
    assert settings.STORAGE_MODE == "memory"
    assert settings.DATABASE_URL == ""
    assert settings.REDIS_URL == ""
    assert settings.SESSION_MEMORY_MAX_TURNS == 6
    assert settings.EMBEDDING_MODEL == "text-embedding-3-small"
    assert settings.EMBEDDING_RETRY_COUNT == 1
