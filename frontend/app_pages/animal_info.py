"""동물 정보 탐색 화면."""
import streamlit as st
from frontend.components.layout import IMAGE_DIR, render_mock_notice, render_page_hero, render_sidebar

render_sidebar("animals")
render_page_hero("동물 친구들을 만나보세요", "관람 전 특징과 에티켓을 한눈에 살펴보세요.", "동물지킴이 히어로 사진.jpg", "ANIMAL ENCYCLOPEDIA")
st.space("small")
left, right = st.columns([1.15, 1], gap="large")
with left:
    st.image(str(IMAGE_DIR / "동물이지미.jpg"), caption="동물원에서 만나는 다채로운 친구들", width="stretch")
with right:
    animal = st.selectbox("궁금한 동물", ["자이언트 판다", "기린", "코끼리", "펭귄", "호랑이"])
    facts = {"자이언트 판다":("대나무 숲", "대나무", "오전 관람 추천"), "기린":("사바나", "나뭇잎", "10:30 먹이 설명"), "코끼리":("코끼리 숲", "건초와 과일", "13:30 먹이 설명"), "펭귄":("펭귄 빌리지", "생선", "11:00 먹이 설명"), "호랑이":("호랑이 숲", "육류", "15:30 먹이 설명")}
    habitat, food, tip = facts[animal]
    st.subheader(animal, icon=":material/pets:")
    a, b = st.columns(2)
    a.metric("만나는 곳", habitat); b.metric("좋아하는 먹이", food)
    st.success(tip, icon=":material/lightbulb:")
    st.info("큰 소리를 내거나 유리창을 두드리지 말아 주세요.", icon=":material/volunteer_activism:")
render_mock_notice()
