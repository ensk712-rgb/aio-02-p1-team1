"""tests/agent 전역 픽스처.

zoo_guide Profile은 이제 get_course_info/get_indoor_course_info를 모두
등록하고 있어서, run_agent()를 쓰는 테스트는 (Tool 호출과 무관한 것들까지도)
매 실행마다 날씨 선조회(P1-B 계획서 §6.2)를 함께 거친다. 이 픽스처는 실제
Open-Meteo API를 타지 않도록 lookup_public_weather를 맑음 고정값으로
가짜 처리한다 — 날씨 narrowing 자체를 검증하는 테스트는 개별적으로 다시
monkeypatch해서 이 기본값을 덮어쓰면 된다.
"""

from datetime import datetime, timezone

import pytest

from backend.app.schemas.common import ToolRunResult
from backend.app.tools import course_weather_policy


@pytest.fixture(autouse=True)
def _fake_weather_lookup(monkeypatch: pytest.MonkeyPatch):
    def _fake_lookup_public_weather(region: str, *, now: datetime | None = None):
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

    # course_weather_policy.py가 `from ... import lookup_public_weather`로
    # 이름을 직접 들여왔으므로, zoo_tools 쪽이 아니라 이 모듈의 이름을
    # 패치해야 실제로 적용된다.
    monkeypatch.setattr(
        course_weather_policy, "lookup_public_weather", _fake_lookup_public_weather
    )
