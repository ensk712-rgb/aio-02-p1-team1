"""현재 날씨와 단기 일기예보 화면."""

from __future__ import annotations

from datetime import date
import os

import streamlit as st

from frontend.bootstrap import get_client
from frontend.clients.agent_client import AgentClientError
from frontend.components.layout import render_page_hero, render_sidebar

_CONDITION = {
    "clear": ("맑음", "☀️"),
    "cloudy": ("흐림", "☁️"),
    "rain": ("비", "🌧️"),
    "storm": ("뇌우", "⛈️"),
}


def _value(value, suffix: str = "") -> str:
    return "정보 없음" if value is None else f"{value}{suffix}"


render_sidebar("environment")
render_page_hero(
    "오늘과 앞으로의 날씨",
    "현재 날씨와 일기예보를 확인하고 더 편안한 관람 계획을 세워보세요.",
    "동물지킴이 히어로 사진.jpg",
    "ZOO WEATHER",
)
st.space("small")

try:
    result = get_client().get_public_weather("서울")
except AgentClientError as error:
    result = None
    st.error(str(error), icon=":material/cloud_off:")

if result and result.get("success"):
    data = result.get("data", {})
    current = data.get("current") or {}
    condition_label, condition_icon = _CONDITION.get(
        current.get("condition", data.get("condition")), ("확인 중", "🌿")
    )
    st.subheader(f"오늘의 날씨 · {condition_icon} {condition_label}")
    metrics = st.columns(4)
    metrics[0].metric(
        "기온",
        _value(current.get("temperature_c"), "°C"),
        _value(current.get("apparent_temperature_c"), "°C") + " 체감",
    )
    metrics[1].metric("습도", _value(current.get("humidity_percent"), "%"))
    metrics[2].metric("바람", _value(current.get("wind_speed_kmh"), " km/h"))
    metrics[3].metric(
        "관람 추천", "실내 중심" if data.get("indoor_recommended") else "실내·야외"
    )

    st.subheader("일기예보", icon=":material/calendar_month:")
    forecast = (data.get("forecast") or [])[:4]
    if forecast:
        for column, item in zip(st.columns(len(forecast)), forecast):
            label, icon = _CONDITION.get(item.get("condition"), ("확인 중", "🌿"))
            day = date.fromisoformat(item["date"])
            with column.container(border=True):
                st.caption("오늘" if day == date.today() else f"{day.month}/{day.day}")
                st.markdown(f"### {icon} {label}")
                st.write(
                    f"{_value(item.get('temperature_min_c'), '°')} / "
                    f"**{_value(item.get('temperature_max_c'), '°')}**"
                )
                st.caption(
                    "강수 확률 · "
                    + _value(item.get("precipitation_probability_percent"), "%")
                )
    else:
        st.info("현재 일기예보 데이터가 없습니다.", icon=":material/info:")

    if data.get("indoor_recommended"):
        st.warning(
            "비 또는 뇌우가 예상됩니다. 해양관 등 실내 관람을 먼저 고려하세요.",
            icon=":material/umbrella:",
        )
    else:
        st.success(
            "야외 관람이 가능한 날씨입니다. 수분 보충과 햇빛 차단도 챙겨주세요.",
            icon=":material/eco:",
        )
    st.caption(f"Open-Meteo 제공 · 기준 시각 {data.get('as_of', '-')} · 10분 캐시")
    if os.getenv("ZOO_UI_FAKE_MODE") == "1":
        st.caption(":material/science: 현재 날씨와 일기예보는 화면 시연용 Mock 데이터입니다.")
elif result:
    error = result.get("error") or {}
    st.error(
        error.get("message") or "날씨 정보를 불러오지 못했습니다.",
        icon=":material/cloud_off:",
    )
