"""전체 지도 탐색 화면."""
import streamlit as st
from frontend.components.layout import IMAGE_DIR, render_mock_notice, render_page_hero, render_sidebar

render_sidebar("map")
render_page_hero("오늘의 모험 지도를 펼쳐요", "구역별 위치를 확인하고 길을 잃지 않도록 출발지를 기억하세요.", "지도서비스 이미지.png", "EXPLORE THE PARK")
st.space("small")
map_col, info_col = st.columns([2.25, 1], gap="large")
with map_col:
    st.image(str(IMAGE_DIR / "예약승인 팜플릿 이미지2_전체 지도 맵.png"), caption="전체 지도 · 확대해서 주요 구역을 확인하세요", width="stretch")
with info_col:
    st.subheader("빠른 위치 찾기", icon=":material/location_on:")
    zone = st.radio("이동할 구역", ["판다월드", "사바나", "펭귄 빌리지", "호랑이 숲"])
    details = {"판다월드":"글로벌페어 → 주토피아 · 도보 약 18분", "사바나":"정문 → 주토피아 · 도보 약 22분", "펭귄 빌리지":"판다월드 → 실내관 · 도보 약 7분", "호랑이 숲":"사바나 → 맹수 구역 · 도보 약 9분"}
    st.success(details[zone], icon=":material/directions_walk:")
    st.image(str(IMAGE_DIR / "지도서비스 이미지2.png"), caption="모바일 지도 서비스 참고 이미지", width="stretch")
render_mock_notice()
