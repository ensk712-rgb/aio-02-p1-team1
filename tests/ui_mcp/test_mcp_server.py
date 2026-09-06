import pytest

from mcp_server.server import create_mcp_server


@pytest.mark.anyio
async def test_server_lists_exactly_three_read_tools() -> None:
    tools = await create_mcp_server().list_tools()
    assert {tool.name for tool in tools} == {"get_feeding_schedule", "check_closure_status", "find_habitat_route"}
    assert all(tool.inputSchema.get("properties") for tool in tools)
