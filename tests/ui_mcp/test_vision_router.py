"""POST /api/tools/animal-image-analysis 계약을 검증한다."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.tools_router import create_tools_router
from backend.app.schemas.common import ToolError, ToolRunResult
from backend.app.services import vision_service


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(create_tools_router())
    return TestClient(app)


def test_animal_image_analysis_returns_success_envelope(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analyze(image_bytes: bytes, *, content_type: str) -> ToolRunResult:
        assert image_bytes
        assert content_type == "image/jpeg"
        return ToolRunResult(
            success=True,
            data={"analysis": "호랑이로 보입니다."},
            error=None,
            source="vision_animal_image",
            retrieved_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(vision_service, "analyze_animal_image", fake_analyze)

    response = _client().post(
        "/api/tools/animal-image-analysis",
        files={"image": ("tiger.jpg", b"fake-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["analysis"] == "호랑이로 보입니다."


def test_animal_image_analysis_reports_analyzer_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_analyze(image_bytes: bytes, *, content_type: str) -> ToolRunResult:
        return ToolRunResult(
            success=False,
            data={},
            error=ToolError(code="VISION_ANALYSIS_ERROR", message="이미지 분석 중 오류가 발생했습니다."),
            source="vision_animal_image",
            retrieved_at=datetime.now(timezone.utc),
        )

    monkeypatch.setattr(vision_service, "analyze_animal_image", fake_analyze)

    response = _client().post(
        "/api/tools/animal-image-analysis",
        files={"image": ("tiger.jpg", b"fake-bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "VISION_ANALYSIS_ERROR"


def test_animal_image_analysis_rejects_non_image_content_type() -> None:
    response = _client().post(
        "/api/tools/animal-image-analysis",
        files={"image": ("note.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
