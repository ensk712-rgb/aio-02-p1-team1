"""레인저 에이전트 MVP 챗봇 — RAG 답변, Tool 조회, 예약 승인 흐름을 한 화면에서 확인합니다.

실행: streamlit run frontend/app.py  (backend가 http://127.0.0.1:8000 에서 먼저 떠 있어야 합니다)
"""

import uuid

import httpx
import streamlit as st

BACKEND_URL = "http://127.0.0.1:8000"

st.set_page_config(page_title="레인저 에이전트", page_icon="🦁")
st.title("🦁 레인저 에이전트")
st.caption("동물원 안내를 사육사에게 묻듯이 물어보세요 · MVP")

if "session_id" not in st.session_state:
    st.session_state.session_id = f"guest-{uuid.uuid4().hex[:8]}"
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_action" not in st.session_state:
    st.session_state.pending_action = None


def call_ask(message: str) -> dict:
    response = httpx.post(
        f"{BACKEND_URL}/api/agent/ask",
        json={"message": message, "session_id": st.session_state.session_id},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


def call_confirm(action_id: str) -> dict:
    response = httpx.post(
        f"{BACKEND_URL}/api/agent/confirm",
        json={"action_id": action_id, "session_id": st.session_state.session_id},
        timeout=60,
    )
    response.raise_for_status()
    return response.json()


for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])
        if msg.get("tag"):
            st.caption(msg["tag"])

if st.session_state.pending_action:
    action = st.session_state.pending_action
    with st.chat_message("assistant"):
        st.write(action["summary"])
        col1, col2 = st.columns(2)
        if col1.button("확인", key=f"confirm-{action['action_id']}", use_container_width=True):
            result = call_confirm(action["action_id"])
            st.session_state.messages.append({"role": "assistant", "content": result["final_answer"]})
            st.session_state.pending_action = None
            st.rerun()
        if col2.button("취소", key=f"cancel-{action['action_id']}", use_container_width=True):
            st.session_state.messages.append({"role": "assistant", "content": "예약을 취소했어요."})
            st.session_state.pending_action = None
            st.rerun()

if prompt := st.chat_input("사육사에게 묻듯이 물어보세요"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    try:
        result = call_ask(prompt)
    except httpx.HTTPError as error:
        result = {
            "status": "error",
            "final_answer": f"백엔드에 연결할 수 없어요: {error}",
            "sources": [],
            "tool_call": None,
            "pending_action": None,
        }

    if result["status"] == "confirmation_required":
        st.session_state.pending_action = result["pending_action"]
    else:
        tag = None
        if result.get("sources"):
            tag = "RAG · " + ", ".join(s["title"] for s in result["sources"])
        elif result.get("tool_call"):
            tag = "TOOL · " + result["tool_call"]["name"]
        st.session_state.messages.append({"role": "assistant", "content": result["final_answer"], "tag": tag})
    st.rerun()
