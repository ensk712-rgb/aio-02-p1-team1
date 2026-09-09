"""전체 지도, 빠른 길찾기, 맞춤 관람 코스를 제공하는 통합 화면."""

import streamlit as st

from frontend.bootstrap import get_client
from frontend.clients.agent_client import AgentClientError
from frontend.components.layout import render_page_hero, render_sidebar
from frontend.components.route_map import MAP_POINTS, render_route_map

_ENTRANCE = "정문"
_SCOPE_NOTICE = {
    "indoor_only": "비 예보로 실내에서 관람 가능한 코스만 추천했습니다.",
    "outdoor_only": "실외 관람 코스만 추천했습니다.",
}


def _load_closures() -> list[dict] | None:
    try:
        result = get_client().get_closure_status()
    except AgentClientError as error:
        st.error(str(error), icon=":material/gpp_bad:")
        return None
    if not result.get("success"):
        st.error((result.get("error") or {}).get("message") or "휴장 정보를 불러오지 못했습니다.")
        return None
    return result.get("data", {}).get("items", [])


def _render_course(data: dict) -> None:
    scope = data.get("facility_scope")
    if scope in _SCOPE_NOTICE:
        st.info(_SCOPE_NOTICE[scope], icon=":material/info:")
    elif scope == "all" and data.get("weather_lookup_succeeded") is False:
        st.warning("날씨 정보를 확인하지 못해 실내·실외 코스를 모두 보여드립니다.")
    stops = data.get("stops") or []
    if not stops:
        st.warning("현재 조건에서 가능한 코스를 만들기 어렵습니다. 관람 시간을 늘리거나 조건을 조정해 주세요.")
        render_route_map(caption="추천 가능한 동선이 없습니다")
        return
    route_names = [data.get("current", _ENTRANCE)] + [stop["habitat"] for stop in stops]
    render_route_map(
        route_names,
        segment_minutes=[int(stop["travel_minutes"]) for stop in stops],
        total_minutes=sum(int(stop["travel_minutes"]) for stop in stops),
        caption="운영 데이터 기반 추천 동선 · 실제 보행 시간은 다를 수 있습니다",
    )
    st.subheader("코스별 관람 계획", icon=":material/format_list_numbered:")
    position = data.get("current", _ENTRANCE)
    for order, stop in enumerate(stops, start=1):
        with st.container(border=True):
            cols = st.columns([0.45, 2, 1, 1, 1], vertical_alignment="center")
            cols[0].markdown(f"### {order}")
            cols[1].markdown(f"**{position} → {stop['habitat']}**")
            cols[2].metric("이동", f"{stop['travel_minutes']}분")
            cols[3].metric("관람", f"{stop['visit_minutes']}분")
            cols[4].metric("누적", f"{stop['cumulative_minutes']}분")
        position = stop["habitat"]
    st.caption(f"총 소요 시간 · {data.get('total_minutes', 0)}분 / 남는 시간 · {data.get('remaining_minutes', 0)}분")


render_sidebar("map")
render_page_hero(
    "지도와 맞춤 경로를 한눈에",
    "목적지까지 빠른 길을 찾거나 관람 조건에 맞는 하루 코스를 설정하세요.",
    "지도서비스 이미지3.png",
    "MAP & SMART ROUTE",
)
st.space("small")
quick_tab, custom_tab = st.tabs(["빠른 길찾기", "맞춤 경로 설정"])

with quick_tab:
    closure_items = _load_closures()
    if closure_items is None:
        render_route_map()
    else:
        habitats = [item["habitat"] for item in closure_items]
        closed = {item["habitat"] for item in closure_items if item["closed"]}
        controls = st.columns(2)
        start = controls[0].selectbox("출발", habitats, index=habitats.index(_ENTRANCE), key="map_route_start")
        options = [name for name in habitats if name != start]
        default = "해양관" if "해양관" in options else options[0]
        destination = controls[1].selectbox(
            "도착", options, index=options.index(default),
            format_func=lambda name: f"{name} · 휴장" if name in closed else name,
            key="map_route_destination",
        )
        try:
            route = get_client().get_habitat_route(start, destination)
        except AgentClientError as error:
            route = None
            st.error(str(error), icon=":material/gpp_bad:")
        data = route.get("data", {}) if route and route.get("success") else {}
        render_route_map(data.get("path"), total_minutes=data.get("estimated_minutes"), closed_habitats=closed)
        if destination in closed:
            reason = next((item.get("reason") for item in closure_items if item["habitat"] == destination), None)
            st.warning(f"{destination}은(는) 현재 휴장 중입니다{f' — {reason}' if reason else ''}.")
        elif data:
            st.success(f"{' → '.join(data['path'])} · 도보 약 {data['estimated_minutes']}분")
        elif route:
            st.warning((route.get("error") or {}).get("message") or "경로를 찾을 수 없습니다.")

with custom_tab:
    with st.form("route_recommendation_form"):
        controls = st.columns(3, vertical_alignment="bottom")
        available = controls[0].number_input("관람 가능 시간(분)", min_value=10, max_value=600, value=120, step=10, key="route_available_minutes")
        current = controls[1].selectbox("현재 위치", list(MAP_POINTS), key="route_current")
        child = controls[2].checkbox("아이 동반", key="route_child_accompanying")
        submitted = st.form_submit_button("추천 동선 보기", icon=":material/route:", width="stretch")
    if submitted:
        try:
            st.session_state.route_recommendation_result = get_client().get_course_info(
                available_minutes=int(available), child_accompanying=child, current=current or _ENTRANCE,
            )
        except AgentClientError as error:
            st.session_state.route_recommendation_result = None
            st.error(str(error), icon=":material/gpp_bad:")
    result = st.session_state.get("route_recommendation_result")
    if result and result.get("success"):
        _render_course(result.get("data", {}))
    elif result:
        st.error((result.get("error") or {}).get("message") or "코스를 계산하지 못했습니다.")
    else:
        render_route_map(caption="관람 조건을 선택하면 이 지도에 추천 동선이 표시됩니다")
