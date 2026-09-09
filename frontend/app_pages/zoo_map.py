"""전체 지도 탐색 화면.

P1-B 맞춤 코스 추천 개발계획서 §11.3·15단계 구현이다. 하드코딩된 구역 목록·
이동 시간 문자열을 걷어내고, 실제 운영 데이터(habitats.json/routes.json/
closures.json)를 GET /api/tools/closure-status·/api/tools/habitat-route로
조회해 그대로 표시한다.
"""

import streamlit as st

from frontend.bootstrap import get_client
from frontend.clients.agent_client import AgentClientError
from frontend.components.layout import render_page_hero, render_sidebar
from frontend.components.route_map import render_route_map

_ENTRANCE = "정문"


def _load_closure_items() -> list[dict] | None:
    try:
        result = get_client().get_closure_status()
    except AgentClientError as error:
        st.error(str(error), icon=":material/gpp_bad:")
        return None
    if not result.get("success"):
        error = result.get("error") or {}
        st.error(error.get("message") or "휴장 정보를 불러오지 못했습니다.", icon=":material/gpp_bad:")
        return None
    return result.get("data", {}).get("items", [])


render_sidebar("map")
render_page_hero(
    "오늘의 모험 지도를 펼쳐요",
    "구역별 위치를 확인하고 길을 잃지 않도록 출발지를 기억하세요.",
    "지도서비스 이미지.png",
    "EXPLORE THE PARK",
)
st.space("small")

closure_items = _load_closure_items()

if closure_items is None:
    st.warning("시설 목록을 불러올 수 없어 위치 안내를 표시할 수 없습니다.", icon=":material/warning:")
    render_route_map(None, closed_habitats=set())
else:
    habitats = [item["habitat"] for item in closure_items]
    closed_habitats = {item["habitat"] for item in closure_items if item["closed"]}
    controls, route_summary = st.columns([1.15, 2.2], gap="large", vertical_alignment="bottom")
    with controls:
        st.subheader("빠른 길 찾기", icon=":material/location_on:")
        start = st.selectbox("출발", habitats, index=habitats.index(_ENTRANCE), key="map_route_start")
    with route_summary:
        destination_options = [name for name in habitats if name != start]
        default_destination = "해양관" if "해양관" in destination_options else destination_options[0]
        destination = st.selectbox(
            "도착",
            destination_options,
            index=destination_options.index(default_destination),
            format_func=lambda name: f"{name} · 휴장" if name in closed_habitats else name,
            key="map_route_destination",
        )

    try:
        route = get_client().get_habitat_route(start, destination)
    except AgentClientError as error:
        route = None
        st.error(str(error), icon=":material/gpp_bad:")

    route_data = route.get("data", {}) if route and route.get("success") else None

    render_route_map(
        (route_data or {}).get("path"),
        total_minutes=(route_data or {}).get("estimated_minutes"),
        closed_habitats=closed_habitats,
    )

    if destination in closed_habitats:
        reason = next(
            (item["reason"] for item in closure_items if item["habitat"] == destination), None
        )
        st.warning(
            f"{destination}은(는) 현재 휴장 중입니다{f' — {reason}' if reason else ''}.",
            icon=":material/block:",
        )
    if route_data and destination not in closed_habitats:
        st.success(
            f"{' → '.join(route_data['path'])} · 도보 약 {route_data['estimated_minutes']}분",
            icon=":material/directions_walk:",
        )
    elif route:
        error = route.get("error") or {}
        st.warning(error.get("message") or "경로를 찾을 수 없습니다.", icon=":material/warning:")
