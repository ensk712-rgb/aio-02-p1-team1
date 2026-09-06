from types import SimpleNamespace

import pytest

import backend.app.mcp_client.client as client_module
from backend.app.mcp_client.client import McpClient


def test_client_normalizes_json_text_result() -> None:
    raw = SimpleNamespace(isError=False, structuredContent=None, content=[SimpleNamespace(text='{"success":true,"data":{"items":[]},"error":null,"source":"mock_zoo_operations","retrieved_at":"2026-09-06T10:00:00+09:00"}')])
    result = McpClient()._normalize_result(raw)
    assert result.success is True
    assert result.data == {"items": []}


def test_client_rejects_invalid_json_without_leaking_payload() -> None:
    raw = SimpleNamespace(isError=False, structuredContent=None, content=[SimpleNamespace(text="secret-not-json")])
    result = McpClient()._normalize_result(raw)
    assert result.success is False
    assert result.error["code"] == "MCP_TOOL_ERROR"
    assert "secret-not-json" not in result.error["message"]


@pytest.mark.anyio
async def test_timeout_retries_once_then_returns_error(monkeypatch) -> None:
    attempts = 0

    class TimeoutContext:
        async def __aenter__(self):
            nonlocal attempts
            attempts += 1
            raise TimeoutError

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(client_module, "streamable_http_client", lambda _: TimeoutContext())
    result = await McpClient(retries=1).call_tool("get_feeding_schedule", {"habitat": "해양관"})
    assert attempts == 2
    assert result.success is False
    assert result.error["code"] == "MCP_TIMEOUT"
