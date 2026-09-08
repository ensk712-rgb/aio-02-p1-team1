"""OpenAI Embeddings API 호출과 재시도를 담당한다.

- LLM 호출(runtime)과는 무관하게 텍스트 -> 벡터 변환만 책임진다.
- 재시도 이후에도 실패하면 EmbeddingServiceError로 감싼다(호출자가 내부
  예외 원문을 그대로 사용자에게 노출하지 않도록).
"""

from __future__ import annotations

from typing import Any, Protocol

from openai import AsyncOpenAI

from backend.app.core.config import try_get_settings


class EmbeddingServiceError(RuntimeError):
    """임베딩 생성이 재시도 후에도 실패했을 때 발생한다."""


class _EmbeddingsApiProtocol(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...


class EmbeddingClientProtocol(Protocol):
    embeddings: _EmbeddingsApiProtocol


_client: EmbeddingClientProtocol | None = None


def _resolve_client(client: EmbeddingClientProtocol | None) -> EmbeddingClientProtocol:
    if client is not None:
        return client

    global _client
    if _client is None:
        settings = try_get_settings()
        api_key = settings.OPENAI_API_KEY if settings is not None else ""
        if not api_key:
            raise RuntimeError("임베딩 생성에는 OPENAI_API_KEY가 필요합니다.")
        _client = AsyncOpenAI(api_key=api_key)
    return _client


async def embed_text(
    text: str,
    *,
    client: EmbeddingClientProtocol | None = None,
    model: str | None = None,
    retry_count: int | None = None,
) -> list[float]:
    """텍스트 하나를 임베딩 벡터로 변환한다. 실패 시 1회(기본) 재시도한다."""
    settings = try_get_settings()
    resolved_model = model or (settings.EMBEDDING_MODEL if settings else "text-embedding-3-small")
    resolved_retry = (
        retry_count if retry_count is not None
        else (settings.EMBEDDING_RETRY_COUNT if settings else 1)
    )
    resolved_client = _resolve_client(client)

    last_error: Exception | None = None
    for _attempt in range(resolved_retry + 1):
        try:
            response = await resolved_client.embeddings.create(
                model=resolved_model,
                input=text,
            )
            return list(response.data[0].embedding)
        except Exception as error:  # API/네트워크 오류는 재시도 대상
            last_error = error

    raise EmbeddingServiceError("임베딩 생성에 반복 실패했습니다.") from last_error


def _reset_client_for_tests() -> None:
    """테스트 전용: 캐시된 클라이언트를 초기화한다."""
    global _client
    _client = None
