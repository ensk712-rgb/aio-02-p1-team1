"""관람 동선 추천 화면.

P1-B 맞춤 코스 추천 개발계획서 §7·14단계 구현이다. Agent 채팅을 거치지 않고
GET /api/tools/course-info(§11.4)를 직접 호출해, 코스 추천 Tool 3종(§5.0) 중
하나가 반환한 구조화된 data를 그대로 렌더링한다 — Agent의 임의 문장을 쓰지
않는다(v0.4 §3 "확인할 근거가 없으면 추측하지 않는다").
"""

import streamlit as st

from frontend.bootstrap import get_client
from frontend.clients.agent_client import AgentClientError
from frontend.components.layout import render_page_hero, render_sidebar
from frontend.components.route_map import MAP_POINTS, render_route_map

_SCOPE_NOTICE = {
    "indoor_only": "비 예보로 실내에서 관람 가능한 코스만 추천했습니다.",
    "outdoor_only": "실외 관람 코스만 추천했습니다.",
}
_WEATHER_LOOKUP_FAILED_NOTICE = "날씨 정보를 확인하지 못해 실내·실외 코스를 모두 보여드립니다."
_EMPTY_RESULT_NOTICE = "현재 조건에서 가능한 코스를 만들기 어렵습니다. 관람 시간을 늘리거나 조건을 조정해 주세요."


def _render_course_result(data: dict) -> None:
    facility_scope = data.get("facility_scope")
    notice = _SCOPE_NOTICE.get(facility_scope)
    if notice:
        st.info(notice, icon=":material/info:")
    elif facility_scope == "all" and data.get("weather_lookup_succeeded") is False:
        st.warning(_WEATHER_LOOKUP_FAILED_NOTICE, icon=":material/cloud_off:")

    stops = data.get("stops") or []
    if not stops:
        st.warning(_EMPTY_RESULT_NOTICE, icon=":material/route:")
        return

    route_names = [data.get("current", "정문")] + [stop["habitat"] for stop in stops]
    render_route_map(
        route_names,
        segment_minutes=[int(stop["travel_minutes"]) for stop in stops],
        total_minutes=sum(int(stop["travel_minutes"]) for stop in stops),
        caption="운영 데이터 기반 추천 동선 · 실제 보행 시간은 다를 수 있습니다",
    )
    st.subheader("코스별 관람 계획", icon=":material/format_list_numbered:")

    position = data.get("current", "정문")
    for order, stop in enumerate(stops, start=1):
        with st.container(border=True):
            cols = st.columns([0.5, 2, 1, 1, 1], vertical_alignment="center")
            cols[0].markdown(f"### {order}")
            cols[1].markdown(f"**{position} → {stop['habitat']}**")
            cols[2].metric("이동", f"{stop['travel_minutes']}분")
            cols[3].metric("관람", f"{stop['visit_minutes']}분")
            cols[4].metric("누적", f"{stop['cumulative_minutes']}분")
        position = stop["habitat"]

    total = data.get("total_minutes", 0)
    remaining = data.get("remaining_minutes", 0)
    st.caption(f"총 소요 시간 · {total}분 / 남는 시간 · {remaining}분")


render_sidebar("route")
render_page_hero(
    "나만의 하루를 디자인하세요",
    "관람 시간과 조건에 맞춰 실제 운영 데이터 기반 추천 동선을 확인해보세요.",
    "지도서비스 이미지3.png",
    "SMART ROUTE",
)
st.space("small")

with st.form("route_recommendation_form"):
    controls = st.columns([1, 1, 1], vertical_alignment="bottom")
    with controls[0]:
        available_minutes = st.number_input(
            "관람 가능 시간(분)",
            min_value=10,
            max_value=600,
            value=120,
            step=10,
            key="route_available_minutes",
        )
    with controls[1]:
        current = st.selectbox("현재 위치", list(MAP_POINTS), key="route_current")
    with controls[2]:
        child_accompanying = st.checkbox("아이 동반", key="route_child_accompanying")
        submitted = st.form_submit_button(
            "추천 동선 보기", icon=":material/route:", width="stretch"
        )

if submitted:
    try:
        response = get_client().get_course_info(
            available_minutes=int(available_minutes),
            child_accompanying=child_accompanying,
            current=current or "정문",
        )
        st.session_state["route_recommendation_result"] = response
    except AgentClientError as error:
        st.session_state["route_recommendation_result"] = None
        st.error(str(error), icon=":material/gpp_bad:")

result = st.session_state.get("route_recommendation_result")
if result:
    if result.get("success"):
        _render_course_result(result.get("data", {}))
    else:
        error = result.get("error") or {}
        st.error(
            error.get("message") or "코스를 계산하지 못했습니다.",
            icon=":material/gpp_bad:",
        )
else:
    render_route_map(caption="관람 조건을 선택하면 이 지도에 추천 동선이 표시됩니다")
