"""P1 확장 조회 Tool을 MCP에 노출하는 얇은 wrapper (작업지시서 v1.1 11.4절)."""

from __future__ import annotations

from typing import Any

from backend.app.tools.zoo_tools import lookup_ticket_scope as _lookup_ticket_scope


def lookup_ticket_scope(ticket_type: str) -> dict[str, Any]:
    """티켓 종류의 관람 가능 범위(포함/제외 전시관)를 교육용 운영 데이터에서 조회한다."""
    return _lookup_ticket_scope(ticket_type).model_dump(mode="json")
