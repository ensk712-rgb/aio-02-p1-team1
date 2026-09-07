"""zoo_guide Profile과 Agent 등록소의 계약을 검증한다."""

import pytest

from backend.app.agents.registry import get_agent_profile, list_agent_profiles


def test_zoo_guide_profile_has_p0_tools() -> None:
    """zoo_guide는 P0의 세 운영 조회 Tool을 허용해야 한다."""
    profile = get_agent_profile("zoo_guide")

    tool_names = {tool.name for tool in profile.allowed_tools}

    assert profile.agent_id == "zoo_guide"
    assert tool_names == {
        "get_feeding_schedule",
        "check_closure_status",
        "find_habitat_route",
    }


def test_zoo_guide_profile_allows_animal_cards_only() -> None:
    """P0 Agent는 animal_cards 컬렉션만 검색할 수 있어야 한다."""
    profile = get_agent_profile("zoo_guide")

    assert profile.allowed_rag_collections == ("animal_cards",)


def test_unknown_agent_id_is_rejected() -> None:
    """등록되지 않은 Agent ID를 기본 Profile로 대체하면 안 된다."""
    with pytest.raises(KeyError):
        get_agent_profile("unknown_agent")


def test_registry_contains_zoo_guide() -> None:
    """등록소 목록에는 zoo_guide가 포함되어야 한다."""
    profiles = list_agent_profiles()

    assert [profile.agent_id for profile in profiles] == ["zoo_guide"]