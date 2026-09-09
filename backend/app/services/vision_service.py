"""OpenAI Vision으로 업로드된 동물 사진을 분석한다.

- 이미지 인식 분석(서브프로젝트 5) 최소 구현: 업로드 이미지를 base64 data URL로
  감싸 Chat Completions Vision에 보내고, 자연어 설명 하나만 돌려받는다.
- RAG/MCP Tool 계약과 동일한 ToolRunResult 봉투를 사용해 프론트가 기존
  UI 패턴(성공/실패 표시)을 그대로 재사용할 수 있게 한다.
"""

from __future__ import annotations

import base64
from datetime import datetime, timezone
from typing import Any, Protocol

from openai import AsyncOpenAI

from backend.app.core.config import try_get_settings
from backend.app.schemas.common import ToolError, ToolRunResult

SOURCE_NAME = "vision_animal_image"

_SYSTEM_PROMPT = (
    "너는 동물원 관람 안내 보조원이다. 업로드된 사진 속 동물의 종류와 눈에 띄는 "
    "특징을 한국어로 3문장 이내로 설명해라. 확신이 없으면 '~로 추정됩니다'처럼 "
    "불확실함을 표시하고, 동물이 아니거나 식별할 수 없으면 그렇다고 말해라."
)


class _ChatCompletionsApiProtocol(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class _ChatApiProtocol(Protocol):
    completions: _ChatCompletionsApiProtocol


class VisionClientProtocol(Protocol):
    chat: _ChatApiProtocol


_client: VisionClientProtocol | None = None


def _resolve_client(client: VisionClientProtocol | None) -> VisionClientProtocol:
    if client is not None:
        return client

    global _client
    if _client is None:
        settings = try_get_settings()
        api_key = settings.OPENAI_API_KEY if settings is not None else ""
        if not api_key:
            raise RuntimeError("이미지 분석에는 OPENAI_API_KEY가 필요합니다.")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def analyze_animal_image(
    image_bytes: bytes,
    *,
    content_type: str,
    client: VisionClientProtocol | None = None,
    model: str | None = None,
) -> ToolRunResult:
    """이미지 바이트를 Vision 모델에 보내 동물 설명 문장을 받아온다.

    실패(네트워크/API 오류)만 success=false로 구분한다 — "동물이 아닌 것 같다"는
    모델이 만든 정상 답변이므로 success=true로 취급한다.
    """
    settings = try_get_settings()
    resolved_model = model or (settings.OPENAI_MODEL if settings else "gpt-4.1-mini")

    try:
        resolved_client = _resolve_client(client)
        encoded = base64.b64encode(image_bytes).decode("ascii")
        response = await resolved_client.chat.completions.create(
            model=resolved_model,
            messages=[
                {"role": "system", "content": _SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "이 사진 속 동물을 분석해줘."},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{content_type};base64,{encoded}"},
                        },
                    ],
                },
            ],
            max_tokens=300,
        )
        analysis = response.choices[0].message.content
    except Exception:  # 내부 예외 원문을 그대로 노출하지 않는다 (기존 서비스 계약과 동일)
        return ToolRunResult(
            success=False,
            data={},
            error=ToolError(
                code="VISION_ANALYSIS_ERROR",
                message="이미지 분석 중 오류가 발생했습니다.",
            ),
            source=SOURCE_NAME,
            retrieved_at=_now(),
        )

    return ToolRunResult(
        success=True,
        data={"analysis": analysis},
        error=None,
        source=SOURCE_NAME,
        retrieved_at=_now(),
    )


def _reset_client_for_tests() -> None:
    """테스트 전용: 캐시된 클라이언트를 초기화한다."""
    global _client
    _client = None
