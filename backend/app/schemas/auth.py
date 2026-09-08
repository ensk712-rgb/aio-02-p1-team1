"""최소 로그인 API 계약."""

from pydantic import BaseModel, ConfigDict, Field, StrictStr


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    user_id: StrictStr = Field(min_length=1, max_length=50)
    password: StrictStr = Field(min_length=1, max_length=100)


class LoginResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    success: bool
    user_id: str
    role: str
    auth_session_id: str
