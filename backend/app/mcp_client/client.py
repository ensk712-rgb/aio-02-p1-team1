"""Streamable HTTP MCP Client와 오류 표준화."""

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import anyio
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


@dataclass(frozen=True)
class ToolRunResult:
    success: bool
    data: dict[str, Any] = field(default_factory=dict)
    error: dict[str, str] | None = None
    source: str = "mcp:zoo-read"
    retrieved_at: str = field(default_factory=lambda: datetime.now(ZoneInfo("Asia/Seoul")).isoformat())


class McpClient:
    def __init__(self, url: str | None = None, *, timeout_seconds: float = 5.0, retries: int = 1) -> None:
        self.url = url or os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8010/mcp")
        self.timeout_seconds = timeout_seconds
        self.retries = retries

    async def _session(self):
        return streamable_http_client(self.url)

    async def list_tools(self) -> list[dict[str, Any]]:
        async with streamable_http_client(self.url) as (read, write, _), ClientSession(read, write) as session:
            with anyio.fail_after(self.timeout_seconds):
                await session.initialize()
                result = await session.list_tools()
        return [
            {"name": tool.name, "description": tool.description or "", "input_schema": tool.inputSchema}
            for tool in result.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolRunResult:
        for attempt in range(self.retries + 1):
            try:
                async with streamable_http_client(self.url) as (read, write, _), ClientSession(read, write) as session:
                    with anyio.fail_after(self.timeout_seconds):
                        await session.initialize()
                        result = await session.call_tool(name, arguments, read_timeout_seconds=timedelta(seconds=self.timeout_seconds))
                return self._normalize_result(result)
            except (TimeoutError, OSError, anyio.BrokenResourceError):
                if attempt == self.retries:
                    return self._error("MCP_TIMEOUT", "MCP 조회 서버가 제한 시간 안에 응답하지 않았습니다.")
            except Exception:
                return self._error("MCP_UNAVAILABLE", "MCP 조회 서버를 사용할 수 없습니다.")
        return self._error("MCP_UNAVAILABLE", "MCP 조회 서버를 사용할 수 없습니다.")

    async def check_health(self) -> bool:
        try:
            tools = await self.list_tools()
        except Exception:
            return False
        return {tool["name"] for tool in tools} == {
            "get_feeding_schedule", "check_closure_status", "find_habitat_route"
        }

    def _normalize_result(self, result: Any) -> ToolRunResult:
        if getattr(result, "isError", False):
            return self._error("MCP_TOOL_ERROR", "MCP Tool 실행에 실패했습니다.")
        payload = getattr(result, "structuredContent", None)
        if payload is None:
            texts = [item.text for item in getattr(result, "content", []) if hasattr(item, "text")]
            if len(texts) != 1:
                return self._error("MCP_TOOL_ERROR", "MCP 결과 형식이 올바르지 않습니다.")
            try:
                payload = json.loads(texts[0])
            except (json.JSONDecodeError, TypeError):
                return self._error("MCP_TOOL_ERROR", "MCP 결과 JSON이 올바르지 않습니다.")
        if not isinstance(payload, dict) or not {"success", "data", "error", "source", "retrieved_at"} <= payload.keys():
            return self._error("MCP_TOOL_ERROR", "MCP 결과 필드가 누락되었습니다.")
        return ToolRunResult(
            success=bool(payload["success"]), data=payload["data"] or {}, error=payload["error"],
            source=str(payload["source"]), retrieved_at=str(payload["retrieved_at"]),
        )

    @staticmethod
    def _error(code: str, message: str) -> ToolRunResult:
        return ToolRunResult(success=False, error={"code": code, "message": message})
