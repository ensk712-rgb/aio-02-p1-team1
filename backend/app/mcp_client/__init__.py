"""MCP SDK 객체를 Backend 계약으로 감추는 Client adapter."""

from .client import McpClient, ToolRunResult

__all__ = ["McpClient", "ToolRunResult"]
