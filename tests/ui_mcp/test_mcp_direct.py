"""FastAPI Backend를 거치지 않는 실제 HTTP MCP 연결 시험."""

from __future__ import annotations

import os
import asyncio
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from backend.app.mcp_client.client import McpClient


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_PORT = 18100
TEST_URL = f"http://127.0.0.1:{TEST_PORT}/mcp"


def _wait_for_port(process: subprocess.Popen[str], timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"MCP Server가 조기 종료했습니다: {stdout} {stderr}")
        try:
            with socket.create_connection(("127.0.0.1", TEST_PORT), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError("MCP Server가 제한 시간 안에 시작되지 않았습니다.")


@pytest.fixture(scope="module")
def mcp_process():
    env = os.environ.copy()
    env.update(
        {
            "APP_MODE": "mock",
            "MCP_HOST": "127.0.0.1",
            "MCP_PORT": str(TEST_PORT),
        }
    )
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_port(process)
        yield process
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)


def test_list_tools_exposes_fixed_names_and_schemas(mcp_process) -> None:
    tools = asyncio.run(McpClient(TEST_URL).list_tools())
    by_name = {tool["name"]: tool for tool in tools}

    assert set(by_name) == {
        "get_feeding_schedule",
        "check_closure_status",
        "find_habitat_route",
        "lookup_public_weather",
    }
    assert by_name["get_feeding_schedule"]["input_schema"]["required"] == ["habitat"]
    assert by_name["check_closure_status"]["input_schema"].get("required", []) == []
    assert by_name["find_habitat_route"]["input_schema"]["required"] == [
        "current",
        "destination",
    ]
    assert by_name["lookup_public_weather"]["input_schema"]["required"] == ["region"]


def test_call_three_tools_returns_common_result_contract(mcp_process) -> None:
    calls = (
        ("get_feeding_schedule", {"habitat": "해양관"}),
        ("check_closure_status", {"habitat": "해양관"}),
        ("find_habitat_route", {"current": "정문", "destination": "해양관"}),
        ("lookup_public_weather", {"region": "서울"}),
    )

    async def call_and_assert() -> None:
        client = McpClient(TEST_URL)
        for name, arguments in calls:
            result = await client.call_tool(name, arguments)
            assert result.success is True, name
            assert result.data, name
            assert result.error is None, name
            expected_source = (
                "mock_public_weather"
                if name == "lookup_public_weather"
                else "mock_zoo_operations"
            )
            assert result.source == expected_source, name
            assert result.retrieved_at.utcoffset() is not None, name

    asyncio.run(call_and_assert())


def test_public_weather_returns_fixed_contract(mcp_process) -> None:
    async def call_and_assert() -> None:
        result = await McpClient(TEST_URL).call_tool(
            "lookup_public_weather",
            {"region": "서울"},
        )

        assert result.success is True
        assert set(result.data) == {"region", "condition", "as_of"}
        assert result.data["region"] == "서울"
        assert result.data["condition"] == "맑음"
        assert result.source == "mock_public_weather"
        assert result.retrieved_at.utcoffset() is not None

    asyncio.run(call_and_assert())
