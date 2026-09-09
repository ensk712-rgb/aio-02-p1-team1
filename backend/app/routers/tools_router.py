"""GET /api/tools/* 조회 전용 엔드포인트.

P1-B 맞춤 코스 추천 계획서 §11.4(3차 회의 확정)의 (A)안 구현이다.
Agent/LLM을 거치지 않고 Backend가 zoo_tools.py 함수를 직접 실행해
구조화된 ToolRunResult를 그대로 반환한다 — 지도·동선 화면(§11, 14·15단계)이
자연어 없이 결정적으로 Tool 결과를 얻을 때 이 엔드포인트를 쓴다.

read Tool만 노출하므로 인증 없이 게스트도 호출 가능하다(v0.4 §15.1의
/api/agent/ask와 동일한 수준의 접근 허용).
"""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, File, HTTPException, Query, UploadFile, status

from backend.app.schemas.common import ToolRunResult
from backend.app.services import vision_service
from backend.app.tools import zoo_tools
from backend.app.tools.course_weather_policy import recommend_course_with_weather

CourseScope = Literal["all", "indoor_only", "outdoor_only"]


def create_tools_router() -> APIRouter:
    """조회 전용 Tool 2종을 REST로 직접 호출하는 Router를 만든다."""
    router = APIRouter(tags=["tools"])

    @router.get("/api/tools/habitat-route", response_model=ToolRunResult)
    async def habitat_route(current: str, destination: str) -> ToolRunResult:
        """find_habitat_route를 그대로 호출한다(§11.4)."""
        return zoo_tools.find_habitat_route(current, destination)

    @router.get("/api/tools/closure-status", response_model=ToolRunResult)
    async def closure_status(habitat: str | None = None) -> ToolRunResult:
        """check_closure_status를 그대로 호출한다.

        §11.4 표에는 명시돼 있지 않지만, §11.3 "휴장 상태 반영"이 지도 화면(15단계)
        요구사항으로 못박혀 있고 check_closure_status를 노출하는 다른 경로가
        없다 — habitat-route/course-info 2종만으로는 휴장 여부를 알 수 없어
        REST로 추가한다(기존 명명 규칙을 따름).
        """
        return zoo_tools.check_closure_status(habitat)

    @router.get("/api/tools/course-info", response_model=ToolRunResult)
    async def course_info(
        available_minutes: int,
        child_accompanying: bool = False,
        current: str = "정문",
        scope: CourseScope | None = Query(
            default=None,
            description=(
                "생략하면 §6.2와 동일한 로직으로 날씨를 선조회해 "
                "get_course_info 또는 get_indoor_course_info 중 하나를 호출한다. "
                "명시하면 날씨와 무관하게 해당 facility_scope의 Tool을 직접 호출한다."
            ),
        ),
    ) -> ToolRunResult:
        """scope 생략 시 §6.2와 같은 Runtime 로직을 재사용해 날씨 기반으로
        get_course_info/get_indoor_course_info 중 하나를 고른다(DRY, §11.4) —
        그렇지 않으면 지도 화면과 채팅 화면이 같은 조건에서 다른 코스를 보여줄
        수 있다. scope="outdoor_only"를 명시하면 날씨와 무관하게
        get_outdoor_course_info를 직접 호출한다(§5.2.3).
        """
        if scope == "all":
            return zoo_tools.get_course_info(available_minutes, child_accompanying, current)
        if scope == "indoor_only":
            return zoo_tools.get_indoor_course_info(
                available_minutes, child_accompanying, current
            )
        if scope == "outdoor_only":
            return zoo_tools.get_outdoor_course_info(
                available_minutes, child_accompanying, current
            )
        return await recommend_course_with_weather(
            available_minutes=available_minutes,
            child_accompanying=child_accompanying,
            current=current,
        )

    @router.get("/api/tools/public-weather", response_model=ToolRunResult)
    async def public_weather(region: str = "서울") -> ToolRunResult:
        """현재 날씨와 5일 예보를 사용자 화면에 제공한다."""
        return zoo_tools.lookup_public_weather(region)

    @router.post("/api/tools/animal-image-analysis", response_model=ToolRunResult)
    async def animal_image_analysis(image: UploadFile = File(...)) -> ToolRunResult:
        """업로드된 사진을 Vision 모델로 분석해 동물 설명을 반환한다(이미지 인식 분석)."""
        content_type = image.content_type or ""
        if not content_type.startswith("image/"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미지 파일만 업로드할 수 있습니다.",
            )
        image_bytes = await image.read()
        return await vision_service.analyze_animal_image(
            image_bytes, content_type=content_type
        )

    return router
