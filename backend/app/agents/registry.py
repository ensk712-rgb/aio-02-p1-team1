"""Agent ID로 Agent Profile을 찾아주는 등록소를 구현한다."""

from backend.app.agents.models import AgentProfile
from backend.app.agents.zoo_guide_agent import create_zoo_guide_profile


_AGENT_PROFILES: dict[str, AgentProfile] = {
    "zoo_guide": create_zoo_guide_profile(),
}


def get_agent_profile(agent_id: str) -> AgentProfile:
    """Agent ID에 해당하는 Profile을 반환한다.

    등록되지 않은 ID는 조용히 기본 Agent로 바꾸지 않는다.
    호출자가 잘못된 Agent ID를 빠르게 발견하도록 KeyError를 발생시킨다.
    """
    try:
        return _AGENT_PROFILES[agent_id]
    except KeyError as error:
        raise KeyError(f"등록되지 않은 Agent ID입니다: {agent_id}") from error


def list_agent_profiles() -> tuple[AgentProfile, ...]:
    """등록된 모든 Agent Profile을 읽기 전용 튜플 형태로 반환한다."""
    return tuple(_AGENT_PROFILES.values())
