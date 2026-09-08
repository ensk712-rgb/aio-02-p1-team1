"""관람 동선 추천 화면."""
import streamlit as st
from frontend.components.layout import IMAGE_DIR, render_mock_notice, render_page_hero, render_sidebar

render_sidebar("route")
render_page_hero("나만의 하루를 디자인하세요", "관람 시간과 관심 동물에 맞춰 편안한 추천 동선을 골라보세요.", "지도서비스 이미지3.png", "SMART ROUTE")
st.space("small")
left, right = st.columns([1,1.4], gap="large")
with left:
    duration = st.segmented_control("관람 시간", ["90분", "2시간 30분", "반일"], default="2시간 30분")
    priority = st.multiselect("꼭 만나고 싶은 동물", ["판다", "기린", "펭귄", "코끼리", "호랑이"], default=["판다", "기린"])
    st.metric("예상 이동", "3.2 km", "휴식 2회 포함")
with right:
    st.image(str(IMAGE_DIR / "예약승인 팜플릿 이미지2_전체 지도 맵.png"), caption="추천 동선용 전체 지도", width="stretch")
st.html('<div class="zoo-route">입구 → 🦒 사바나 → 🐼 판다월드 → ☕ 휴식 → 🐧 펭귄 빌리지</div>')
st.caption(f"선택: {duration} · 관심 동물 {', '.join(priority) if priority else '전체'}")
render_mock_notice()
