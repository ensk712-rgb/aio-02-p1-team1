"""예약 요청과 관리자 승인 API 계약."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class ReservationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    program: StrictStr = Field(min_length=1, max_length=100)
    visit_time: StrictStr = Field(min_length=1, max_length=50)
    headcount: int = Field(ge=1, le=10)


class ReservationDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]


class ReservationConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    action_id: StrictStr = Field(min_length=1)
    session_id: StrictStr = Field(min_length=1)
    decision: Literal["confirm", "cancel"]
