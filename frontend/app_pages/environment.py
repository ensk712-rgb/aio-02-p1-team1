"""관람 환경 상태 화면."""
import streamlit as st
from frontend.components.layout import IMAGE_DIR, render_mock_notice, render_page_hero, render_sidebar

render_sidebar("environment")
render_page_hero("숲의 리듬을 확인하세요", "날씨와 구역별 혼잡도를 살펴 더 쾌적한 관람 시간을 선택하세요.", "동물지킴이 히어로 사진.jpg", "LIVE PARK PULSE")
st.space("small")
metrics = st.columns(4)
for col, label, value, delta in zip(metrics,["기온","습도","미세먼지","전체 혼잡도"],["26°C","54%","좋음","보통"],["체감 27°C","쾌적","32 ㎍/㎥","43%"]): col.metric(label,value,delta)
left, right = st.columns([1.25,1], gap="large")
with left:
    st.subheader("구역별 혼잡도", icon=":material/groups:")
    for label, value in [("판다월드",.72),("사바나",.48),("펭귄 빌리지",.35),("호랑이 숲",.28)]: st.progress(value, text=f"{label} · {int(value*100)}%")
with right:
    st.image(str(IMAGE_DIR / "지도서비스 이미지.png"), caption="스마트 파크 안내", width="stretch")
    st.success("지금은 호랑이 숲부터 관람하면 가장 여유로워요.", icon=":material/eco:")
render_mock_notice()
