"""기존 예약·승인 상태를 홈에서 재사용하는 컴포넌트."""

from datetime import datetime, timezone

import pandas as pd
import streamlit as st

from frontend.bootstrap import AgentClientProtocol
from frontend.clients.agent_client import AgentClientError


def _expiry_label(raw_value: object) -> str:
    if not isinstance(raw_value, str):
        return "확인 불가"
    try:
        value = datetime.fromisoformat(raw_value)
    except ValueError:
        return "확인 불가"
    return value.astimezone().strftime("%H:%M:%S")


def _remaining_seconds(raw_value: object) -> int | None:
    if not isinstance(raw_value, str):
        return None
    try:
        expires_at = datetime.fromisoformat(raw_value)
    except ValueError:
        return None
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    return max(0, int((expires_at - datetime.now(timezone.utc)).total_seconds()))


def _set_notice(message: object, *, level: str) -> None:
    st.session_state.approval_notice = {
        "message": str(message or "처리 결과를 확인해 주세요."),
        "level": level,
    }


def render_approval_notice() -> None:
    notice = st.session_state.get("approval_notice")
    if not notice:
        return
    if isinstance(notice, dict):
        message = str(notice.get("message", ""))
        level = notice.get("level")
    else:  # 이전 세션 값과의 호환
        message, level = str(notice), "info"
    if level == "error":
        st.error(message, icon=":material/gpp_bad:")
    elif level == "success":
        st.success(message, icon=":material/check_circle:")
    else:
        st.info(message, icon=":material/info:")
    st.caption("만료·소유권·중복 요청 여부는 서버가 최종 판정합니다.")
    st.session_state.approval_notice = None


def _progress_value(remaining: int) -> float:
    """Streamlit progress가 허용하는 0~1 범위로 값을 제한한다."""
    return min(1.0, max(0.0, remaining / 120))


def render_pending_reservation_action(
    client: AgentClientProtocol,
    action: dict[str, object],
    *,
    key_prefix: str = "reservation",
) -> None:
    """챗봇과 예약 탭에서 같은 예약 확인·취소 UI를 사용한다."""
    action_id = str(action.get("action_id", ""))
    if not action_id:
        st.warning("예약 요청 식별자를 확인할 수 없습니다.")
        return
    remaining = _remaining_seconds(action.get("expires_at"))
    locally_expired = remaining == 0
    with st.container(border=True, key=f"{key_prefix}_approval_card_{action_id}"):
        st.subheader("예약 내용을 확인해 주세요", icon=":material/verified_user:")
        st.write(str(action.get("summary", "예약 요청")))
        if remaining is None:
            st.warning("남은 시간을 계산할 수 없습니다. 서버 판정을 확인해 주세요.")
        elif locally_expired:
            st.warning("화면 기준 확인 시간이 지났습니다. 서버에서 최종 만료 여부를 확인합니다.", icon=":material/timer_off:")
        else:
            st.progress(_progress_value(remaining), text=f"확인 가능 시간 · {remaining}초 남음")
        st.caption(f"서버 만료 시각 · {_expiry_label(action.get('expires_at'))}")
        st.caption("확인 전에는 예약이 생성되거나 관리자에게 전달되지 않습니다.")
        with st.container(horizontal=True):
            locked = st.session_state.approval_processing or locally_expired
            button_prefix = "" if key_prefix == "reservation" else f"{key_prefix}_"
            confirm = st.button("확인", type="primary", icon=":material/check:", disabled=locked, key=f"{button_prefix}confirm_{action_id}")
            cancel = st.button("취소", icon=":material/close:", disabled=locked, key=f"{button_prefix}cancel_{action_id}")
        if confirm or cancel:
            st.session_state.approval_processing = True
            try:
                result = client.confirm_reservation(
                    st.session_state.auth_session_id,
                    action_id,
                    "confirm" if confirm else "cancel",
                )
                st.session_state.pending_reservation_action = None
                _set_notice(result.get("message"), level="success" if confirm else "info")
            except AgentClientError as error:
                st.session_state.pending_reservation_action = None
                _set_notice(error, level="error")
            finally:
                st.session_state.approval_processing = False
            st.rerun()


def render_reservation(client: AgentClientProtocol, *, expanded: bool = False) -> None:
    with st.expander("체험 예약 요청", icon=":material/event:", expanded=expanded):
        with st.form("reservation_request"):
            program = st.selectbox("프로그램", ["사육사 체험", "먹이주기 체험"], key="program")
            visit_time = st.selectbox("시간", ["11:00", "15:00"], key="visit_time")
            headcount = st.number_input("인원", min_value=1, max_value=10, value=1, key="headcount")
            submitted = st.form_submit_button("예약 내용 확인", icon=":material/send:", width="stretch")
        if submitted:
            try:
                result = client.create_reservation(st.session_state.auth_session_id, program=program, visit_time=visit_time, headcount=int(headcount))
                st.session_state.pending_reservation_action = result.get("pending_action")
                _set_notice(result.get("message"), level="info")
            except AgentClientError as error:
                _set_notice(error, level="error")

        render_approval_notice()

        action = st.session_state.get("pending_reservation_action")
        if isinstance(action, dict):
            render_pending_reservation_action(client, action)

        try:
            items = client.get_my_reservations(st.session_state.auth_session_id).get("items", [])
            if items:
                st.dataframe(pd.DataFrame(items)[["program", "visit_time", "headcount", "status"]], hide_index=True, key="my_reservations")
        except AgentClientError:
            st.warning("예약 현황을 불러올 수 없습니다.", icon=":material/warning:")
