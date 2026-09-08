"""우측 고정형 AI 대화 패널과 단일 질문 처리 흐름."""

from __future__ import annotations

import streamlit as st

from frontend.bootstrap import AgentClientProtocol
from frontend.clients.agent_client import AgentClientError
from frontend.ui import render_agent_response


def _run_pending_question(client: AgentClientProtocol) -> None:
    question = st.session_state.pop("pending_question", None)
    if not isinstance(question, str) or not question.strip():
        return

    st.session_state.chat_status = "processing"
    st.session_state.messages.append({"role": "user", "content": question.strip()})
    with st.status("동물원 안내 정보를 확인하고 있습니다…", state="running") as status:
        try:
            response = client.ask(
                question.strip(),
                st.session_state.session_id,
                auth_session_id=st.session_state.auth_session_id,
            )

            session_id = response.get("session_id")
            if isinstance(session_id, str) and session_id:
                st.session_state.session_id = session_id
            st.session_state.messages.append({"role": "assistant", "response": response})
            st.session_state.chat_status = "ready"
            status.update(label="안내 정보를 확인했습니다.", state="complete")
        except AgentClientError as error:
            st.session_state.messages.append(
                {
                    "role": "assistant",
                    "response": {
                        "status": "error",
                        "final_answer": str(error),
                        "error_kind": error.kind,
                    },
                }
            )
            st.session_state.chat_status = "error"
            status.update(label="안내 정보를 가져오지 못했습니다.", state="error")


def render_chat_panel(client: AgentClientProtocol) -> None:
    with st.container(border=True, key="chat_panel"):
        with st.container(horizontal=True, vertical_alignment="center"):
            st.subheader("AI 가이드 챗봇", icon=":material/eco:")
            status = st.session_state.get("chat_status", "ready")
            if status == "processing":
                st.badge("확인 중", color="orange", icon=":material/progress_activity:")
            elif status == "error":
                st.badge("연결 확인", color="red", icon=":material/error:")
            else:
                st.badge("대화 가능", color="green", icon=":material/check_circle:")

        _run_pending_question(client)

        with st.container(height=350, border=False, key="chat_history"):
            if not st.session_state.messages:
                with st.chat_message("assistant", avatar=":material/eco:"):
                    st.write("안녕하세요! 동물 정보, 먹이시간, 휴장 여부와 관람 경로를 물어보세요.")
                    st.caption("아래 입력창이나 중앙의 빠른 질문을 이용할 수 있어요.")
            for index, message in enumerate(st.session_state.messages):
                avatar = ":material/eco:" if message["role"] == "assistant" else ":material/person:"
                with st.chat_message(message["role"], avatar=avatar):
                    if message["role"] == "assistant":
                        render_agent_response(message["response"], key_prefix=f"chat_{index}")
                    else:
                        st.markdown(message["content"])

        with st.form("chat_panel_form", border=False, clear_on_submit=True):
            question = st.text_input(
                "AI 가이드에게 질문하기",
                placeholder="메시지를 보내세요",
                label_visibility="collapsed",
                key="chat_message_input",
                max_chars=2000,
            )
            submitted = st.form_submit_button(
                "보내기",
                icon=":material/send:",
                width="stretch",
                disabled=st.session_state.get("chat_status") == "processing",
            )
        if submitted and question.strip():
            st.session_state.pending_question = question.strip()
            st.rerun()
