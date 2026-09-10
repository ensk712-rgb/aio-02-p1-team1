"""Agent 응답을 안전하게 표시하는 Streamlit UI 함수."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

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

CLIENT_ERROR_LABELS = {
    "connection": ("서버 연결 실패", ":material/cloud_off:"),
    "timeout": ("응답 지연", ":material/timer_off:"),
    "http": ("API 요청 실패", ":material/http:"),
    "invalid_response": ("응답 형식 오류", ":material/data_alert:"),
}

TOOL_LABELS = {
    "retrieve_animal_info": "동물 정보 검색",
    "get_feeding_schedule": "먹이주기 일정 조회",
    "get_habitat_route": "관람 경로 조회",
    "get_closure_status": "시설 운영 여부 조회",
    "lookup_public_weather": "날씨 정보 조회",
    "reserve_experience_program": "체험 예약 요청",
}


def render_agent_response(response: dict[str, Any], *, key_prefix: str = "response") -> None:
    status = str(response.get("status", "error"))
    label, color = STATUS_LABELS.get(status, ("알 수 없는 상태", "red"))
    error_kind = response.get("error_kind")
    error_icon = ":material/error:"
    if status == "error" and isinstance(error_kind, str):
        label, error_icon = CLIENT_ERROR_LABELS.get(error_kind, (label, error_icon))
    st.badge(label, color=color)

    answer = response.get("final_answer")
    if not isinstance(answer, str) or not answer.strip():
        answer = "표시할 답변이 없습니다. 다시 질문해 주세요."

    if status == "completed":
        st.markdown(answer)
    elif status == "needs_clarification":
        st.warning(answer, icon=":material/help:")
    elif status == "confirmation_required":
        st.info(answer, icon=":material/fact_check:")
    elif status in {"rejected", "stopped"}:
        st.warning(answer, icon=":material/shield:")
    else:
        st.error(answer, icon=error_icon)

    render_sources(response.get("sources", []), key_prefix=key_prefix)
    render_tool_calls(response.get("tool_calls", []), key_prefix=key_prefix)


def render_sources(sources: Any, *, key_prefix: str = "response") -> None:
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
                key=f"{key_prefix}_source_cards",
            )


def render_tool_calls(tool_calls: Any, *, key_prefix: str = "response") -> None:
    if not isinstance(tool_calls, list):
        return
    for index, call in enumerate(tool_calls):
        if not isinstance(call, dict):
            continue
        result = call.get("result") if isinstance(call.get("result"), dict) else {}
        success = result.get("success") is True
        title = "운영 정보 확인" if success else "운영 정보 조회 실패"
        icon = ":material/directions_walk:" if success else ":material/error:"
        with st.container(border=True, key=f"{key_prefix}_tool_card_{index}"):
            st.subheader(title, icon=icon)
            tool_name = str(call.get("name", ""))
            st.caption(f"확인 항목 · {TOOL_LABELS.get(tool_name, '기타 운영 정보')}")
            if success:
                data = result.get("data") if isinstance(result.get("data"), dict) else {}
                displayed = _display_data(data)
                if displayed:
                    st.table(displayed, border="horizontal")

                pending_action = data.get("pending_action")
                if isinstance(pending_action, dict):
                    st.markdown("**진행현황**")
                    st.table(_pending_action_rows(pending_action), border="horizontal")

                chunks = data.get("chunks")
                if isinstance(chunks, list) and chunks:
                    safe_chunks = [_display_data(chunk) for chunk in chunks if isinstance(chunk, dict)]
                    if safe_chunks:
                        st.markdown("**검색 자료**")
                        st.dataframe(
                            pd.DataFrame(safe_chunks),
                            hide_index=True,
                            key=f"{key_prefix}_tool_chunks_{index}",
                        )
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
        "matched": "검색 결과",
        "chunks": "검색 자료",
        "doc_id": "자료 ID",
        "title": "자료명",
        "page": "페이지",
        "text": "내용",
        "score": "관련도",
        "collection": "자료 분류",
        "query": "검색어",

        "pending_action": "진행현황",
    }
    displayed: dict[str, str] = {}
    for key, value in data.items():
        if key in {"as_of", "chunks", "pending_action"}:
            continue
        if key == "matched" and isinstance(value, bool):
            normalized = "일치하는 정보 있음" if value else "일치하는 정보 없음"
        elif isinstance(value, bool):
            normalized = "예" if value else "아니요"
        elif isinstance(value, list):
            normalized = " → ".join(str(item) for item in value)
        elif value is None:
            normalized = "없음"
        else:
            normalized = str(value)
        displayed[labels.get(key, key)] = normalized
    return displayed


def _format_kst(raw_value: object) -> str:
    if not isinstance(raw_value, str):
        return "확인 불가"
    try:
        parsed = datetime.fromisoformat(raw_value.replace("Z", "+00:00"))
    except ValueError:
        return raw_value
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(ZoneInfo("Asia/Seoul")).strftime("%Y-%m-%d %H:%M:%S KST")


def _pending_action_rows(action: dict[str, Any]) -> pd.DataFrame:
    labels = {
        "action_id": "요청 ID",
        "tool_name": "요청 종류",
        "summary": "예약 내용",
        "approval_status": "진행 상태",
        "expires_at": "확인 만료 시각",
    }
    tool_labels = {"reserve_experience_program": "체험 예약 요청"}
    status_labels = {
        "pending": "확인 대기",
        "processing": "처리 중",
        "completed": "확인 완료",
        "cancelled": "취소",
        "expired": "만료",
    }
    rows = []
    for key in ("action_id", "tool_name", "summary", "approval_status", "expires_at"):
        if key not in action:
            continue
        value = action[key]
        if key == "tool_name":
            value = tool_labels.get(str(value), str(value))
        elif key == "approval_status":
            value = status_labels.get(str(value), str(value))
        elif key == "expires_at":
            value = _format_kst(value)
        rows.append({"항목": labels[key], "내용": value})
    return pd.DataFrame(rows)
