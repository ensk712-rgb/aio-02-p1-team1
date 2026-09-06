"""Agent Profile을 구성하는 내부 데이터 모델을 정의한다."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.app.schemas.tools import RiskLevel


class AgentToolPolicy(BaseModel):
    """Agent가 사용할 수 있는 Tool 한 개의 정책 정보다."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1)
    risk: RiskLevel
    description: str = Field(min_length=1)


class AgentProfile(BaseModel):
    """한 Agent의 목표, 지침, 허용 기능을 묶은 불변 설정이다."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    agent_id: str = Field(min_length=1, description="Agent 고유 ID")
    name: str = Field(min_length=1, description="사람에게 보여 줄 Agent 이름")
    goal: str = Field(min_length=1, description="Agent의 최종 목적")
    description: str = Field(min_length=1, description="Agent의 역할 설명")
    example_questions: tuple[str, ...] = Field(
        default=(),
        description="Agent가 처리할 수 있는 대표 질문",
    )
    instructions: str = Field(min_length=1, description="Provider 행동 지침")
    allowed_tools: tuple[AgentToolPolicy, ...] = ()
    allowed_rag_collections: tuple[Literal["animal_cards"], ...] = ()