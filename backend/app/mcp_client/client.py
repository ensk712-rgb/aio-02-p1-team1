"""Streamable HTTP MCP Client adapter."""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import timedelta
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import ValidationError

from backend.app.schemas.tools import ToolRunResult


class McpResultError(RuntimeError):
    """MCP 응답을 안전한 Tool 결과로 변환할 수 없을 때 발생한다."""


class McpClient:
    def __init__(self, server_url: str, *, timeout_seconds: float = 10) -> None:
        self._server_url = server_url
        self._read_timeout = timedelta(seconds=timeout_seconds)

    @asynccontextmanager
    async def _session(self) -> AsyncIterator[ClientSession]:
        async with streamable_http_client(self._server_url) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(
                read_stream,
                write_stream,
                read_timeout_seconds=self._read_timeout,
            ) as session:
                await session.initialize()
                yield session

    async def list_tools(self) -> list[dict[str, Any]]:
        async with self._session() as session:
            response = await session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolRunResult:
        async with self._session() as session:
            response = await session.call_tool(name, arguments=arguments)

        return self.parse_tool_response(response)

    @staticmethod
    def parse_tool_response(response: Any) -> ToolRunResult:
        """SDK 응답을 공통 계약으로 변환한다. 테스트에서 오류 응답을 직접 주입한다."""
        if response.isError:
            raise McpResultError("MCP Tool 실행이 실패했습니다.")

        text_parts = [
            item.text for item in response.content if getattr(item, "type", None) == "text"
        ]
        if len(text_parts) != 1:
            raise McpResultError("MCP Tool 결과 형식이 올바르지 않습니다.")

        try:
            payload = json.loads(text_parts[0])
            return ToolRunResult.model_validate(payload)
        except (json.JSONDecodeError, TypeError, ValidationError) as error:
            raise McpResultError("MCP Tool 결과 계약이 올바르지 않습니다.") from error

    async def check_health(self) -> bool:
        try:
            await self.list_tools()
        except Exception:
            return False
        return True
