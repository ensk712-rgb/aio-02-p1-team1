"""운영 Tool 입력 검증 모델 (작업지시서 v1.1 4.1절).

- strict=True: 숫자·목록 등을 문자열로 조용히 변환하지 않는다 (A-05: current=123 등 차단).
- extra="forbid": 정의되지 않은 추가 필드를 거절한다.
- 위치 문자열은 공백 제거 후 1~100자.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator


class FeedingScheduleInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    habitat: str = Field(min_length=1, max_length=100)

    @field_validator("habitat")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("habitat은 공백만으로 구성될 수 없다")
        return stripped


class ClosureStatusInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    habitat: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator("habitat")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("habitat은 공백만으로 구성될 수 없다")
        return stripped


class RouteInput(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")

    current: str = Field(min_length=1, max_length=100)
    destination: str = Field(min_length=1, max_length=100)

    @field_validator("current", "destination")
    @classmethod
    def _strip(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("위치 이름은 공백만으로 구성될 수 없다")
        return stripped
