"""embed_text의 재시도/오류 처리를 실제 API 없이 검증한다."""

from __future__ import annotations

import pytest


class _FakeEmbeddingData:
    def __init__(self, vector: list[float]) -> None:
        self.embedding = vector


class _FakeEmbeddingResponse:
    def __init__(self, vector: list[float]) -> None:
        self.data = [_FakeEmbeddingData(vector)]


class FakeEmbeddingsApi:
    def __init__(self, *, fail_times: int = 0, vector: list[float] | None = None) -> None:
        self.fail_times = fail_times
        self.calls = 0
        self.vector = vector or [0.1, 0.2, 0.3]

    async def create(self, **kwargs: object) -> _FakeEmbeddingResponse:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("일시적 임베딩 API 오류")
        return _FakeEmbeddingResponse(self.vector)


class FakeEmbeddingClient:
    def __init__(self, *, fail_times: int = 0, vector: list[float] | None = None) -> None:
        self.embeddings = FakeEmbeddingsApi(fail_times=fail_times, vector=vector)


@pytest.mark.asyncio
async def test_embed_text_returns_vector_on_first_success() -> None:
    from backend.app.services.embedding_service import embed_text

    client = FakeEmbeddingClient(vector=[0.5, 0.25])
    result = await embed_text("호랑이", client=client, model="text-embedding-3-small", retry_count=1)

    assert result == [0.5, 0.25]
    assert client.embeddings.calls == 1


@pytest.mark.asyncio
async def test_embed_text_retries_once_then_succeeds() -> None:
    from backend.app.services.embedding_service import embed_text

    client = FakeEmbeddingClient(fail_times=1, vector=[0.9])
    result = await embed_text("펭귄", client=client, model="text-embedding-3-small", retry_count=1)

    assert result == [0.9]
    assert client.embeddings.calls == 2


@pytest.mark.asyncio
async def test_embed_text_raises_after_exhausting_retries() -> None:
    from backend.app.services.embedding_service import EmbeddingServiceError, embed_text

    client = FakeEmbeddingClient(fail_times=5)
    with pytest.raises(EmbeddingServiceError):
        await embed_text("사자", client=client, model="text-embedding-3-small", retry_count=1)

    assert client.embeddings.calls == 2  # 최초 1회 + 재시도 1회
