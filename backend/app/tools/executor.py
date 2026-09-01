"""Allowlist Tool을 찾아 입력 검증과 오류 표준화를 거쳐 안전하게 실행합니다.

`agent_orchestration_service`가 모든 Tool 실행에 사용합니다. 모델이 반환한 이름을
그대로 실행하지 않고 `TOOL_REGISTRY`에 등록된 Tool만 실행합니다.
"""

from dataclasses import dataclass, field
from typing import Any

from pydantic import ValidationError

from app.tools.registry import TOOL_REGISTRY


@dataclass
class ToolRunResult:
    success: bool
    tool_name: str
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None


def execute_tool_safely(name: str, arguments: dict) -> ToolRunResult:
    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        return ToolRunResult(success=False, tool_name=name, error={"code": "TOOL_NOT_ALLOWED", "message": "허용되지 않은 Tool입니다."})
    try:
        return ToolRunResult(success=True, tool_name=name, data=tool.execute(arguments))
    except ValidationError as error:
        details = [{"field": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in error.errors()]
        return ToolRunResult(success=False, tool_name=name, error={"code": "TOOL_VALIDATION_ERROR", "details": details})
    except Exception as error:  # noqa: BLE001 — Tool 실행 실패를 표준 오류로 변환
        return ToolRunResult(success=False, tool_name=name, error={"code": "TOOL_EXECUTION_ERROR", "message": str(error)})
