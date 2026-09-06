"""Tool의 이름·설명·입력 모델·실행 함수를 단일 명세로 등록합니다.

`agents.routing_agent`(Tool 정의 목록)와 `tools.executor`(안전 실행)가 사용합니다.
`requires_approval=True`인 Tool은 `agent_orchestration_service`가 즉시 실행하지 않고
승인 대기(pending action)로 돌립니다.
"""

from collections.abc import Callable
from dataclasses import dataclass

from pydantic import BaseModel

from app.tools.zoo_tools import (
    ClosureStatusInput,
    FeedingScheduleInput,
    HabitatRouteInput,
    ReserveExperienceInput,
    TicketScopeInput,
    check_closure_status,
    find_habitat_route,
    get_feeding_schedule,
    lookup_ticket_scope,
    reserve_experience_program,
)

ToolFunction = Callable[[BaseModel], dict]


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    input_model: type[BaseModel]
    function: ToolFunction
    requires_approval: bool = False

    def definition(self) -> dict:
        return {"name": self.name, "description": self.description, "input_schema": self.input_model.model_json_schema()}

    def execute(self, arguments: dict) -> dict:
        return self.function(self.input_model.model_validate(arguments))


TOOL_REGISTRY: dict[str, ToolSpec] = {
    "get_feeding_schedule": ToolSpec(
        name="get_feeding_schedule",
        description="특정 동물사의 다음 먹이시간과 장소를 조회합니다.",
        input_model=FeedingScheduleInput,
        function=get_feeding_schedule,
    ),
    "check_closure_status": ToolSpec(
        name="check_closure_status",
        description="특정 동물사 또는 전체 동물원의 임시 휴장 여부를 조회합니다.",
        input_model=ClosureStatusInput,
        function=check_closure_status,
    ),
    "find_habitat_route": ToolSpec(
        name="find_habitat_route",
        description="현재 위치에서 목적지 동물사까지 예상 소요 시간을 조회합니다.",
        input_model=HabitatRouteInput,
        function=find_habitat_route,
    ),
    "lookup_ticket_scope": ToolSpec(
        name="lookup_ticket_scope",
        description="티켓 종류별로 야간개장·체험 프로그램 포함 여부를 조회합니다.",
        input_model=TicketScopeInput,
        function=lookup_ticket_scope,
    ),
    "reserve_experience_program": ToolSpec(
        name="reserve_experience_program",
        description="체험 프로그램을 예약합니다. 정원이 있는 상태 변경 액션이라 사용자 확인이 필요합니다.",
        input_model=ReserveExperienceInput,
        function=reserve_experience_program,
        requires_approval=True,
    ),
}


def get_tool_definitions() -> list[dict]:
    return [tool.definition() for tool in TOOL_REGISTRY.values()]
