import json
from pathlib import Path

from backend.app.core.config import DATA_DIR


def _load(relative_path: str) -> dict:
    with (DATA_DIR / relative_path).open(encoding="utf-8") as f:
        return json.load(f)


def test_course_profile_habitats_are_registered_habitats():
    """course_profiles.json의 모든 habitat이 habitats.json에 등록되어 있어야 한다."""
    profiles = _load("operations/course_profiles.json")["profiles"]
    habitats = {h["name"] for h in _load("operations/habitats.json")["habitats"]}

    for row in profiles:
        assert row["habitat"] in habitats, f"등록되지 않은 시설: {row['habitat']}"


def test_course_profile_excludes_entrance():
    """정문은 출발점 전용이므로 코스 프로필에 포함하지 않는다."""
    profiles = _load("operations/course_profiles.json")["profiles"]
    assert all(row["habitat"] != "정문" for row in profiles)


def test_course_profile_visit_minutes_are_positive():
    profiles = _load("operations/course_profiles.json")["profiles"]
    assert all(row["visit_minutes"] > 0 for row in profiles)


def test_course_profile_has_no_duplicate_habitat():
    profiles = _load("operations/course_profiles.json")["profiles"]
    names = [row["habitat"] for row in profiles]
    assert len(names) == len(set(names))
