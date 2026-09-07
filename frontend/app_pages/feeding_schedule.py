"""먹이주기 일정 화면."""
import streamlit as st
from frontend.components.layout import render_mock_notice, render_page_hero, render_sidebar

render_sidebar("feeding")
render_page_hero("가장 생생한 순간을 놓치지 마세요", "동물별 먹이 설명 시간과 장소를 확인해 관람 순서를 정해보세요.", "동물이지미.jpg", "TODAY'S FEEDING")
st.space("small")
times = [("10:30","기린","사바나","곧 시작"),("11:00","펭귄","펭귄 빌리지","여유"),("13:30","코끼리","코끼리 숲","여유"),("15:30","호랑이","호랑이 숲","여유")]
for idx, (time, animal, place, state) in enumerate(times):
    with st.container(border=True):
        cols = st.columns([.7,1,1.5,.7], vertical_alignment="center")
        cols[0].subheader(time); cols[1].markdown(f"### {animal}"); cols[2].write(place); cols[3].badge(state, color="orange" if idx == 0 else "green")
st.warning("현장 운영과 동물 건강 상태에 따라 일정이 바뀔 수 있습니다.", icon=":material/campaign:")
render_mock_notice()
