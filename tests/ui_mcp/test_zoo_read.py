from mcp_server.tools.zoo_read import check_closure_status, find_habitat_route, get_feeding_schedule


def test_three_read_wrappers_follow_result_contract() -> None:
    results = [get_feeding_schedule("해양관"), check_closure_status("맹수사"), find_habitat_route("정문", "해양관")]
    for result in results:
        assert result["success"] is True
        assert result["error"] is None
        assert result["source"] == "mock_zoo_operations"
        assert "+09:00" in result["retrieved_at"]


def test_unknown_route_is_explicit_error() -> None:
    result = find_habitat_route("정문", "없는관")
    assert result["success"] is False
    assert result["error"]["code"] == "ROUTE_NOT_FOUND"
