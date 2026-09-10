"""홈 본문에 표시하는 AI 답변 이력과 단일 질문 처리 흐름."""

from __future__ import annotations

import streamlit as st

from frontend.bootstrap import AgentClientProtocol
from frontend.clients.agent_client import AgentClientError
from frontend.components.reservation import render_approval_notice, render_pending_reservation_action
from frontend.ui import render_agent_response


def _run_pending_question(client: AgentClientProtocol) -> None:
    question = st.session_state.pop("pending_question", None)
    if not isinstance(question, str) or not question.strip():
        return

    st.session_state.chat_status = "processing"
    st.session_state.messages.append({"role": "user", "content": question.strip()})
    with st.status("동물원 안내 정보를 확인하고 있습니다…", state="running") as status:
        try:
            streamed_text = ""
            response = None
            live_output = st.empty()
            for event in client.ask_stream(
                question.strip(), st.session_state.session_id,
                auth_session_id=st.session_state.auth_session_id,
            ):
                if event.get("event") == "delta":
                    streamed_text += str(event.get("data", {}).get("text", ""))
                    live_output.markdown(streamed_text + " ▌")
                elif event.get("event") == "done":
                    response = event.get("data")
                elif event.get("event") == "error":
                    raise AgentClientError(
                        str(event.get("data", {}).get("detail", "실시간 응답 오류")),
                        kind="stream",
                    )
            live_output.empty()
            if not isinstance(response, dict):
                raise AgentClientError("실시간 응답이 완료되지 않았습니다.", kind="stream")

            session_id = response.get("session_id")
            if isinstance(session_id, str) and session_id:
                st.session_state.session_id = session_id
            pending_action = response.get("pending_action")
            if isinstance(pending_action, dict):
                st.session_state.pending_reservation_action = pending_action
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
        render_approval_notice()

        with st.container(height=350, border=False, key="chat_history"):
            if not st.session_state.messages:
                with st.chat_message("assistant", avatar=":material/eco:"):
                    st.write("안녕하세요! 동물 정보, 먹이시간, 휴장 여부와 관람 경로를 물어보세요.")
                    st.caption("위 입력창이나 빠른 질문을 이용할 수 있어요.")
            for index, message in enumerate(st.session_state.messages):
                avatar = ":material/eco:" if message["role"] == "assistant" else ":material/person:"
                with st.chat_message(message["role"], avatar=avatar):
                    if message["role"] == "assistant":
                        response = message["response"]
                        render_agent_response(response, key_prefix=f"chat_{index}")
                        pending_action = response.get("pending_action")
                        active_action = st.session_state.get("pending_reservation_action")
                        if (
                            isinstance(pending_action, dict)
                            and isinstance(active_action, dict)
                            and pending_action.get("action_id") == active_action.get("action_id")
                        ):
                            render_pending_reservation_action(
                                client,
                                active_action,
                                key_prefix=f"chat_{index}",
                            )
                    else:
                        st.markdown(message["content"])
