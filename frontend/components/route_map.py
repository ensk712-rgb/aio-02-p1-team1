"""첨부 동물원 지도 위에 관람 동선을 표시하는 공통 컴포넌트."""

from __future__ import annotations

import base64
import html
from pathlib import Path

import streamlit as st


MAP_IMAGE_PATH = Path(__file__).resolve().parents[1] / "image" / "zoo_animal_photo_map_v2.png"
MAP_VIEWBOX = (1448, 1086)


MAP_POINTS = {
    "정문": (724, 900),
    "호랑이관": (728, 145),
    "해양관": (294, 790),
    "코끼리관": (997, 570),
    "기린관": (1007, 345),
}
PLAZA_POINT = (724, 625)


def _route_path(points: list[tuple[int, int]]) -> str:
    if not points:
        return ""
    parts = [f"M {points[0][0]} {points[0][1]}"]
    for point in points[1:]:
        if point != PLAZA_POINT:
            parts.append(f"Q {PLAZA_POINT[0]} {PLAZA_POINT[1]} {point[0]} {point[1]}")
        else:
            parts.append(f"L {point[0]} {point[1]}")
    return " ".join(parts)


def render_route_map(
    route_names: list[str] | None = None,
    *,
    segment_minutes: list[int] | None = None,
    total_minutes: int | None = None,
    closed_habitats: set[str] | None = None,
    caption: str = "배치 시안 · 실제 위치와 다를 수 있습니다",
) -> None:
    """공통 지도에 애니메이션 경로, 출발·경유·도착, 도보 시간을 표시한다."""
    route_names = [name for name in (route_names or []) if name in MAP_POINTS]
    closed_habitats = closed_habitats or set()
    plotted_names: list[str] = []
    for name in route_names:
        if plotted_names and plotted_names[-1] != "정문" and name != "정문":
            plotted_names.append("__plaza__")
        plotted_names.append(name)
    plotted_points = [
        PLAZA_POINT if name == "__plaza__" else MAP_POINTS[name]
        for name in plotted_names
    ]

    path_markup = marker_markup = minute_markup = ""
    path_value = _route_path(plotted_points)
    if path_value:
        path_markup = (
            f'<path d="{path_value}" fill="none" stroke="rgba(255,255,255,.96)" '
            'stroke-width="20" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path id="activeRoute" class="route-line" d="{path_value}" fill="none" '
            'stroke="#087a58" stroke-width="10" stroke-dasharray="22 14" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
            '<circle r="8" fill="#ffcf4a" stroke="#fff" stroke-width="4">'
            '<animateMotion dur="6s" repeatCount="indefinite" rotate="auto">'
            '<mpath href="#activeRoute"/></animateMotion></circle>'
        )

    for index, name in enumerate(route_names):
        x, y = MAP_POINTS[name]
        role = "출발" if index == 0 else "도착" if index == len(route_names) - 1 else f"경유 {index}"
        color = "#b02a1e" if name in closed_habitats else (
            "#087a58" if index == 0 else "#215ca3" if index == len(route_names) - 1 else "#d58a13"
        )
        if index == 0:
            symbol = f'<circle r="20" fill="{color}" stroke="#fff" stroke-width="6"/>'
        elif index == len(route_names) - 1:
            symbol = f'<circle r="22" fill="#fff" stroke="{color}" stroke-width="7"/><circle r="10" fill="{color}"/>'
        else:
            symbol = f'<circle r="19" fill="#fff" stroke="{color}" stroke-width="7"/>'
        marker_markup += (
            f'<g transform="translate({x} {y})">{symbol}'
            f'<text y="-31" fill="#fff" stroke="#123b2d" stroke-width="10" paint-order="stroke" '
            'text-anchor="middle" font-family="Arial,sans-serif" font-size="22" font-weight="800">'
            f'{html.escape(role)} · {html.escape(name)}</text></g>'
        )

    minutes = list(segment_minutes or [])
    if len(route_names) == 2 and not minutes and total_minutes is not None:
        minutes = [total_minutes]
    for index, value in enumerate(minutes[: max(0, len(route_names) - 1)]):
        x1, y1 = MAP_POINTS[route_names[index]]
        x2, y2 = MAP_POINTS[route_names[index + 1]]
        x = int((x1 + x2 + PLAZA_POINT[0]) / 3)
        y = int((y1 + y2 + PLAZA_POINT[1]) / 3)
        label = f"도보 약 {int(value)}분"
        width = 142
        minute_markup += (
            f'<g transform="translate({x} {y})"><rect x="{-width // 2}" y="-20" width="{width}" '
            'height="40" rx="20" fill="#fff" stroke="#087a58" stroke-width="3" opacity=".96"/>'
            f'<text y="8" text-anchor="middle" fill="#123b2d" font-family="Arial,sans-serif" '
            f'font-size="20" font-weight="800">{label}</text></g>'
        )

    overlay = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {MAP_VIEWBOX[0]} {MAP_VIEWBOX[1]}">'
        '<style>@keyframes draw{to{stroke-dashoffset:-720}}.route-line{animation:draw 13s linear infinite}</style>'
        f'{path_markup}{minute_markup}{marker_markup}</svg>'
    )
    image_data = base64.b64encode(MAP_IMAGE_PATH.read_bytes()).decode("ascii")
    overlay_data = base64.b64encode(overlay.encode("utf-8")).decode("ascii")
    total_badge = f'<b>총 도보 약 {int(total_minutes)}분</b>' if total_minutes is not None else ""
    st.html(
        f'<figure class="zoo-photo-map"><div class="zoo-photo-map__canvas">'
        f'<img src="data:image/png;base64,{image_data}" alt="동물원 안내 지도">'
        f'<img src="data:image/svg+xml;base64,{overlay_data}" alt="추천 관람 동선" '
        'style="position:absolute;inset:0;width:100%;height:100%;z-index:2;pointer-events:none;object-fit:cover">'
        f'</div><figcaption><span><i class="map-key map-key--route"></i>추천 동선</span>'
        f'<span>● 출발　○ 경유　◎ 도착</span>{total_badge}<small>{html.escape(caption)}</small></figcaption></figure>'
    )
