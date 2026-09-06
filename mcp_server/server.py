"""조회 Tool 3종을 Streamable HTTP로 제공하는 MCP Server."""

from mcp.server.fastmcp import FastMCP

from mcp_server.tools import zoo_read


def create_mcp_server() -> FastMCP:
    server = FastMCP(
        "zoo-read",
        instructions="교육용 동물원 운영 Mock 조회 Tool",
        host="127.0.0.1",
        port=8010,
        streamable_http_path="/mcp",
        json_response=True,
    )
    server.tool(description="특정 동물사의 다음 먹이시간과 장소를 조회합니다.")(zoo_read.get_feeding_schedule)
    server.tool(description="특정 동물사 또는 전체 동물원의 휴장 상태를 조회합니다.")(zoo_read.check_closure_status)
    server.tool(description="현재 위치에서 목적지 동물사까지의 경로를 조회합니다.")(zoo_read.find_habitat_route)
    return server


mcp = create_mcp_server()


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
