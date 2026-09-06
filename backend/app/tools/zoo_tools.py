"""동물원 조회·예약 Tool 5종의 입력 모델과 함수입니다.

데이터는 MVP용 In-memory Mock입니다 (`docs/04_pending-action-and-confirmation.md`와 같은
패턴 — 실제 서비스 확장 시 DB로 교체). 함수는 각각 조회 또는 상태 변경 하나만 합니다.
"""

from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

# ---------- Mock 데이터 ----------

FEEDING_SCHEDULE: dict[str, dict] = {
    "해양관": {"animal": "물개", "time": "14:30", "location": "해양관 2층 관람대"},
    "맹수사": {"animal": "호랑이", "time": "11:00", "location": "맹수사 정문 앞"},
    "판다관": {"animal": "판다", "time": "10:30", "location": "판다관 실내 전시장"},
}

CLOSURE_STATUS: dict[str, str] = {
    "맹수사": "청소로 인한 임시휴장 (14:00 재개 예정)",
}

ROUTE_MINUTES: dict[tuple[str, str], int] = {
    ("정문", "판다관"): 5,
    ("정문", "해양관"): 12,
    ("정문", "맹수사"): 8,
    ("정문", "야행성동물관"): 15,
}

TICKET_SCOPE: dict[str, dict] = {
    "기본권": {"night_open": False, "experience_included": False},
    "종합이용권": {"night_open": True, "experience_included": True},
    "야간권": {"night_open": True, "experience_included": False},
}

EXPERIENCE_PROGRAMS: dict[str, dict] = {
    "사육사체험": {"capacity_per_slot": 10},
}
_RESERVED: dict[str, int] = {}


# ---------- 입력 모델 ----------

class FeedingScheduleInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habitat: str = Field(description="동물사 이름, 예: 해양관")


class ClosureStatusInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    habitat: str | None = Field(default=None, description="특정 동물사 이름. 비우면 전체 휴장 목록을 반환")


class HabitatRouteInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current: str = Field(default="정문", description="현재 위치")
    destination: str = Field(description="목적지 동물사 이름")


class TicketScopeInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticket_type: str = Field(description="티켓 종류, 예: 종합이용권")


class ReserveExperienceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    program: str = Field(description="체험 프로그램 이름, 예: 사육사체험")
    time: str = Field(description="예약 시각, 예: 15:00")
    headcount: int = Field(ge=1, le=20, description="인원 수")


# ---------- 함수 ----------

def get_feeding_schedule(args: FeedingScheduleInput) -> dict:
    entry = FEEDING_SCHEDULE.get(args.habitat)
    if entry is None:
        return {"found": False, "message": f"'{args.habitat}'은(는) 등록된 동물사가 아니에요.", "available_habitats": list(FEEDING_SCHEDULE)}
    return {"found": True, **entry}


def check_closure_status(args: ClosureStatusInput) -> dict:
    if args.habitat:
        reason = CLOSURE_STATUS.get(args.habitat)
        return {"habitat": args.habitat, "closed": reason is not None, "reason": reason}
    return {"closed_habitats": dict(CLOSURE_STATUS)}


def find_habitat_route(args: HabitatRouteInput) -> dict:
    minutes = ROUTE_MINUTES.get((args.current, args.destination))
    note = ""
    if minutes is None:
        minutes = ROUTE_MINUTES.get(("정문", args.destination))
        note = "정확한 출발지 경로 정보가 없어 정문 기준으로 안내해요." if minutes is not None else ""
    if minutes is None:
        return {"from": args.current, "to": args.destination, "found": False, "message": f"'{args.destination}' 경로 정보를 찾을 수 없어요."}
    return {"from": args.current, "to": args.destination, "found": True, "estimated_minutes": minutes, "note": note}


def lookup_ticket_scope(args: TicketScopeInput) -> dict:
    scope = TICKET_SCOPE.get(args.ticket_type)
    if scope is None:
        return {"found": False, "message": f"'{args.ticket_type}' 티켓 정보를 찾을 수 없어요. 매표소에 문의해 주세요.", "known_types": list(TICKET_SCOPE)}
    return {"found": True, "ticket_type": args.ticket_type, **scope}


def reserve_experience_program(args: ReserveExperienceInput) -> dict:
    program = EXPERIENCE_PROGRAMS.get(args.program)
    if program is None:
        return {"success": False, "message": f"'{args.program}' 프로그램이 없어요.", "known_programs": list(EXPERIENCE_PROGRAMS)}
    key = f"{args.program}|{args.time}"
    reserved = _RESERVED.get(key, 0)
    remaining = program["capacity_per_slot"] - reserved
    if args.headcount > remaining:
        return {"success": False, "message": f"정원이 초과되어 예약할 수 없어요. 남은 자리 {max(remaining, 0)}명.", "remaining": max(remaining, 0)}
    _RESERVED[key] = reserved + args.headcount
    return {
        "success": True,
        "reservation_id": f"EXP-{uuid4().hex[:6].upper()}",
        "program": args.program,
        "time": args.time,
        "headcount": args.headcount,
    }
