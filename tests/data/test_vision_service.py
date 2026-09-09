"""analyze_animal_image이 OpenAI Vision 응답을 ToolRunResult로 바꾸는지 검증한다."""

from __future__ import annotations

import pytest


class _FakeMessage:
    def __init__(self, content: str) -> None:
        self.content = content


class _FakeChoice:
    def __init__(self, content: str) -> None:
        self.message = _FakeMessage(content)


class _FakeChatResponse:
    def __init__(self, content: str) -> None:
        self.choices = [_FakeChoice(content)]


class FakeChatCompletionsApi:
    def __init__(self, *, content: str = "호랑이로 보입니다.", raise_error: bool = False) -> None:
        self.content = content
        self.raise_error = raise_error
        self.calls: list[dict] = []

    async def create(self, **kwargs) -> _FakeChatResponse:
        self.calls.append(kwargs)
        if self.raise_error:
            raise RuntimeError("일시적 Vision API 오류")
        return _FakeChatResponse(self.content)


class FakeChat:
    def __init__(self, completions: FakeChatCompletionsApi) -> None:
        self.completions = completions


class FakeVisionClient:
    def __init__(self, *, content: str = "호랑이로 보입니다.", raise_error: bool = False) -> None:
        self.chat = FakeChat(FakeChatCompletionsApi(content=content, raise_error=raise_error))


@pytest.mark.asyncio
async def test_analyze_animal_image_returns_success_result() -> None:
    from backend.app.services.vision_service import analyze_animal_image

    client = FakeVisionClient(content="호랑이로 보입니다. 줄무늬가 선명합니다.")
    result = await analyze_animal_image(
        b"fake-image-bytes", content_type="image/jpeg", client=client, model="gpt-4.1-mini"
    )

    assert result.success is True
    assert result.data["analysis"] == "호랑이로 보입니다. 줄무늬가 선명합니다."
    assert result.error is None
    assert result.source == "vision_animal_image"

    sent = client.chat.completions.calls[0]
    assert sent["model"] == "gpt-4.1-mini"
    image_part = sent["messages"][-1]["content"][-1]
    assert image_part["type"] == "image_url"
    assert image_part["image_url"]["url"].startswith("data:image/jpeg;base64,")


@pytest.mark.asyncio
async def test_analyze_animal_image_wraps_api_error() -> None:
    from backend.app.services.vision_service import analyze_animal_image

    client = FakeVisionClient(raise_error=True)
    result = await analyze_animal_image(
        b"fake-image-bytes", content_type="image/png", client=client, model="gpt-4.1-mini"
    )

    assert result.success is False
    assert result.error.code == "VISION_ANALYSIS_ERROR"
    assert "일시적 Vision API 오류" not in result.error.message
