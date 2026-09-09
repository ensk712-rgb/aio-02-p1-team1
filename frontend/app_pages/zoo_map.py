"""전체 지도 탐색 화면.

P1-B 맞춤 코스 추천 개발계획서 §11.3·15단계 구현이다. 하드코딩된 구역 목록·
이동 시간 문자열을 걷어내고, 실제 운영 데이터(habitats.json/routes.json/
closures.json)를 GET /api/tools/closure-status·/api/tools/habitat-route로
조회해 그대로 표시한다.
"""


import base64
import html
from pathlib import Path

import streamlit as st

from frontend.bootstrap import get_client
from frontend.clients.agent_client import AgentClientError

from frontend.components.layout import render_page_hero, render_sidebar

_ENTRANCE = "정문"
_MAP_IMAGE_PATH = Path(__file__).resolve().parents[2] / "docs" / "design" / "동물원 지도.png"
_MAP_POINTS = {
    "정문": (768, 848),
    "호랑이관": (427, 184),
    "해양관": (1082, 579),
    "코끼리관": (1152, 177),
    "기린관": (934, 166),
}
_PLAZA_POINT = (770, 421)


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


def _route_path(points: list[tuple[int, int]]) -> str:
    """시설 좌표를 지도 중앙 산책로를 거치는 부드러운 SVG 경로로 바꾼다."""
    if not points:
        return ""
    path = [f"M {points[0][0]} {points[0][1]}"]
    for point in points[1:]:
        if point != _PLAZA_POINT:
            path.append(
                f"Q {_PLAZA_POINT[0]} {_PLAZA_POINT[1]} {point[0]} {point[1]}"
            )
        else:
            path.append(f"L {point[0]} {point[1]}")
    return " ".join(path)


def _render_route_map(route_data: dict | None, closed_habitats: set[str]) -> None:
    """첨부 지도 위에 선택 경로와 출발·도착 표식을 겹쳐 렌더링한다."""
    encoded = base64.b64encode(_MAP_IMAGE_PATH.read_bytes()).decode("ascii")
    route_names = (route_data or {}).get("path") or []
    plotted_names: list[str] = []
    for name in route_names:
        if name not in _MAP_POINTS:
            continue
        if plotted_names and plotted_names[-1] != _ENTRANCE and name != _ENTRANCE:
            plotted_names.append("__plaza__")
        plotted_names.append(name)

    plotted_points = [
        _PLAZA_POINT if name == "__plaza__" else _MAP_POINTS[name]
        for name in plotted_names
    ]
    path_markup = ""
    marker_markup = ""
    if plotted_points:
        path_markup = (
            f'<path class="route-shadow" d="{_route_path(plotted_points)}" '
            'fill="none" stroke="rgba(255,255,255,.94)" stroke-width="18" '
            'stroke-linecap="round" stroke-linejoin="round"></path>'
            f'<path class="route-line" d="{_route_path(plotted_points)}" '
            'fill="none" stroke="#0b5c43" stroke-width="9" stroke-dasharray="20 13" '
            'stroke-linecap="round" stroke-linejoin="round"></path>'
        )
        visible_names = [name for name in plotted_names if name != "__plaza__"]
        for index, name in enumerate(visible_names):
            x, y = _MAP_POINTS[name]
            marker_class = "is-closed" if name in closed_habitats else ""
            marker_color = "#b02a1e" if name in closed_habitats else "#0b5c43"
            marker_label = "출발" if index == 0 else "도착" if index == len(visible_names) - 1 else "경유"
            marker_markup += (
                f'<g class="route-marker {marker_class}" transform="translate({x} {y})">'
                f'<circle r="18" fill="#fff" stroke="{marker_color}" stroke-width="7"></circle>'
                f'<circle class="marker-core" r="7" fill="{marker_color}"></circle>'
                f'<text y="-27" fill="#fff" stroke="#07452f" stroke-width="9" '
                'paint-order="stroke" text-anchor="middle" font-family="Arial,sans-serif" '
                f'font-size="23" font-weight="800">{html.escape(name)} · {marker_label}</text></g>'
            )

    overlay_svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1536 1024">'
        f'{path_markup}{marker_markup}</svg>'
    )
    overlay_encoded = base64.b64encode(overlay_svg.encode("utf-8")).decode("ascii")

    st.html(
        f"""
        <figure class="zoo-photo-map">
          <div class="zoo-photo-map__canvas">
            <img src="data:image/png;base64,{encoded}" alt="동물 사진과 산책로가 표시된 동물원 지도">
            <img src="data:image/svg+xml;base64,{overlay_encoded}" alt="선택한 시설까지의 보행 경로" style="position:absolute;inset:0;width:100%;height:100%;z-index:2;pointer-events:none;object-fit:cover">
          </div>
          <figcaption><span><i class="map-key map-key--route"></i>선택 경로</span><span><i class="map-key map-key--closed"></i>휴장 시설</span><small>배치 시안 · 실제 위치와 다를 수 있습니다</small></figcaption>
        </figure>
        """
    )

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
    _render_route_map(None, set())
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
    _render_route_map(route_data, closed_habitats)

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
