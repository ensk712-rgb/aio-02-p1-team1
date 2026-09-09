"""Zoo 운영 조회용 Streamable HTTP MCP Server."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from backend.app.core.config import get_settings
from mcp_server.tools.public_data import lookup_public_weather, lookup_ticket_scope
from mcp_server.tools.zoo_read import (
    check_closure_status,
    find_habitat_route,
    get_course_info,
    get_feeding_schedule,
    get_indoor_course_info,
    get_outdoor_course_info,
)


def create_mcp_server(*, host: str | None = None, port: int | None = None) -> FastMCP:
    settings = get_settings()
    server = FastMCP(
        "zoo-read",
        host=host or settings.MCP_HOST,
        port=port or settings.MCP_PORT,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
    )
    server.tool()(get_feeding_schedule)
    server.tool()(check_closure_status)
    server.tool()(find_habitat_route)
    server.tool()(lookup_ticket_scope)
    # P1-B 맞춤 코스 추천 Tool 4종 (계획서 §5.0, §5.2.1)
    server.tool()(get_course_info)
    server.tool()(get_indoor_course_info)
    server.tool()(get_outdoor_course_info)
    server.tool()(lookup_public_weather)
    return server


def main() -> None:
    create_mcp_server().run(transport="streamable-http")


if __name__ == "__main__":
    main()
