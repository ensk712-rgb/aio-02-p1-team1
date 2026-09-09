"""전체 지도 탐색 화면.

P1-B 맞춤 코스 추천 개발계획서 §11.3·15단계 구현이다. 하드코딩된 구역 목록·
이동 시간 문자열을 걷어내고, 실제 운영 데이터(habitats.json/routes.json/
closures.json)를 GET /api/tools/closure-status·/api/tools/habitat-route로
조회해 그대로 표시한다.
"""

import streamlit as st

from frontend.bootstrap import get_client
from frontend.clients.agent_client import AgentClientError
from frontend.components.layout import IMAGE_DIR, render_page_hero, render_sidebar

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

map_col, info_col = st.columns([2.25, 1], gap="large")
with map_col:
    st.image(
        str(IMAGE_DIR / "예약승인 팜플릿 이미지2_전체 지도 맵.png"),
        caption="전체 지도 · 확대해서 주요 구역을 확인하세요",
        width="stretch",
    )
with info_col:
    st.subheader("빠른 위치 찾기", icon=":material/location_on:")
    if closure_items is None:
        st.warning("시설 목록을 불러올 수 없어 위치 안내를 표시할 수 없습니다.", icon=":material/warning:")
    else:
        habitats = [item["habitat"] for item in closure_items if item["habitat"] != _ENTRANCE]
        closed_habitats = {item["habitat"] for item in closure_items if item["closed"]}
        zone = st.radio(
            "이동할 구역",
            habitats,
            format_func=lambda name: f"{name} (휴장)" if name in closed_habitats else name,
        )
        if zone in closed_habitats:
            reason = next(
                (item["reason"] for item in closure_items if item["habitat"] == zone), None
            )
            st.warning(f"현재 휴장 중입니다{f' — {reason}' if reason else ''}.", icon=":material/block:")
        else:
            try:
                route = get_client().get_habitat_route(_ENTRANCE, zone)
            except AgentClientError as error:
                route = None
                st.error(str(error), icon=":material/gpp_bad:")
            if route is not None:
                if route.get("success"):
                    data = route["data"]
                    st.success(
                        f"{' → '.join(data['path'])} · 도보 약 {data['estimated_minutes']}분",
                        icon=":material/directions_walk:",
                    )
                else:
                    error = route.get("error") or {}
                    st.warning(error.get("message") or "경로를 찾을 수 없습니다.", icon=":material/warning:")
        st.image(
            str(IMAGE_DIR / "지도서비스 이미지2.png"),
            caption="모바일 지도 서비스 참고 이미지",
            width="stretch",
        )
