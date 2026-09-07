"""Phase 8 사용자 체험 예약 및 승인 카드 전용 화면."""

import os

import streamlit as st

from frontend.bootstrap import get_client
from frontend.components.layout import IMAGE_DIR, render_page_hero, render_sidebar
from frontend.components.reservation import render_reservation


render_sidebar("reservation")
render_page_hero(
    "동물과 더 가까워지는 특별한 시간",
    "프로그램을 선택한 뒤 내용을 직접 확인하면 관리자에게 승인 요청이 전달됩니다.",
    "예약승인 팜플릿 이미지.png",
    "KEEPER EXPERIENCE",
)

st.space("small")
guide, reservation = st.columns([1, 1.25], gap="large")
with guide:
    st.image(
        str(IMAGE_DIR / "동물지킴이 히어로 사진.jpg"),
        caption="동물지킴이와 함께하는 생생한 체험",
        width="stretch",
    )
    st.subheader("예약은 이렇게 진행돼요", icon=":material/route:")
    for number, title, description in (
        ("01", "프로그램 선택", "체험 종류, 시간, 인원을 선택합니다."),
        ("02", "120초 내 직접 확인", "확인 전에는 예약이 생성되지 않습니다."),
        ("03", "관리자 검토", "승인 또는 거절 결과가 내 예약에 반영됩니다."),
    ):
        with st.container(border=True):
            st.markdown(f"**{number} · {title}**")
            st.caption(description)
    st.warning("현장 운영과 동물 건강 상태에 따라 체험이 변경될 수 있습니다.", icon=":material/campaign:")

with reservation:
    st.subheader("체험 예약 센터", icon=":material/confirmation_number:")
    st.caption("민감한 승인 판단은 화면이 아닌 서버에서 처리합니다.")
    render_reservation(get_client(), expanded=True)

if os.getenv("ZOO_UI_FAKE_MODE") == "1":
    st.caption(":material/science: 시연용 Mock 모드에서는 예약과 관리자 판정이 메모리 데이터로 동작합니다.")
else:
    st.caption(":material/cloud_done: 실제 Backend API에 연결된 예약 화면입니다.")
