"""C2 확인 테스트: 운영 조회 Tool 3종 (최두나 소유)."""

from datetime import datetime
from zoneinfo import ZoneInfo

from backend.app.tools import zoo_tools

SEOUL = ZoneInfo("Asia/Seoul")
# 낮 12시: 해양관은 펭귄(11:00/14:30) + 물개(13:00/16:00) 두 일정이 섞여 있다.
NOON = datetime(2026, 9, 5, 12, 0, tzinfo=SEOUL)
# 13:30: 물개 13:00은 지났고, 펭귄 14:30만 다음 일정으로 남는 시각 (단일 동물 케이스 확인용)
AFTER_130 = datetime(2026, 9, 5, 13, 30, tzinfo=SEOUL)


# ---- get_feeding_schedule ----

def test_feeding_schedule_picks_nearest_upcoming_time_across_animals_in_habitat():
    # 정오에는 물개(13:00)가 펭귄(14:30)보다 먼저이므로 물개가 대표로 뽑혀야 한다
    result = zoo_tools.get_feeding_schedule("해양관", now=NOON)

    assert result.success is True
    assert result.data["habitat"] == "해양관"
    assert result.data["animal"] == "물개"
    assert result.data["next_feeding_at"].startswith("2026-09-05T13:00:00")
    assert result.data["as_of"] == NOON.isoformat()


def test_feeding_schedule_switches_to_next_animal_after_earlier_one_passes():
    result = zoo_tools.get_feeding_schedule("해양관", now=AFTER_130)

    assert result.success is True
    assert result.data["animal"] == "펭귄"
    assert result.data["next_feeding_at"].startswith("2026-09-05T14:30:00")


def test_feeding_schedule_normalizes_alias():
    result = zoo_tools.get_feeding_schedule("펭귄관", now=NOON)

    assert result.success is True
    assert result.data["habitat"] == "해양관"


def test_feeding_schedule_returns_none_when_all_times_passed_today():
    late = datetime(2026, 9, 5, 23, 0, tzinfo=SEOUL)
    result = zoo_tools.get_feeding_schedule("호랑이관", now=late)

    assert result.success is True
    assert result.data["next_feeding_at"] is None


def test_feeding_schedule_no_schedule_today_returns_null_not_guessed_time():
    result = zoo_tools.get_feeding_schedule("코끼리관", now=NOON)

    assert result.success is True
    assert result.data["next_feeding_at"] is None


def test_feeding_schedule_unknown_habitat_is_error():
    result = zoo_tools.get_feeding_schedule("사자관", now=NOON)

    assert result.success is False
    assert result.error.code == "HABITAT_NOT_FOUND"


# ---- check_closure_status ----

def test_closure_status_single_habitat():
    result = zoo_tools.check_closure_status("코끼리관", now=NOON)

    assert result.success is True
    assert result.data["items"] == [
        {"habitat": "코끼리관", "closed": True, "reason": "시설 점검으로 임시 휴장"}
    ]


def test_closure_status_all_habitats_when_none_given():
    result = zoo_tools.check_closure_status(None, now=NOON)

    assert result.success is True
    habitats = {item["habitat"] for item in result.data["items"]}
    assert habitats == {"정문", "호랑이관", "해양관", "코끼리관", "기린관"}


def test_closure_status_unknown_habitat_is_error():
    result = zoo_tools.check_closure_status("사자관", now=NOON)

    assert result.success is False
    assert result.error.code == "HABITAT_NOT_FOUND"


# ---- find_habitat_route ----

def test_route_known_pair():
    result = zoo_tools.find_habitat_route("정문", "해양관", now=NOON)

    assert result.success is True
    assert result.data["path"] == ["정문", "해양관"]
    assert result.data["estimated_minutes"] == 15


def test_route_reverse_direction_is_also_defined():
    result = zoo_tools.find_habitat_route("해양관", "정문", now=NOON)

    assert result.success is True
    assert result.data["estimated_minutes"] == 15


def test_route_alias_normalization():
    result = zoo_tools.find_habitat_route("정문", "호랑이사", now=NOON)

    assert result.success is True
    assert result.data["destination"] == "호랑이관"


def test_route_same_current_and_destination():
    result = zoo_tools.find_habitat_route("정문", "정문", now=NOON)

    assert result.success is True
    assert result.data["estimated_minutes"] == 0


def test_route_unknown_habitat_is_error():
    result = zoo_tools.find_habitat_route("정문", "사자관", now=NOON)

    assert result.success is False
    assert result.error.code == "HABITAT_NOT_FOUND"


def test_route_between_non_gate_habitats_when_defined():
    result = zoo_tools.find_habitat_route("호랑이관", "코끼리관", now=NOON)
    assert result.success is True
    assert result.data["estimated_minutes"] == 18


def test_route_between_known_habitats_without_defined_row_is_route_not_found():
    # 호랑이관<->기린관은 routes.json에 정의되지 않은 조합 (둘 다 등록된 시설이지만 경로 없음)
    result = zoo_tools.find_habitat_route("호랑이관", "기린관", now=NOON)

    assert result.success is False
    assert result.error.code == "ROUTE_NOT_FOUND"


def test_route_rejects_non_string_argument_strict_validation():
    # A-05: find_habitat_route(current=123, destination="해양관") 등 strict 타입 오류 차단
    result = zoo_tools.find_habitat_route(123, "해양관", now=NOON)  # type: ignore[arg-type]

    assert result.success is False
    assert result.error.code == "INVALID_ARGUMENT"


# ---- lookup_ticket_scope (P1, 작업지시서 v1.1 11.4절) ----

def test_ticket_scope_known_type_returns_included_and_excluded():
    result = zoo_tools.lookup_ticket_scope("일반권", now=NOON)

    assert result.success is True
    assert result.data["ticket_type"] == "일반권"
    assert result.data["included"] == ["호랑이관", "해양관", "코끼리관", "기린관"]
    assert result.data["excluded"] == ["체험 프로그램"]
    # 시간 기준 데이터가 아니므로 as_of는 계약에 포함하지 않는다.
    assert "as_of" not in result.data


def test_ticket_scope_alias_normalization():
    result = zoo_tools.lookup_ticket_scope("성인", now=NOON)

    assert result.success is True
    assert result.data["ticket_type"] == "일반권"


def test_ticket_scope_experience_program_excludes_exhibits():
    result = zoo_tools.lookup_ticket_scope("체험권", now=NOON)

    assert result.success is True
    assert result.data["ticket_type"] == "체험프로그램권"
    assert result.data["included"] == ["체험 프로그램"]
    assert "호랑이관" in result.data["excluded"]


def test_ticket_scope_unknown_type_is_error():
    result = zoo_tools.lookup_ticket_scope("무제한권", now=NOON)

    assert result.success is False
    assert result.error.code == "TICKET_TYPE_NOT_FOUND"


def test_ticket_scope_rejects_empty_string():
    result = zoo_tools.lookup_ticket_scope("", now=NOON)

    assert result.success is False
    assert result.error.code == "INVALID_ARGUMENT"


def test_ticket_scope_rejects_non_string_argument_strict_validation():
    result = zoo_tools.lookup_ticket_scope(123, now=NOON)  # type: ignore[arg-type]

    assert result.success is False
    assert result.error.code == "INVALID_ARGUMENT"
