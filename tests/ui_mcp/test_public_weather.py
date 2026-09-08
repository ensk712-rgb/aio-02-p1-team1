"""공공 날씨 MCP wrapper의 단위 계약을 검증한다."""

from __future__ import annotations

from datetime import datetime

from mcp_server.tools import public_data
from mcp_server.tools.public_data import lookup_public_weather


def test_lookup_public_weather_returns_common_result(monkeypatch) -> None:
    fixed_now = datetime.fromisoformat("2026-09-08T10:00:00+09:00")
    monkeypatch.setattr(public_data, "_resolve_now", lambda: fixed_now)

    result = lookup_public_weather(" 서울 ")

    assert result["success"] is True
    assert result["data"] == {
        "region": "서울",
        "condition": "맑음",
        "as_of": "2026-09-08T10:00:00+09:00",
    }
    assert result["error"] is None
    assert result["source"] == "mock_public_weather"
    assert datetime.fromisoformat(result["retrieved_at"]).utcoffset() is not None


def test_lookup_public_weather_rejects_unknown_region() -> None:
    result = lookup_public_weather("부산")

    assert result["success"] is False
    assert result["data"] == {}
    assert result["error"]["code"] == "REGION_NOT_FOUND"
    assert result["source"] == "mock_public_weather"


def test_lookup_public_weather_rejects_blank_region() -> None:
    result = lookup_public_weather("   ")

    assert result["success"] is False
    assert result["error"]["code"] == "INVALID_ARGUMENT"
