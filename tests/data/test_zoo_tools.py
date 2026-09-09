"""C2 확인 테스트: 운영 조회 Tool 3종 (최두나 소유)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from backend.app.schemas.common import ToolRunResult
from backend.app.tools import zoo_tools

SEOUL = ZoneInfo("Asia/Seoul")
# 낮 12시: 해양관은 펭귄(11:00/14:30) + 물개(13:00/16:00) 두 일정이 섞여 있다.
NOON = datetime(2026, 9, 5, 12, 0, tzinfo=SEOUL)
# 13:30: 물개 13:00은 지났고, 펭귄 14:30만 다음 일정으로 남는 시각 (단일 동물 케이스 확인용)
AFTER_130 = datetime(2026, 9, 5, 13, 30, tzinfo=SEOUL)


@pytest.fixture(autouse=True)
def _reset_weather_cache():
    """lookup_public_weather의 TTL 캐시가 테스트 간에 새지 않도록 매 테스트 전에 비운다."""
    zoo_tools._reset_weather_cache_for_tests()
    yield
    zoo_tools._reset_weather_cache_for_tests()


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


# ---- lookup_public_weather ----
# 테스트는 실제 Open-Meteo API를 호출하지 않는다 — httpx.get을 가짜로 대체한다
# (P1-B 계획서 §10 "테스트는 실제 외부 API를 호출하지 않는다").


class _FakeWeatherResponse:
    def __init__(self, weather_code: int) -> None:
        self._weather_code = weather_code

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return {"current": {"weather_code": self._weather_code}}


def _fake_httpx_get(weather_code: int):
    def _get(url, *, params=None, timeout=None):
        return _FakeWeatherResponse(weather_code)

    return _get


def test_public_weather_maps_clear_code(monkeypatch):
    monkeypatch.setattr(zoo_tools.httpx, "get", _fake_httpx_get(0))

    result = zoo_tools.lookup_public_weather("서울", now=NOON)

    assert result.success is True
    assert result.data["region"] == "서울"
    assert result.data["condition"] == "clear"
    assert result.data["indoor_recommended"] is False
    assert result.data["as_of"] == NOON.isoformat()
    assert result.source == zoo_tools.OPEN_METEO_SOURCE


def test_public_weather_maps_cloudy_code(monkeypatch):
    monkeypatch.setattr(zoo_tools.httpx, "get", _fake_httpx_get(2))

    result = zoo_tools.lookup_public_weather("서울", now=NOON)

    assert result.data["condition"] == "cloudy"
    assert result.data["indoor_recommended"] is False


def test_public_weather_maps_rain_code_and_recommends_indoor(monkeypatch):
    monkeypatch.setattr(zoo_tools.httpx, "get", _fake_httpx_get(63))

    result = zoo_tools.lookup_public_weather("서울", now=NOON)

    assert result.data["condition"] == "rain"
    assert result.data["indoor_recommended"] is True


def test_public_weather_maps_storm_code_and_recommends_indoor(monkeypatch):
    monkeypatch.setattr(zoo_tools.httpx, "get", _fake_httpx_get(96))

    result = zoo_tools.lookup_public_weather("서울", now=NOON)

    assert result.data["condition"] == "storm"
    assert result.data["indoor_recommended"] is True


def test_public_weather_rejects_empty_string(monkeypatch):
    result = zoo_tools.lookup_public_weather("", now=NOON)

    assert result.success is False
    assert result.error.code == "INVALID_ARGUMENT"
    assert result.source == zoo_tools.OPEN_METEO_SOURCE


def test_public_weather_rejects_non_string_argument_strict_validation():
    result = zoo_tools.lookup_public_weather(123, now=NOON)  # type: ignore[arg-type]

    assert result.success is False
    assert result.error.code == "INVALID_ARGUMENT"
    assert result.source == zoo_tools.OPEN_METEO_SOURCE


def test_public_weather_unsupported_region_is_error(monkeypatch):
    result = zoo_tools.lookup_public_weather("부산", now=NOON)

    assert result.success is False
    assert result.error.code == "REGION_NOT_SUPPORTED"
    assert result.source == zoo_tools.OPEN_METEO_SOURCE


def test_public_weather_api_failure_is_error(monkeypatch):
    def _raise(url, *, params=None, timeout=None):
        raise zoo_tools.httpx.ConnectTimeout("timeout")

    monkeypatch.setattr(zoo_tools.httpx, "get", _raise)

    result = zoo_tools.lookup_public_weather("서울", now=NOON)

    assert result.success is False
    assert result.error.code == "WEATHER_LOOKUP_FAILED"
    assert result.source == zoo_tools.OPEN_METEO_SOURCE
    # 다른 Tool과 공유하는 mock source를 실패 시에도 잘못 붙이지 않는지 확인
    assert result.source != zoo_tools.SOURCE_NAME


def test_public_weather_ttl_cache_reuses_within_10_minutes(monkeypatch):
    call_count = {"n": 0}

    def _get(url, *, params=None, timeout=None):
        call_count["n"] += 1
        return _FakeWeatherResponse(0)  # clear

    monkeypatch.setattr(zoo_tools.httpx, "get", _get)

    first = zoo_tools.lookup_public_weather("서울", now=NOON)
    second = zoo_tools.lookup_public_weather(
        "서울", now=NOON + timedelta(minutes=9, seconds=59)
    )

    assert call_count["n"] == 1  # 두 번째 호출은 API를 다시 부르지 않는다
    assert first.data == second.data
    assert second.data["as_of"] == NOON.isoformat()  # 캐시된 데이터의 원래 조회 시각 유지
    assert second.retrieved_at == NOON + timedelta(minutes=9, seconds=59)


def test_public_weather_ttl_cache_expires_after_10_minutes(monkeypatch):
    call_count = {"n": 0}
    codes = [0, 63]  # clear -> rain

    def _get(url, *, params=None, timeout=None):
        code = codes[call_count["n"]]
        call_count["n"] += 1
        return _FakeWeatherResponse(code)

    monkeypatch.setattr(zoo_tools.httpx, "get", _get)

    first = zoo_tools.lookup_public_weather("서울", now=NOON)
    second = zoo_tools.lookup_public_weather("서울", now=NOON + timedelta(minutes=10, seconds=1))

    assert call_count["n"] == 2  # TTL 만료로 다시 호출됨(수동 갱신 없이 자동)
    assert first.data["condition"] == "clear"
    assert second.data["condition"] == "rain"
    assert second.data["as_of"] == (NOON + timedelta(minutes=10, seconds=1)).isoformat()


# ---- get_course_info / get_indoor_course_info / get_outdoor_course_info ----


def _mock_closed_habitats(monkeypatch, closed: set[str] = frozenset()):
    """closures.json 상태와 무관하게 지정한 시설만 휴장으로 강제한다.

    실제 closures.json은 코끼리관을 항상 휴장으로 등록해 두고 있어서, 계획서
    §6.3의 예시(코끼리관 포함, 총 115분)를 그대로 재현하려면 휴장 상태를
    모킹해야 한다. 그리디 알고리즘 자체를 검증하는 테스트에서만 쓴다.
    closed=set()(기본값)이면 전부 개장 상태다.
    """

    def _fake_check_closure_status(habitat=None, *, now=None):
        as_of = (now or NOON).isoformat()
        items = [{"habitat": name, "closed": True, "reason": "테스트"} for name in closed]
        return ToolRunResult(
            success=True,
            data={"items": items, "as_of": as_of},
            error=None,
            source=zoo_tools.SOURCE_NAME,
            retrieved_at=now or NOON,
        )

    monkeypatch.setattr(zoo_tools, "check_closure_status", _fake_check_closure_status)


def _all_habitats_open(monkeypatch):
    _mock_closed_habitats(monkeypatch, set())


def test_get_course_info_matches_plan_worked_example_when_nothing_closed(monkeypatch):
    """P1-B 계획서 §6.3 예시: 5살 아이·120분 → 해양관(40)→기린관(79)→코끼리관(115)."""
    _all_habitats_open(monkeypatch)

    result = zoo_tools.get_course_info(120, child_accompanying=True, now=NOON)

    assert result.success is True
    assert [s["habitat"] for s in result.data["stops"]] == ["해양관", "기린관", "코끼리관"]
    assert [s["cumulative_minutes"] for s in result.data["stops"]] == [40, 79, 115]
    assert result.data["total_minutes"] == 115
    assert result.data["remaining_minutes"] == 5
    assert result.data["facility_scope"] == "all"
    assert result.data["current"] == "정문"
    assert result.source == zoo_tools.SOURCE_NAME


def test_get_course_info_real_data_skips_permanently_closed_elephant():
    """실제 closures.json 그대로(코끼리관 상시 휴장, 기린관↔호랑이관 경로 없음)면
    3번째 후보(코끼리관)는 휴장으로, 4번째(호랑이관)는 경로 없음으로 각각
    건너뛰어 2개 시설만 남는다 — 그리디는 멈추지 않고 다음 후보로 계속 간다.
    """
    result = zoo_tools.get_course_info(120, child_accompanying=True, now=NOON)

    assert [s["habitat"] for s in result.data["stops"]] == ["해양관", "기린관"]
    assert result.data["total_minutes"] == 79
    assert result.data["remaining_minutes"] == 41


def test_get_course_info_returns_empty_stops_when_time_too_short():
    result = zoo_tools.get_course_info(5, now=NOON)

    assert result.success is True
    assert result.data["stops"] == []
    assert result.data["total_minutes"] == 0
    assert result.data["remaining_minutes"] == 5


def test_get_course_info_rejects_zero_available_minutes():
    result = zoo_tools.get_course_info(0, now=NOON)

    assert result.success is False
    assert result.error.code == "INVALID_ARGUMENT"


def test_get_course_info_unknown_current_habitat_is_error():
    result = zoo_tools.get_course_info(120, current="없는시설", now=NOON)

    assert result.success is False
    assert result.error.code == "HABITAT_NOT_FOUND"


def test_get_indoor_course_info_only_visits_indoor_habitats():
    # 실제 데이터는 indoor=true인 시설이 해양관 하나뿐이다.
    result = zoo_tools.get_indoor_course_info(120, now=NOON)

    assert result.data["facility_scope"] == "indoor_only"
    assert [s["habitat"] for s in result.data["stops"]] == ["해양관"]


def test_get_indoor_course_info_empty_when_no_time_for_any_indoor_habitat():
    result = zoo_tools.get_indoor_course_info(10, now=NOON)

    assert result.data["stops"] == []


def test_get_outdoor_course_info_only_visits_outdoor_habitats():
    # 실제 데이터: 코끼리관은 휴장, 기린관↔호랑이관 경로가 없어 기린관만 채택된다.
    result = zoo_tools.get_outdoor_course_info(120, now=NOON)

    assert result.data["facility_scope"] == "outdoor_only"
    assert [s["habitat"] for s in result.data["stops"]] == ["기린관"]
    for stop in result.data["stops"]:
        profile = zoo_tools.get_course_profile(stop["habitat"])
        assert profile["indoor"] is False


def test_get_outdoor_course_info_empty_when_no_time_for_any_outdoor_habitat():
    result = zoo_tools.get_outdoor_course_info(5, now=NOON)

    assert result.data["stops"] == []


def test_course_tools_share_planner_rules_via_facility_scope(monkeypatch):
    """세 Tool이 같은 _recommend_course()를 공유하는지 확인 — facility_scope만
    다르게 줘도 나머지 규칙(휴장 제외, 시간 계산)이 동일하게 적용돼야 한다.
    """
    _all_habitats_open(monkeypatch)

    all_result = zoo_tools.get_course_info(120, child_accompanying=True, now=NOON)
    indoor_result = zoo_tools.get_indoor_course_info(120, child_accompanying=True, now=NOON)
    outdoor_result = zoo_tools.get_outdoor_course_info(120, child_accompanying=True, now=NOON)

    assert all_result.data["facility_scope"] == "all"
    assert indoor_result.data["facility_scope"] == "indoor_only"
    assert outdoor_result.data["facility_scope"] == "outdoor_only"
    assert all(s["habitat"] in {"해양관"} for s in indoor_result.data["stops"])
    assert all(s["habitat"] != "해양관" for s in outdoor_result.data["stops"])


def test_closing_a_middle_stop_finds_a_substitute_not_just_a_gap(monkeypatch):
    """§10: "코끼리관이 휴장이면 대체 조합을 반환한다"를 실제로 대체가 일어나는
    경우로 검증한다(기존 실제 데이터 테스트는 대체 없이 그냥 빠지기만 했다).
    기린관만 휴장시키면: 해양관(40) 다음 기린관은 휴장으로 건너뛰고, 코끼리관은
    해양관↔코끼리관 경로가 없어 건너뛰고, 호랑이관이 대신 채택돼야 한다.
    """
    _mock_closed_habitats(monkeypatch, {"기린관"})

    result = zoo_tools.get_course_info(120, child_accompanying=True, now=NOON)

    assert [s["habitat"] for s in result.data["stops"]] == ["해양관", "호랑이관"]
    assert result.data["total_minutes"] == 40 + 20 + 15  # 해양관(15+25) + 호랑이관(20+15)


def test_greedy_follows_course_profiles_declaration_order(monkeypatch):
    """§10: "그리디는 선언 순서를 따른다" — course_profiles.json의 순서를
    바꾸면 결과 순서도 그대로 바뀌어야 한다(정렬하지 않는다, §6.1)."""
    _all_habitats_open(monkeypatch)
    original_load_json = zoo_tools._load_json

    def _reordered_load_json(relative_path):
        payload = original_load_json(relative_path)
        if relative_path == "operations/course_profiles.json":
            payload = {"profiles": list(reversed(payload["profiles"]))}
        return payload

    monkeypatch.setattr(zoo_tools, "_load_json", _reordered_load_json)

    result = zoo_tools.get_course_info(120, child_accompanying=True, now=NOON)

    # 원래 순서(해양관, 기린관, 코끼리관, 호랑이관)를 뒤집으면 child_friendly
    # 후보 순회 순서도 코끼리관, 기린관, 해양관으로 바뀐다.
    assert [s["habitat"] for s in result.data["stops"]][0] == "코끼리관"


def test_child_accompanying_prioritizes_child_friendly_habitat(monkeypatch):
    """§10: "아이 동반 우선순위" — 실제 course_profiles.json은 child_friendly
    시설이 이미 선언 순서상 먼저라 True/False 차이가 우연히 안 드러나므로,
    일부러 순서를 뒤집은 2개짜리 후보 목록으로 우선순위 재정렬 자체를 검증한다.
    """
    _all_habitats_open(monkeypatch)
    original_load_json = zoo_tools._load_json

    def _fake_load_json(relative_path):
        if relative_path == "operations/course_profiles.json":
            return {
                "profiles": [
                    {
                        "habitat": "호랑이관",
                        "visit_minutes": 15,
                        "child_friendly": False,
                        "indoor": False,
                    },
                    {
                        "habitat": "기린관",
                        "visit_minutes": 20,
                        "child_friendly": True,
                        "indoor": False,
                    },
                ]
            }
        return original_load_json(relative_path)

    monkeypatch.setattr(zoo_tools, "_load_json", _fake_load_json)

    # 정문→호랑이관(10+15=25) 또는 정문→기린관(8+20=28) 중 하나만 들어가는 예산.
    # 호랑이관↔기린관 경로가 없어 두 번째 정류지는 어차피 못 들어간다.
    without_child = zoo_tools.get_course_info(28, child_accompanying=False, now=NOON)
    with_child = zoo_tools.get_course_info(28, child_accompanying=True, now=NOON)

    assert [s["habitat"] for s in without_child.data["stops"]] == ["호랑이관"]
    assert [s["habitat"] for s in with_child.data["stops"]] == ["기린관"]
