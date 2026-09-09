"""날씨 선조회 + 동적 Allowlist 좁히기(P1-B 계획서 §6.2)를 검증한다."""

import asyncio
from datetime import datetime, timezone

from backend.app.agents.models import AgentProfile, AgentToolPolicy
from backend.app.agents.registry import get_agent_profile
from backend.app.schemas.common import ToolError, ToolRunResult
from backend.app.tools import course_weather_policy
from backend.app.tools.course_weather_policy import (
    narrow_course_tools_by_weather,
    recommend_course_with_weather,
)

NOW = datetime(2026, 9, 5, 12, 0, tzinfo=timezone.utc)


def _weather_result(*, success: bool, condition: str | None = None) -> ToolRunResult:
    if not success:
        return ToolRunResult(
            success=False,
            data={},
            error=ToolError(code="WEATHER_LOOKUP_FAILED", message="실패"),
            source="open_meteo_forecast",
            retrieved_at=NOW,
        )
    return ToolRunResult(
        success=True,
        data={
            "region": "서울",
            "condition": condition,
            "indoor_recommended": condition in {"rain", "storm"},
            "as_of": NOW.isoformat(),
        },
        error=None,
        source="open_meteo_forecast",
        retrieved_at=NOW,
    )


def _tool_names(profile: AgentProfile) -> set[str]:
    return {policy.name for policy in profile.allowed_tools}


def test_narrowing_skips_profiles_without_both_course_tools(monkeypatch):
    """코스 Tool 두 개 중 하나라도 없는 Profile은 건드리지 않는다(다른 Agent 보호)."""

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("두 Tool이 없는 Profile에서는 날씨를 조회하면 안 된다")

    monkeypatch.setattr(course_weather_policy, "lookup_public_weather", _should_not_be_called)

    minimal_profile = AgentProfile(
        agent_id="other_agent",
        name="다른 Agent",
        goal="목표",
        description="설명",
        instructions="지침",
        allowed_tools=(
            AgentToolPolicy(name="get_course_info", risk="read", description="설명"),
        ),
    )

    result = asyncio.run(narrow_course_tools_by_weather(minimal_profile, now=NOW))

    assert result.applied is False
    assert result.weather is None
    assert result.profile is minimal_profile


def test_narrowing_keeps_only_indoor_tool_when_raining(monkeypatch):
    monkeypatch.setattr(
        course_weather_policy,
        "lookup_public_weather",
        lambda region, *, now=None: _weather_result(success=True, condition="rain"),
    )

    result = asyncio.run(narrow_course_tools_by_weather(get_agent_profile("zoo_guide"), now=NOW))

    assert result.applied is True
    names = _tool_names(result.profile)
    assert "get_indoor_course_info" in names
    assert "get_course_info" not in names
    # 실외 전용 Tool은 날씨와 무관하게 항상 남는다(계획서 §5.0)
    assert "get_outdoor_course_info" in names


def test_narrowing_keeps_only_all_weather_tool_when_clear(monkeypatch):
    monkeypatch.setattr(
        course_weather_policy,
        "lookup_public_weather",
        lambda region, *, now=None: _weather_result(success=True, condition="clear"),
    )

    result = asyncio.run(narrow_course_tools_by_weather(get_agent_profile("zoo_guide"), now=NOW))

    names = _tool_names(result.profile)
    assert "get_course_info" in names
    assert "get_indoor_course_info" not in names


def test_narrowing_defaults_to_all_weather_tool_when_lookup_fails(monkeypatch):
    """날씨 조회 실패 시 안전한 기본 동작: 더 넓은 옵션(get_course_info)을 남긴다."""
    monkeypatch.setattr(
        course_weather_policy,
        "lookup_public_weather",
        lambda region, *, now=None: _weather_result(success=False),
    )

    result = asyncio.run(narrow_course_tools_by_weather(get_agent_profile("zoo_guide"), now=NOW))

    names = _tool_names(result.profile)
    assert "get_course_info" in names
    assert "get_indoor_course_info" not in names
    assert result.weather is not None
    assert result.weather.success is False


def test_narrowing_calls_weather_lookup_with_fixed_seoul_region(monkeypatch):
    """region은 current(시설명)가 아니라 고정 지역명 '서울'이어야 한다."""
    seen_regions: list[str] = []

    def _fake(region: str, *, now=None):
        seen_regions.append(region)
        return _weather_result(success=True, condition="clear")

    monkeypatch.setattr(course_weather_policy, "lookup_public_weather", _fake)

    asyncio.run(narrow_course_tools_by_weather(get_agent_profile("zoo_guide"), now=NOW))

    assert seen_regions == [course_weather_policy.WEATHER_REGION]
    assert course_weather_policy.WEATHER_REGION == "서울"


def test_narrowing_does_not_mutate_original_profile(monkeypatch):
    """원본 Profile 객체는 그대로 유지돼야 한다(model_copy로 새 객체만 반환)."""
    monkeypatch.setattr(
        course_weather_policy,
        "lookup_public_weather",
        lambda region, *, now=None: _weather_result(success=True, condition="rain"),
    )

    original = get_agent_profile("zoo_guide")
    original_tool_count = len(original.allowed_tools)

    result = asyncio.run(narrow_course_tools_by_weather(original, now=NOW))

    assert len(original.allowed_tools) == original_tool_count
    assert "get_course_info" in _tool_names(original)
    assert result.profile is not original


def test_recommend_course_with_weather_marks_lookup_succeeded(monkeypatch):
    """날씨 조회가 성공하면 data.weather_lookup_succeeded=True를 함께 반환한다.

    §11.4 화면(route_recommendation.py, 14단계)이 "날씨가 맑아서
    get_course_info가 선택됨"과 "조회 실패로 기본값 get_course_info가
    선택됨"을 facility_scope만으로는 구분할 수 없어 이 값이 필요하다.
    """
    monkeypatch.setattr(
        course_weather_policy,
        "lookup_public_weather",
        lambda region, *, now=None: _weather_result(success=True, condition="clear"),
    )

    result = asyncio.run(
        recommend_course_with_weather(available_minutes=120, now=NOW)
    )

    assert result.success is True
    assert result.data["weather_lookup_succeeded"] is True
    # 원래 코스 데이터(facility_scope 등)는 그대로 유지돼야 한다
    assert result.data["facility_scope"] == "all"


def test_recommend_course_with_weather_marks_lookup_failed_but_still_returns_course(
    monkeypatch,
):
    """날씨 조회가 실패해도 안전한 기본값(get_course_info)으로 코스는 정상 반환하되,
    weather_lookup_succeeded=False로 표시해 화면이 실패 안내를 띄울 수 있게 한다.
    """
    monkeypatch.setattr(
        course_weather_policy,
        "lookup_public_weather",
        lambda region, *, now=None: _weather_result(success=False),
    )

    result = asyncio.run(
        recommend_course_with_weather(available_minutes=120, now=NOW)
    )

    assert result.success is True
    assert result.data["weather_lookup_succeeded"] is False
    assert result.data["facility_scope"] == "all"
