"""Agent 응답을 안전하게 표시하는 Streamlit UI 함수."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st


STATUS_LABELS = {
    "completed": ("확인 완료", "green"),
    "needs_clarification": ("정보 필요", "orange"),
    "confirmation_required": ("확인 대기", "orange"),
    "rejected": ("요청 차단", "red"),
    "stopped": ("안전 중단", "orange"),
    "error": ("조회 실패", "red"),
}


def render_agent_response(response: dict[str, Any], *, key_prefix: str = "live") -> None:
    status = str(response.get("status", "error"))
    label, color = STATUS_LABELS.get(status, ("알 수 없는 상태", "red"))
    st.badge(label, color=color)

    answer = response.get("final_answer")
    if not isinstance(answer, str) or not answer.strip():
        answer = "표시할 답변이 없습니다. 다시 질문해 주세요."

    if status == "completed":
        st.markdown(answer)
    elif status == "needs_clarification":
        st.warning(answer, icon=":material/help:")
    elif status in {"rejected", "stopped"}:
        st.warning(answer, icon=":material/shield:")
    else:
        st.error(answer, icon=":material/error:")

    render_sources(response.get("sources", []), key_prefix=key_prefix)
    render_tool_calls(response.get("tool_calls", []), key_prefix=key_prefix)


def render_sources(sources: Any, *, key_prefix: str = "live") -> None:
    if not isinstance(sources, list) or not sources:
        return
    with st.expander("확인한 동물 정보", icon=":material/menu_book:"):
        safe_rows = []
        for source in sources:
            if not isinstance(source, dict):
                continue
            safe_rows.append(
                {
                    "자료": source.get("title", "제목 없음"),
                    "페이지": source.get("page"),
                    "관련도": source.get("score"),
                }
            )
        if safe_rows:
            st.dataframe(
                pd.DataFrame(safe_rows),
                hide_index=True,
                column_config={
                    "관련도": st.column_config.ProgressColumn(
                        "관련도", min_value=0.0, max_value=1.0, format="%.2f"
                    )
                },
                key=f"source_cards_{key_prefix}",
            )


def render_tool_calls(tool_calls: Any, *, key_prefix: str = "live") -> None:
    if not isinstance(tool_calls, list):
        return
    for index, call in enumerate(tool_calls):
        if not isinstance(call, dict):
            continue
        result = call.get("result") if isinstance(call.get("result"), dict) else {}
        success = result.get("success") is True
        title = "운영 정보 확인" if success else "운영 정보 조회 실패"
        icon = ":material/directions_walk:" if success else ":material/error:"
        with st.container(border=True, key=f"tool_card_{key_prefix}_{index}"):
            st.subheader(title, icon=icon)
            st.caption(f"사용 도구 · {call.get('name', '알 수 없음')}")
            if success:
                data = result.get("data") if isinstance(result.get("data"), dict) else {}
                st.table(_display_data(data), border="horizontal")
                st.caption(
                    f"자료 기준: {data.get('as_of', '확인 불가')} · "
                    f"조회 시각: {result.get('retrieved_at', '확인 불가')} · "
                    f"출처: {result.get('source', '확인 불가')}"
                )
            else:
                error = result.get("error") if isinstance(result.get("error"), dict) else {}
                st.error(
                    error.get("message", "운영 정보를 확인하지 못했습니다."),
                    icon=":material/error:",
                )


def _display_data(data: dict[str, Any]) -> dict[str, Any]:
    labels = {
        "habitat": "시설",
        "animal": "동물",
        "next_feeding_at": "다음 먹이시간",
        "location": "위치",
        "current": "출발",
        "destination": "도착",
        "path": "경로",
        "estimated_minutes": "예상 시간(분)",
    }
    displayed: dict[str, str] = {}
    for key, value in data.items():
        if key == "as_of":
            continue
        if isinstance(value, list):
            normalized = " → ".join(str(item) for item in value)
        elif value is None:
            normalized = "없음"
        else:
            normalized = str(value)
        displayed[labels.get(key, key)] = normalized
    return displayed
