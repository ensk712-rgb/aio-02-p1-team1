"""최소 로그인 API 요청·응답 계약."""

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    user_id: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class LoginResponse(BaseModel):
    authenticated: bool
    user_id: str
