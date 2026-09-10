"""업로드 이미지의 안전한 기본 시각 특성 분석 화면."""

from io import BytesIO

import streamlit as st
from PIL import Image, UnidentifiedImageError

from frontend.bootstrap import get_client
from frontend.clients.agent_client import AgentClientError
from frontend.components.layout import render_sidebar

render_sidebar("image")
st.title("이미지 인식 분석", icon=":material/image_search:")
st.caption("동물 사진을 올리면 이미지의 기본 특성을 분석하고 촬영 상태를 안내합니다.")

uploaded = st.file_uploader("분석할 이미지", type=["jpg", "jpeg", "png", "webp"], key="analysis_image")
if uploaded is None:
    st.info("JPG, PNG 또는 WEBP 이미지를 선택해 주세요. 최대 업로드 용량은 서버 설정을 따릅니다.")
else:
    try:
        raw = uploaded.getvalue()
        image = Image.open(BytesIO(raw))
        image.verify()
        image = Image.open(BytesIO(raw)).convert("RGB")
        preview, result = st.columns([1.35, 1], gap="large")
        with preview:
            st.image(image, caption=uploaded.name, width="stretch")
        with result:
            st.divider()
            st.subheader("AI 동물 종 분석")
            if st.button("AI로 동물 종 분석하기", icon=":material/smart_toy:", key="analyze_species"):
                with st.spinner("AI가 사진을 분석하고 있습니다…"):
                    try:
                        client = get_client()
                        result = client.analyze_animal_image(
                            raw,
                            filename=uploaded.name,
                            content_type=uploaded.type or "image/jpeg",
                        )
                    except AgentClientError as error:
                        st.error(f"이미지 분석 요청에 실패했습니다: {error}")
                    else:
                        if result.get("success"):
                            st.info(result.get("data", {}).get("analysis", "분석 결과가 비어 있습니다."))
                        else:
                            message = (result.get("error") or {}).get(
                                "message", "이미지 분석 중 오류가 발생했습니다."
                            )
                            st.error(message)
        st.caption("이미지 품질·색상 특성은 이 화면에서 바로 계산되고, 동물 종 분석은 'AI로 동물 종 분석하기' 버튼을 누르면 서버의 Vision 모델을 호출합니다.")
    except (UnidentifiedImageError, OSError, ValueError):
        st.error("올바른 이미지 파일을 읽을 수 없습니다. 다른 파일로 다시 시도해 주세요.")

