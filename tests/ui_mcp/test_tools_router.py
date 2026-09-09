"""GET /api/tools/* Router(P1-B 계획서 §11.4)의 HTTP 계약을 검증한다."""

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.tools_router import create_tools_router
from backend.app.schemas.common import ToolRunResult
from backend.app.tools import course_weather_policy


@pytest.fixture(autouse=True)
def _fake_weather_lookup(monkeypatch: pytest.MonkeyPatch):
    """실제 Open-Meteo API를 타지 않도록 기본값(맑음)으로 가짜 처리한다.

    scope=all/indoor_only/outdoor_only를 명시하는 테스트는 이 값이 안 쓰이는지도
    함께 확인한다.
    """

    def _fake(region: str, *, now=None):
        as_of = now or datetime.now(timezone.utc)
        return ToolRunResult(
            success=True,
            data={
                "region": region,
                "condition": "clear",
                "indoor_recommended": False,
                "as_of": as_of.isoformat(),
            },
            error=None,
            source="open_meteo_forecast",
            retrieved_at=as_of,
        )

    monkeypatch.setattr(course_weather_policy, "lookup_public_weather", _fake)


@pytest.fixture()
def client() -> TestClient:
    app = FastAPI()
    app.include_router(create_tools_router())
    return TestClient(app)


def test_habitat_route_returns_tool_run_result_json(client: TestClient) -> None:
    response = client.get(
        "/api/tools/habitat-route",
        params={"current": "정문", "destination": "해양관"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["path"] == ["정문", "해양관"]
    assert body["data"]["estimated_minutes"] == 15
    assert body["source"] == "mock_zoo_operations"


def test_habitat_route_unknown_habitat_is_200_with_success_false(client: TestClient) -> None:
    """Tool 계약대로 오류도 HTTP 200 + success=false로 그대로 반환한다."""
    response = client.get(
        "/api/tools/habitat-route",
        params={"current": "정문", "destination": "사자관"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HABITAT_NOT_FOUND"


def test_habitat_route_missing_required_query_param_is_422(client: TestClient) -> None:
    response = client.get("/api/tools/habitat-route", params={"current": "정문"})

    assert response.status_code == 422


def test_closure_status_without_habitat_returns_all_items(client: TestClient) -> None:
    response = client.get("/api/tools/closure-status")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    habitats = {item["habitat"] for item in body["data"]["items"]}
    assert habitats == {"정문", "호랑이관", "해양관", "코끼리관", "기린관"}
    closed = {item["habitat"] for item in body["data"]["items"] if item["closed"]}
    assert closed == {"코끼리관"}


def test_closure_status_with_habitat_returns_single_item(client: TestClient) -> None:
    response = client.get("/api/tools/closure-status", params={"habitat": "코끼리관"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["items"] == [
        {"habitat": "코끼리관", "closed": True, "reason": "시설 점검으로 임시 휴장"}
    ]


def test_closure_status_unknown_habitat_is_200_with_success_false(client: TestClient) -> None:
    response = client.get("/api/tools/closure-status", params={"habitat": "사자관"})

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HABITAT_NOT_FOUND"


def test_course_info_without_scope_uses_weather_and_returns_all_scope(
    client: TestClient,
) -> None:
    """날씨가 맑음(fixture 기본값)이므로 scope 생략 시 facility_scope="all"이어야 한다."""
    response = client.get(
        "/api/tools/course-info",
        params={"available_minutes": 120, "child_accompanying": True},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["facility_scope"] == "all"
    assert body["data"]["weather_lookup_succeeded"] is True


def test_course_info_without_scope_switches_to_indoor_when_raining(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _rainy(region: str, *, now=None):
        as_of = now or datetime.now(timezone.utc)
        return ToolRunResult(
            success=True,
            data={
                "region": region,
                "condition": "rain",
                "indoor_recommended": True,
                "as_of": as_of.isoformat(),
            },
            error=None,
            source="open_meteo_forecast",
            retrieved_at=as_of,
        )

    monkeypatch.setattr(course_weather_policy, "lookup_public_weather", _rainy)

    response = client.get(
        "/api/tools/course-info",
        params={"available_minutes": 120},
    )

    body = response.json()
    assert body["data"]["facility_scope"] == "indoor_only"
    assert body["data"]["weather_lookup_succeeded"] is True


def test_course_info_without_scope_marks_weather_lookup_failed(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """날씨 조회 자체가 실패해도 기본값(all)으로 코스는 반환하되 실패를 표시한다(§7)."""

    def _failing(region: str, *, now=None):
        return ToolRunResult(
            success=False,
            data={},
            error={"code": "WEATHER_LOOKUP_FAILED", "message": "실패"},
            source="open_meteo_forecast",
            retrieved_at=now or datetime.now(timezone.utc),
        )

    monkeypatch.setattr(course_weather_policy, "lookup_public_weather", _failing)

    response = client.get(
        "/api/tools/course-info",
        params={"available_minutes": 120},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["facility_scope"] == "all"
    assert body["data"]["weather_lookup_succeeded"] is False


def test_course_info_scope_outdoor_only_bypasses_weather(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scope=outdoor_only면 날씨를 아예 조회하지 않고 바로 get_outdoor_course_info를 부른다."""

    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("scope가 명시되면 날씨를 조회하면 안 된다")

    monkeypatch.setattr(course_weather_policy, "lookup_public_weather", _should_not_be_called)

    response = client.get(
        "/api/tools/course-info",
        params={"available_minutes": 120, "scope": "outdoor_only"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["facility_scope"] == "outdoor_only"


def test_course_info_scope_all_and_indoor_only_also_bypass_weather(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _should_not_be_called(*args, **kwargs):
        raise AssertionError("scope가 명시되면 날씨를 조회하면 안 된다")

    monkeypatch.setattr(course_weather_policy, "lookup_public_weather", _should_not_be_called)

    all_response = client.get(
        "/api/tools/course-info", params={"available_minutes": 120, "scope": "all"}
    )
    indoor_response = client.get(
        "/api/tools/course-info", params={"available_minutes": 120, "scope": "indoor_only"}
    )

    assert all_response.json()["data"]["facility_scope"] == "all"
    assert indoor_response.json()["data"]["facility_scope"] == "indoor_only"


def test_course_info_missing_available_minutes_is_422(client: TestClient) -> None:
    response = client.get("/api/tools/course-info")

    assert response.status_code == 422


def test_course_info_invalid_scope_value_is_422(client: TestClient) -> None:
    response = client.get(
        "/api/tools/course-info",
        params={"available_minutes": 120, "scope": "not_a_real_scope"},
    )

    assert response.status_code == 422
