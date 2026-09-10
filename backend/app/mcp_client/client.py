"""Streamable HTTP MCP Client adapter."""

from __future__ import annotations

import asyncio
import json
from datetime import timedelta
from typing import Any

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from pydantic import ValidationError

from backend.app.schemas.tools import ToolRunResult


class McpResultError(RuntimeError):
    """MCP 응답을 안전한 Tool 결과로 변환할 수 없을 때 발생한다."""


class McpClient:
    """MCP 서버 연결을 지연 생성해 재사용하는 클라이언트.

    호출마다 세션을 새로 열고 닫으면(초기화 핸드셰이크 + TCP 연결을 매번
    반복하면), mcp SDK가 처음 보는 Tool마다 자동으로 다시 보내는 출력 스키마
    재검증용 ``list_tools()`` 요청과 겹쳐 응답이 오지 않고 그대로 멈추는
    현상이 관찰되었다(연속 호출 5~6번째부터 10초 이상 응답 없음, mcp
    1.27.0~1.30.0 전체에서 재현). 세션을 프로세스 생명주기 동안 하나만 열어
    재사용하면 재현되지 않는다.

    ``streamable_http_client``는 내부적으로 anyio TaskGroup을 쓰는데,
    TaskGroup은 "진입한 태스크에서만 종료할 수 있다"는 제약이 있다. 이
    클라이언트는 FastAPI 앱 시작 시 한 번 만들어져 이후 요청마다 다른
    asyncio Task에서 호출되므로, 세션을 연 태스크와 (재연결 등으로) 닫는
    태스크가 달라질 수 있다. 그래서 세션의 진입·종료를 전담하는 별도
    태스크(``_owner``)를 하나 띄워 계속 살려두고, 다른 태스크들은 신호
    (``asyncio.Event``)로만 열고 닫기를 요청한다.
    """

    def __init__(self, server_url: str, *, timeout_seconds: float = 10) -> None:
        self._server_url = server_url
        self._read_timeout = timedelta(seconds=timeout_seconds)
        self._owner_task: asyncio.Task[None] | None = None
        self._session: ClientSession | None = None
        self._ready = asyncio.Event()
        self._closing = asyncio.Event()
        self._connect_error: BaseException | None = None
        self._connect_lock = asyncio.Lock()

    async def _owner(self, ready: asyncio.Event, closing: asyncio.Event) -> None:
        """세션을 열고, 닫힘 신호가 올 때까지 같은 태스크에서 세션을 붙들고 있는다."""
        try:
            async with streamable_http_client(self._server_url) as streams:
                read_stream, write_stream, _ = streams
                async with ClientSession(
                    read_stream,
                    write_stream,
                    read_timeout_seconds=self._read_timeout,
                ) as session:
                    await session.initialize()
                    self._session = session
                    ready.set()
                    await closing.wait()
        except BaseException as error:  # noqa: BLE001 - 호출부(_get_session)로 그대로 전달한다
            self._connect_error = error
            ready.set()
        finally:
            self._session = None

    async def _get_session(self) -> ClientSession:
        async with self._connect_lock:
            if self._owner_task is None or self._owner_task.done():
                self._connect_error = None
                self._ready = asyncio.Event()
                self._closing = asyncio.Event()
                self._owner_task = asyncio.create_task(
                    self._owner(self._ready, self._closing)
                )
            ready = self._ready

        await ready.wait()
        if self._connect_error is not None:
            error, self._connect_error = self._connect_error, None
            raise error
        assert self._session is not None
        return self._session

    async def _reset_session(self) -> None:
        """세션을 폐기한다 — 다음 호출은 새 연결로 재시도한다.

        세션을 연 태스크(``_owner``)에게 닫힘 신호만 보내고, 그 태스크가
        스스로(같은 태스크 안에서) 세션을 정리하도록 기다린다.
        """
        async with self._connect_lock:
            owner_task, self._owner_task = self._owner_task, None
            closing = self._closing
        if owner_task is not None and not owner_task.done():
            closing.set()
            await owner_task
        self._session = None

    async def aclose(self) -> None:
        """앱 종료 시(또는 테스트 정리 시) 열려 있는 연결을 닫는다."""
        await self._reset_session()

    async def list_tools(self) -> list[dict[str, Any]]:
        try:
            session = await self._get_session()
            response = await session.list_tools()
        except Exception:
            await self._reset_session()
            raise
        return [
            {
                "name": tool.name,
                "description": tool.description or "",
                "input_schema": tool.inputSchema,
            }
            for tool in response.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> ToolRunResult:
        try:
            session = await self._get_session()
            response = await session.call_tool(name, arguments=arguments)
        except Exception:
            await self._reset_session()
            raise

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
