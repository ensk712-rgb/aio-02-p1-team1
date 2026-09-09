# pgvector·Redis 전환 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **이 프로젝트 전용 규칙 (사용자 지시):**
> - **커밋은 매번 사용자에게 먼저 물어보고 승인받은 뒤에만 실행한다.** 스킬 기본 흐름이 "커밋" 스텝을 포함하더라도, 실제 `git commit`은 사용자의 명시적 "커밋해줘" 없이는 실행하지 않는다.
> - **각 Task, 각 Step마다 결과를 사용자에게 보여주고 확인받은 뒤 다음으로 넘어간다.** 여러 Task를 이어서 자동으로 처리하지 않는다.

**Goal:** RAG 검색을 실제 임베딩 기반 pgvector 벡터 검색으로 전환하고, 게스트 세션·Trace·세션 대화 기억 저장소를 Redis로 구현하며, 대화 기억을 Agent 응답에 실제로 연결한다.

**Architecture:** 각 Repository 모듈(`document_repository`, `session_repository`, `trace_repository`, 신규 `session_memory_repository`)은 파일을 나누지 않고 **`STORAGE_MODE` 설정값에 따라 내부에서 분기**한다 (`memory` → 기존 In-Memory 로직, `persistent` → Postgres/Redis 로직). 이렇게 하면 이 모듈들을 정적으로 import하는 `rag_service.py`, `agent_orchestration_service.py`의 호출 코드를 전혀 바꾸지 않고 구현만 교체할 수 있다. `backend/app/main.py`(이번 계획에서 신규 작성)는 STORAGE_MODE를 알 필요 없이 항상 같은 방식으로 모듈을 조립한다.

**Tech Stack:** FastAPI, Pydantic v2, `psycopg[binary]` 3.x + `psycopg_pool` (Postgres/pgvector), `redis` (redis-py, 동기 클라이언트), OpenAI Embeddings API(`text-embedding-3-small`), pytest, Docker Compose(`pgvector/pgvector:pg16`, `redis:7`).

**Spec:** [docs/superpowers/specs/2026-09-08-pgvector-redis-migration-design.md](../specs/2026-09-08-pgvector-redis-migration-design.md)

## Global Constraints

- `RAG_TOP_K=3`, `RAG_MIN_SCORE=0.5` — 기존 기본값 그대로 유지 (`backend/app/core/config.py`)
- `SESSION_TTL_SECONDS=7200`(기본) — 세션/Trace/세션기억 TTL에 공통 사용
- `STORAGE_MODE` 기본값은 항상 `memory` — 기존 회귀 테스트가 `persistent`로 우연히 전환되면 안 됨
- Postgres/Redis 연결 실패는 내부 예외 원문을 노출하지 않고 `ToolError` 계약(`code`, `message`)으로만 감싼다
- 신규 통합 테스트는 `@pytest.mark.integration`(이미 `pytest.ini`에 등록됨)으로 표시하고, 일반 `pytest` 실행(마커 미지정)에서는 자동 스킵되게 한다
- 커밋 메시지 끝에 `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>` 포함 (사용자가 커밋을 승인했을 때만)

---

## Task 0: Baseline 복구 — `main.py`와 실행 가능한 서버 조립

**배경:** 현재 `choiduna` 브랜치에는 실제로 뜨는 FastAPI 서버 진입점이 없다(`backend/app/main.py` 없음, `health_router.py`/`admin_router.py`/`mcp_client/client.py` 없음, `APP_MODE=mock`에서 쓸 수 있는 대화형 Mock Provider도 없음). `test` 브랜치에는 이 파일들이 이미 있으나 auth/예약 시스템과 얽혀 있어 그대로 가져올 수 없다. 이 Task에서는 auth/예약 의존이 없는 파일만 가져오고, `main.py`는 새로 작성한다.

**Files:**
- Create (checkout from `test` branch, unmodified): `backend/app/mcp_client/__init__.py`, `backend/app/mcp_client/client.py`, `backend/app/core/auth.py`, `backend/app/routers/health_router.py`, `backend/app/routers/admin_router.py`
- Modify (checkout from `test` branch, replaces current file — strict superset, adds `ZooMockProvider`): `backend/app/providers/mock_provider.py`
- Create: `backend/app/main.py`
- Test: `tests/ui_mcp/test_health_admin_router.py` (adapted from `test` branch), `tests/ui_mcp/test_main_integration.py` (adapted from `test` branch)

**Interfaces:**
- Produces: `create_app(settings: Settings | None = None) -> FastAPI` (`backend/app/main.py`) — 이후 모든 Task가 `STORAGE_MODE=persistent`를 검증할 때 이 함수로 실제 앱을 띄운다.
- Produces: `McpClient(server_url: str, *, timeout_seconds: float = 10)` — `list_tools()`, `call_tool()`, `check_health()` (`backend/app/mcp_client/client.py`)
- Produces: `ZooMockProvider` (`backend/app/providers/mock_provider.py`) — `APP_MODE=mock`일 때 `main.py`가 사용

- [ ] **Step 1: `test` 브랜치에서 auth/예약과 무관한 파일들을 checkout**

```bash
git checkout test -- backend/app/mcp_client/__init__.py backend/app/mcp_client/client.py backend/app/core/auth.py backend/app/routers/health_router.py backend/app/routers/admin_router.py backend/app/providers/mock_provider.py
```

- [ ] **Step 2: 가져온 파일들이 현재 브랜치의 스키마와 맞는지 확인**

Run: `python -c "import ast; [ast.parse(open(p, encoding='utf-8').read()) for p in ['backend/app/mcp_client/client.py','backend/app/core/auth.py','backend/app/routers/health_router.py','backend/app/routers/admin_router.py','backend/app/providers/mock_provider.py']]"`
Expected: 예외 없이 종료 (구문 오류 없음)

- [ ] **Step 3: `backend/app/main.py` 작성**

```python
"""Zoo Visit Guide FastAPI 애플리케이션 조립 진입점.

auth/예약 시스템은 이번 로드맵에서 다루지 않으므로 agent/health/admin
Router만 등록한다 (plan.md 2.2절 Out-of-Scope).
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.app.agents.runtime import RuntimeSettings
from backend.app.core.config import Settings, get_settings
from backend.app.mcp_client.client import McpClient
from backend.app.providers.mock_provider import ZooMockProvider
from backend.app.providers.openai_provider import OpenAIProvider
from backend.app.repositories import session_repository, trace_repository
from backend.app.routers.admin_router import create_admin_router
from backend.app.routers.agent_router import create_agent_router
from backend.app.routers.health_router import create_health_router
from backend.app.schemas.tools import ToolRunResult as ExecutorToolRunResult
from backend.app.services.agent_orchestration_service import AgentOrchestrationService
from backend.app.services.rag_service import retrieve_animal_info
from backend.app.tools.executor import ToolExecutor


def create_app(settings: Settings | None = None) -> FastAPI:
    """설정을 조립해 실행 가능한 FastAPI 앱을 만든다."""
    settings = settings or get_settings()

    mcp_client = McpClient(
        settings.MCP_SERVER_URL,
        timeout_seconds=settings.MCP_TIMEOUT_SECONDS,
    )
    executor = ToolExecutor(
        rag_search=_retrieve_animal_info_for_executor,
        mcp_client=mcp_client,
        max_same_tool_calls=settings.MAX_SAME_TOOL_CALLS,
        max_tool_calls=settings.MAX_TOOL_CALLS,
    )
    provider = (
        ZooMockProvider()
        if settings.APP_MODE == "mock"
        else OpenAIProvider(
            model=settings.OPENAI_MODEL,
            api_key=settings.OPENAI_API_KEY,
            timeout_seconds=min(30.0, settings.RUN_TIMEOUT_SECONDS),
        )
    )
    service = AgentOrchestrationService(
        session_repository=session_repository,
        trace_repository=trace_repository,
        provider=provider,
        executor=executor,
        settings=RuntimeSettings(
            max_agent_steps=settings.MAX_AGENT_STEPS,
            run_timeout_seconds=settings.RUN_TIMEOUT_SECONDS,
        ),
    )

    application = FastAPI(title="Zoo Visit Guide API", version="0.1.0")
    application.include_router(create_agent_router(service))
    application.include_router(
        create_health_router(
            mcp_client,
            app_mode=settings.APP_MODE,
            storage=settings.STORAGE_MODE,
        )
    )
    application.include_router(
        create_admin_router(
            trace_repository.list_runs,
            admin_token=settings.ADMIN_TOKEN,
        )
    )
    return application


def _retrieve_animal_info_for_executor(query: str, collection: str) -> ExecutorToolRunResult:
    """rag_service의 ToolRunResult(schemas.common)를 Executor 계약(schemas.tools)으로 정규화한다."""
    result = retrieve_animal_info(query, collection)
    return ExecutorToolRunResult.model_validate(result.model_dump())


app = create_app()
```

- [ ] **Step 4: `health_router.py`의 `storage` 파라미터 타입을 확장 (Task 1에서 STORAGE_MODE 리터럴이 늘어날 것을 대비해 지금 확인만)**

Run: `grep -n "storage" backend/app/routers/health_router.py`
Expected: `storage: Literal["memory"] = "memory"` 한 줄이 보임 — Task 1에서 `Literal["memory", "persistent"]`로 넓힐 예정이므로 지금은 수정하지 않고 그대로 둔다.

- [ ] **Step 5: `tests/ui_mcp/test_health_admin_router.py` 작성 (test 브랜치 버전에서 auth 세션 테스트 1건 제외)**

```python
"""health와 관리자 Trace Router 계약 시험."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.admin_router import create_admin_router
from backend.app.routers.health_router import create_health_router


class FakeMcpHealth:
    def __init__(self, available: bool) -> None:
        self.available = available

    async def check_health(self) -> bool:
        return self.available


def _health_client(available: bool) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_health_router(FakeMcpHealth(available), app_mode="mock")
    )
    return TestClient(app)


def test_health_reports_actual_mcp_state() -> None:
    healthy = _health_client(True).get("/api/health")
    assert healthy.status_code == 200
    assert healthy.json() == {
        "status": "ok",
        "backend": "ok",
        "mcp": "ok",
        "storage": "memory",
        "app_mode": "mock",
    }

    degraded = _health_client(False).get("/api/health")
    assert degraded.status_code == 503
    assert degraded.json()["mcp"] == "unavailable"
    assert degraded.json()["status"] == "degraded"


def _admin_client(token: str) -> TestClient:
    app = FastAPI()
    app.include_router(
        create_admin_router(
            lambda session_id: [
                {"run_id": "run_1", "status": "completed", "trace": []}
            ] if session_id == "session_1" else [],
            admin_token=token,
        )
    )
    return TestClient(app)


def test_admin_trace_blocks_unconfigured_missing_and_wrong_token() -> None:
    assert _admin_client("").get("/api/admin/trace?session_id=session_1").status_code == 401

    client = _admin_client("test-admin-token")
    assert client.get("/api/admin/trace?session_id=session_1").status_code == 401
    wrong = client.get(
        "/api/admin/trace?session_id=session_1",
        headers={"Authorization": "Bearer wrong"},
    )
    assert wrong.status_code == 401
    assert "test-admin-token" not in wrong.text


def test_admin_trace_returns_repository_contract() -> None:
    response = _admin_client("test-admin-token").get(
        "/api/admin/trace?session_id=session_1",
        headers={"Authorization": "Bearer test-admin-token"},
    )
    assert response.status_code == 200
    assert response.json() == {
        "runs": [{"run_id": "run_1", "status": "completed", "trace": []}]
    }
```

- [ ] **Step 6: 테스트 실행**

Run: `python -m pytest tests/ui_mcp/test_health_admin_router.py -v`
Expected: 4개 테스트 모두 PASS

- [ ] **Step 7: `tests/ui_mcp/test_main_integration.py` 작성 (실제 MCP Server 프로세스를 띄워 main.py 조립을 검증)**

```python
"""실제 MCP Server와 FastAPI main 조립의 N-01~N-04 연결 시험."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.repositories import session_repository, trace_repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_PORT = 18101


def _wait_for_port(process: subprocess.Popen[str], timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"MCP Server 조기 종료: {stdout} {stderr}")
        try:
            with socket.create_connection(("127.0.0.1", TEST_PORT), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError("MCP Server 시작 timeout")


@pytest.mark.integration
def test_main_connects_n01_to_n04_through_real_mcp() -> None:
    env = os.environ.copy()
    env.update({"APP_MODE": "mock", "MCP_HOST": "127.0.0.1", "MCP_PORT": str(TEST_PORT)})
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_port(process)
        session_repository._reset_for_tests()
        trace_repository._reset_for_tests()
        settings = Settings(
            _env_file=None,
            APP_MODE="mock",
            MCP_SERVER_URL=f"http://127.0.0.1:{TEST_PORT}/mcp",
            ADMIN_TOKEN="integration-admin",
            DEMO_NOW="2026-09-07T12:00:00+09:00",
        )
        with TestClient(create_app(settings)) as client:
            cases = [
                ("호랑이는 어디에서 살고 무엇을 먹어?", "retrieve_animal_info"),
                ("해양관의 다음 먹이시간을 알려 줘.", "get_feeding_schedule"),
                ("오늘 쉬는 전시관이 있는지 알려 줘.", "check_closure_status"),
                ("정문에서 해양관까지 가는 경로를 알려 줘.", "find_habitat_route"),
            ]
            session_id = None
            for message, expected_tool in cases:
                payload = {"message": message}
                if session_id:
                    payload["session_id"] = session_id
                response = client.post("/api/agent/ask", json=payload)
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["status"] == "completed", {
                    "expected_tool": expected_tool,
                    "status": body["status"],
                    "reason": body["termination_reason"],
                    "answer": body["final_answer"],
                    "trace": body["trace"],
                }
                session_id = body["session_id"]
    finally:
        process.terminate()
        process.wait(timeout=5)
```

- [ ] **Step 8: 통합 테스트 실행 (실제 MCP Server 서브프로세스 필요, docker/외부 인프라는 필요 없음)**

Run: `python -m pytest tests/ui_mcp/test_main_integration.py -v -m integration`
Expected: PASS (N-01~N-04 네 질문 모두 `status == "completed"`)

- [ ] **Step 9: 전체 회귀 테스트 실행 (기존 스위트가 이번 변경으로 깨지지 않았는지 확인)**

Run: `python -m pytest -q -m "not integration and not live"`
Expected: 기존 통과하던 테스트 전부 PASS, 실패 0건

- [ ] **Step 10: 사용자 검토 대기**

여기서 멈추고 사용자에게 Step 1~9 결과(어떤 파일이 새로 생겼는지, 테스트 결과)를 보여주고 다음 Task로 넘어가도 되는지 확인받는다. **커밋은 사용자가 명시적으로 요청할 때만 실행한다.**

---

## Task 1: 설정·인프라 스캐폴딩

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `.env.example`
- Modify: `backend/requirements.txt`
- Create: `infra/docker-compose.yml`
- Test: `tests/data/test_config_and_data.py` (기존 파일에 케이스 추가)

**Interfaces:**
- Produces: `Settings.STORAGE_MODE: Literal["memory", "persistent"]`, `Settings.DATABASE_URL: str`, `Settings.REDIS_URL: str`, `Settings.SESSION_MEMORY_MAX_TURNS: int`, `Settings.EMBEDDING_MODEL: str`, `Settings.EMBEDDING_RETRY_COUNT: int` — Task 2 이후 모든 Task가 이 설정값을 읽는다.

- [ ] **Step 1: 기존 config 테스트 확인 (회귀 기준선)**

Run: `python -m pytest tests/data/test_config_and_data.py -v`
Expected: 현재 존재하는 테스트 전부 PASS (수정 전 기준선 확보)

- [ ] **Step 2: `test_config_and_data.py`에 신규 설정 기본값 테스트 추가**

```python
def test_storage_and_persistence_defaults() -> None:
    from backend.app.core.config import Settings

    settings = Settings(_env_file=None)
    assert settings.STORAGE_MODE == "memory"
    assert settings.DATABASE_URL == ""
    assert settings.REDIS_URL == ""
    assert settings.SESSION_MEMORY_MAX_TURNS == 6
    assert settings.EMBEDDING_MODEL == "text-embedding-3-small"
    assert settings.EMBEDDING_RETRY_COUNT == 1
```

- [ ] **Step 3: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/data/test_config_and_data.py::test_storage_and_persistence_defaults -v`
Expected: FAIL (`STORAGE_MODE` 타입에 `persistent`가 없거나 나머지 필드가 없어서 `AttributeError`/`ValidationError`)

- [ ] **Step 4: `backend/app/core/config.py` 수정**

`backend/app/core/config.py:26` 근처 `STORAGE_MODE` 줄을 찾아 교체:

```python
    APP_MODE: Literal["mock", "openai"] = "mock"
    STORAGE_MODE: Literal["memory", "persistent"] = "memory"
```

`RAG 설정` 블록 뒤에 추가:

```python
    # P1: pgvector/Redis 전환 (STORAGE_MODE=persistent일 때만 사용)
    DATABASE_URL: str = ""
    REDIS_URL: str = ""
    SESSION_MEMORY_MAX_TURNS: int = 6
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_RETRY_COUNT: int = 1
```

- [ ] **Step 5: 테스트 재실행**

Run: `python -m pytest tests/data/test_config_and_data.py -v`
Expected: 전부 PASS (신규 케이스 포함)

- [ ] **Step 6: `.env.example`에 항목 추가**

`.env.example`의 `STORAGE_MODE=memory` 줄 아래에 추가:

```
# P1: pgvector/Redis 전환 (STORAGE_MODE=persistent일 때만 필요)
DATABASE_URL=postgresql://zoo:zoo@127.0.0.1:5432/zoo
REDIS_URL=redis://127.0.0.1:6380/0
SESSION_MEMORY_MAX_TURNS=6
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_RETRY_COUNT=1
```

- [ ] **Step 7: `infra/docker-compose.yml` 작성**

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: zoo
      POSTGRES_PASSWORD: zoo
      POSTGRES_DB: zoo
    ports:
      - "5432:5432"
    volumes:
      - zoo_postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7
    ports:
      - "6380:6379"  # 6379는 다른 프로젝트 컨테이너가 이미 점유 중이라 6380으로 매핑

volumes:
  zoo_postgres_data:
```

- [ ] **Step 8: `backend/requirements.txt`에 의존성 추가**

`backend/requirements.txt` 끝에 추가:

```
psycopg[binary]>=3.1,<4
psycopg_pool>=3.2,<4
pgvector>=0.3,<1
redis>=5.0,<6
```

- [ ] **Step 9: 의존성 설치**

Run: `python -m pip install -r backend/requirements.txt`
Expected: 설치 완료, 오류 없음

- [ ] **Step 10: docker-compose 문법 검증 및 컨테이너 기동**

Run: `docker compose -f infra/docker-compose.yml config -q && docker compose -f infra/docker-compose.yml up -d`
Expected: 오류 없이 `postgres`, `redis` 컨테이너가 `Up` 상태로 시작

- [ ] **Step 11: 사용자 검토 대기**

컨테이너가 정상 기동했는지(`docker compose -f infra/docker-compose.yml ps`) 사용자에게 보여주고 다음 Task 진행 여부를 확인받는다.

---

## Task 2: Postgres 연결 헬퍼 + pgvector 스키마

**Files:**
- Create: `backend/app/core/db.py`
- Test: `tests/data/test_db.py`

**Interfaces:**
- Consumes: `Settings.DATABASE_URL` (Task 1)
- Produces: `get_connection_pool() -> ConnectionPool`, `ensure_schema(pool: ConnectionPool | None = None) -> None` — Task 5(`document_repository`)가 사용

- [ ] **Step 1: 실패하는 테스트 작성 — `tests/data/test_db.py`**

```python
"""Postgres 연결 풀과 pgvector 스키마 준비를 검증한다 (실제 DB 필요)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_ensure_schema_creates_pgvector_extension_and_table() -> None:
    from backend.app.core.db import ensure_schema, get_connection_pool

    pool = get_connection_pool(dsn="postgresql://zoo:zoo@127.0.0.1:5432/zoo")
    ensure_schema(pool)

    with pool.connection() as conn:
        row = conn.execute(
            "SELECT extname FROM pg_extension WHERE extname = 'vector'"
        ).fetchone()
        assert row is not None

        row = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'document_chunks' AND column_name = 'embedding'"
        ).fetchone()
        assert row is not None
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/data/test_db.py -v -m integration`
Expected: FAIL (`ModuleNotFoundError: backend.app.core.db`)

- [ ] **Step 3: `backend/app/core/db.py` 작성**

```python
"""Postgres(pgvector) 연결 풀과 스키마 준비를 담당한다.

- 커넥션은 프로세스당 하나의 Pool로 재사용한다 (요청마다 재연결하지 않는다).
- 여기서는 SQL 실행만 담당하고, 검색/삽입 업무 로직은 document_repository가 가진다.
"""

from __future__ import annotations

from psycopg_pool import ConnectionPool

from backend.app.core.config import try_get_settings

_pool: ConnectionPool | None = None

_SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    doc_id TEXT NOT NULL,
    collection TEXT NOT NULL,
    title TEXT NOT NULL,
    page INTEGER,
    text TEXT NOT NULL,
    keywords TEXT[] NOT NULL DEFAULT '{}',
    embedding VECTOR(1536) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (doc_id, collection)
);

CREATE INDEX IF NOT EXISTS document_chunks_collection_idx
    ON document_chunks (collection);
"""


def _resolve_dsn(dsn: str | None) -> str:
    if dsn:
        return dsn
    settings = try_get_settings()
    if settings is None or not settings.DATABASE_URL:
        raise RuntimeError("DATABASE_URL이 설정되지 않았습니다.")
    return settings.DATABASE_URL


def get_connection_pool(dsn: str | None = None) -> ConnectionPool:
    """프로세스 전체에서 재사용하는 단일 Connection Pool을 반환한다."""
    global _pool
    if _pool is None:
        _pool = ConnectionPool(_resolve_dsn(dsn), min_size=1, max_size=5, open=True)
    return _pool


def ensure_schema(pool: ConnectionPool | None = None) -> None:
    """pgvector 확장과 document_chunks 테이블이 없으면 만든다."""
    pool = pool or get_connection_pool()
    with pool.connection() as conn:
        conn.execute(_SCHEMA_SQL)
        conn.commit()


def _reset_pool_for_tests() -> None:
    """테스트 전용: 캐시된 Pool을 닫고 초기화한다."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None
```

- [ ] **Step 4: 테스트 실행 (docker-compose postgres가 떠 있어야 함)**

Run: `python -m pytest tests/data/test_db.py -v -m integration`
Expected: PASS — `vector` 확장과 `document_chunks.embedding` 컬럼이 존재함

- [ ] **Step 5: 사용자 검토 대기**

`docker exec`로 직접 테이블을 확인해 보여주고 다음 Task로 넘어가도 되는지 확인받는다:

```bash
docker compose -f infra/docker-compose.yml exec postgres psql -U zoo -d zoo -c "\d document_chunks"
```

---

## Task 3: Redis 연결 헬퍼

**Files:**
- Create: `backend/app/core/redis_client.py`
- Test: `tests/data/test_redis_client.py`

**Interfaces:**
- Consumes: `Settings.REDIS_URL` (Task 1)
- Produces: `get_redis_client() -> redis.Redis` — Task 7, 8이 사용

- [ ] **Step 1: 실패하는 테스트 작성**

```python
"""Redis 연결 헬퍼를 검증한다 (실제 Redis 필요)."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def test_get_redis_client_can_ping_and_roundtrip_a_value() -> None:
    from backend.app.core.redis_client import get_redis_client

    client = get_redis_client(url="redis://127.0.0.1:6380/0")
    assert client.ping() is True

    client.set("zoo:test:ping", "pong", ex=5)
    assert client.get("zoo:test:ping") == "pong"
    client.delete("zoo:test:ping")
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/data/test_redis_client.py -v -m integration`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: `backend/app/core/redis_client.py` 작성**

```python
"""Redis 클라이언트 지연 초기화 헬퍼."""

from __future__ import annotations

import redis

from backend.app.core.config import try_get_settings

_client: redis.Redis | None = None


def _resolve_url(url: str | None) -> str:
    if url:
        return url
    settings = try_get_settings()
    if settings is None or not settings.REDIS_URL:
        raise RuntimeError("REDIS_URL이 설정되지 않았습니다.")
    return settings.REDIS_URL


def get_redis_client(url: str | None = None) -> redis.Redis:
    """프로세스 전체에서 재사용하는 단일 Redis 클라이언트를 반환한다.

    decode_responses=True로 항상 str을 주고받는다 (bytes 처리 분기를 없앤다).
    """
    global _client
    if _client is None:
        _client = redis.Redis.from_url(_resolve_url(url), decode_responses=True)
    return _client


def _reset_client_for_tests() -> None:
    """테스트 전용: 캐시된 클라이언트를 초기화한다."""
    global _client
    _client = None
```

- [ ] **Step 4: 테스트 실행**

Run: `python -m pytest tests/data/test_redis_client.py -v -m integration`
Expected: PASS

- [ ] **Step 5: 사용자 검토 대기**

---

## Task 4: 임베딩 서비스

**Files:**
- Create: `backend/app/services/embedding_service.py`
- Test: `tests/data/test_embedding_service.py`

**Interfaces:**
- Consumes: `Settings.OPENAI_API_KEY`, `Settings.EMBEDDING_MODEL`, `Settings.EMBEDDING_RETRY_COUNT`
- Produces: `embed_text(text: str, *, client: EmbeddingClientProtocol | None = None) -> list[float]` — Task 5(`document_repository`)가 사용

- [ ] **Step 1: 실패하는 단위 테스트 작성 (Fake Client로 재시도 로직 검증, 실제 API 호출 없음)**

```python
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
```

- [ ] **Step 2: `pytest-asyncio` 설치 및 `pytest.ini`에 asyncio 모드 확인**

Run: `python -c "import pytest_asyncio"`
Expected: 설치되어 있지 않으면 `pip install pytest-asyncio>=0.23,<1`로 설치. `pytest.ini`의 `[pytest]` 섹션에 `asyncio_mode = auto`가 없으면 추가한다.

- [ ] **Step 3: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/data/test_embedding_service.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 4: `backend/app/services/embedding_service.py` 작성**

```python
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
    for attempt in range(resolved_retry + 1):
        try:
            response = await resolved_client.embeddings.create(
                model=resolved_model,
                input=text,
            )
            return list(response.data[0].embedding)
        except Exception as error:  # API/네트워크 오류는 재시도 대상
            last_error = error

    raise EmbeddingServiceError("임베딩 생성에 반복 실패했습니다.") from last_error
```

- [ ] **Step 5: 테스트 실행**

Run: `python -m pytest tests/data/test_embedding_service.py -v`
Expected: 3개 테스트 모두 PASS

- [ ] **Step 6: 사용자 검토 대기**

---

## Task 5: `document_repository` — pgvector 검색 + `insert_chunks`

**Files:**
- Modify: `backend/app/repositories/document_repository.py`
- Test: `tests/data/test_document_repository_pgvector.py`

**Interfaces:**
- Consumes: `backend.app.core.db.get_connection_pool/ensure_schema` (Task 2), `backend.app.services.embedding_service.embed_text` (Task 4)
- Produces: `search(query: str, collection: str, top_k: int) -> list[RetrievedChunk]` (기존 시그니처 유지, 내부만 STORAGE_MODE로 분기), `insert_chunks(chunks: list[ChunkInput]) -> None` (신규) — Task 6(시딩 스크립트)이 사용

- [ ] **Step 1: 기존 회귀 테스트 기준선 확인**

Run: `python -m pytest tests/data/test_rag_service.py tests/data/test_rag_service_safety.py -v`
Expected: 전부 PASS (수정 전 기준선)

- [ ] **Step 2: 실패하는 pgvector 테스트 작성 — `tests/data/test_document_repository_pgvector.py`**

```python
"""STORAGE_MODE=persistent 경로의 document_repository를 실제 Postgres로 검증한다."""

from __future__ import annotations

import pytest

from backend.app.core.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _persistent_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.core import db as db_module
    from backend.app.core import config as config_module

    db_module._reset_pool_for_tests()
    test_settings = Settings(
        _env_file=None,
        STORAGE_MODE="persistent",
        DATABASE_URL="postgresql://zoo:zoo@127.0.0.1:5432/zoo",
        OPENAI_API_KEY=config_module.get_settings().OPENAI_API_KEY,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)

    from backend.app.core.db import ensure_schema, get_connection_pool

    pool = get_connection_pool(dsn=test_settings.DATABASE_URL)
    ensure_schema(pool)
    with pool.connection() as conn:
        conn.execute("DELETE FROM document_chunks WHERE collection = 'test_pgvector'")
        conn.commit()
    yield
    with pool.connection() as conn:
        conn.execute("DELETE FROM document_chunks WHERE collection = 'test_pgvector'")
        conn.commit()


def test_insert_then_search_returns_closest_chunk_first() -> None:
    from backend.app.repositories.document_repository import insert_chunks, search
    from backend.app.schemas.tools import ChunkInput

    insert_chunks([
        ChunkInput(
            doc_id="doc-tiger",
            collection="test_pgvector",
            title="호랑이 정보",
            page=None,
            text="호랑이는 맹수관에서 서식하며 육식을 한다.",
            keywords=["호랑이", "맹수관"],
        ),
        ChunkInput(
            doc_id="doc-penguin",
            collection="test_pgvector",
            title="펭귄 정보",
            page=None,
            text="펭귄은 해양관에서 서식하며 물고기를 먹는다.",
            keywords=["펭귄", "해양관"],
        ),
    ])

    results = search("호랑이는 무엇을 먹나요?", "test_pgvector", top_k=2)

    assert len(results) == 2
    assert results[0].doc_id == "doc-tiger"
    assert 0.0 <= results[0].score <= 1.0
    assert results[0].score >= results[1].score
```

- [ ] **Step 3: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/data/test_document_repository_pgvector.py -v -m integration`
Expected: FAIL (`ImportError: cannot import name 'insert_chunks'` 또는 `ChunkInput` 없음)

- [ ] **Step 4: `backend/app/schemas/tools.py`에 `ChunkInput` 추가**

`backend/app/schemas/tools.py` 끝에 추가:

```python
class ChunkInput(BaseModel):
    """document_repository.insert_chunks에 전달하는 청크 한 건이다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    doc_id: str = Field(min_length=1)
    collection: str = Field(min_length=1)
    title: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
    text: str = Field(min_length=1)
    keywords: list[str] = Field(default_factory=list)
```

- [ ] **Step 5: `document_repository.py`를 STORAGE_MODE 분기 구조로 리팩터링**

기존 `search()` 함수를 `_search_memory()`로 이름을 바꾸고, 새 공개 `search()`가 분기하도록 수정. 파일 끝(`_score` 함수와 기존 `search` 함수 사이)에 아래 내용으로 교체:

```python
def _search_memory(query: str, collection: str, top_k: int) -> list[RetrievedChunk]:
    """기존 키워드 매칭 검색 (STORAGE_MODE=memory)."""
    tokens = _tokenize(query)
    scored: list[tuple[float, dict]] = []
    for card in load_cards():
        if card["collection"] != collection:
            continue
        scored.append((_score(tokens, card), card))

    scored.sort(key=lambda pair: (-pair[0], pair[1]["doc_id"]))

    return [
        RetrievedChunk(
            doc_id=card["doc_id"],
            title=card["title"],
            page=card.get("page"),
            text=card["text"],
            score=score,
            collection=card["collection"],
        )
        for score, card in scored[:top_k]
    ]


def _search_persistent(query: str, collection: str, top_k: int) -> list[RetrievedChunk]:
    """pgvector 코사인 유사도 검색 (STORAGE_MODE=persistent)."""
    import asyncio

    from backend.app.core.db import get_connection_pool
    from backend.app.services.embedding_service import embed_text

    query_embedding = asyncio.run(embed_text(query))
    pool = get_connection_pool()

    with pool.connection() as conn:
        rows = conn.execute(
            """
            SELECT doc_id, title, page, text, collection,
                   (embedding <=> %s::vector) AS distance
            FROM document_chunks
            WHERE collection = %s
            ORDER BY embedding <=> %s::vector, doc_id ASC
            LIMIT %s
            """,
            (query_embedding, collection, query_embedding, top_k),
        ).fetchall()

    return [
        RetrievedChunk(
            doc_id=row[0],
            title=row[1],
            page=row[2],
            text=row[3],
            collection=row[4],
            score=round(max(0.0, 1.0 - float(row[5])), 4),
        )
        for row in rows
    ]


def search(query: str, collection: str, top_k: int) -> list[RetrievedChunk]:
    """STORAGE_MODE에 따라 키워드 검색 또는 pgvector 검색으로 분기한다."""
    settings = try_get_settings()
    if settings is not None and settings.STORAGE_MODE == "persistent":
        return _search_persistent(query, collection, top_k)
    return _search_memory(query, collection, top_k)


def insert_chunks(chunks: list["ChunkInput"]) -> None:
    """청크 목록을 임베딩해 pgvector 테이블에 upsert한다 (STORAGE_MODE=persistent 전용).

    PDF 업로드(서브프로젝트 2)와 시딩 스크립트가 이 함수를 사용한다.
    """
    import asyncio

    from backend.app.core.db import get_connection_pool

    pool = get_connection_pool()
    with pool.connection() as conn:
        for chunk in chunks:
            embedding = asyncio.run(embed_text(chunk.text))
            conn.execute(
                """
                INSERT INTO document_chunks
                    (doc_id, collection, title, page, text, keywords, embedding)
                VALUES (%s, %s, %s, %s, %s, %s, %s::vector)
                ON CONFLICT (doc_id, collection) DO UPDATE SET
                    title = EXCLUDED.title,
                    page = EXCLUDED.page,
                    text = EXCLUDED.text,
                    keywords = EXCLUDED.keywords,
                    embedding = EXCLUDED.embedding
                """,
                (
                    chunk.doc_id,
                    chunk.collection,
                    chunk.title,
                    chunk.page,
                    chunk.text,
                    chunk.keywords,
                    embedding,
                ),
            )
        conn.commit()
```

파일 상단 import 블록에 추가:

```python
from backend.app.core.config import try_get_settings
from backend.app.schemas.tools import ChunkInput
```

- [ ] **Step 6: 테스트 실행 (docker-compose postgres 필요, `OPENAI_API_KEY` 필요 — 없으면 이 Step은 스킵하고 Step 9로 이동해 사용자에게 API Key 유무를 확인)**

Run: `python -m pytest tests/data/test_document_repository_pgvector.py -v -m integration`
Expected: PASS — `doc-tiger`가 1등, `doc-penguin`이 2등으로 반환

- [ ] **Step 7: 기존 회귀 테스트 재실행 (STORAGE_MODE=memory 경로가 그대로인지 확인)**

Run: `python -m pytest tests/data/test_rag_service.py tests/data/test_rag_service_safety.py -v`
Expected: 전부 PASS (Step 1과 동일한 결과)

- [ ] **Step 8: 전체 회귀 테스트**

Run: `python -m pytest -q -m "not integration and not live"`
Expected: 실패 0건

- [ ] **Step 9: 사용자 검토 대기**

---

## Task 6: 동물 정보카드 시딩 스크립트

**Files:**
- Create: `scripts/seed_animal_cards.py`

**Interfaces:**
- Consumes: `backend.app.repositories.document_repository.insert_chunks` (Task 5), `data/animal_cards/*.json`

- [ ] **Step 1: `scripts/seed_animal_cards.py` 작성**

```python
"""data/animal_cards/*.json을 읽어 Postgres(pgvector)에 적재한다.

1회 실행 스크립트다. 카드 파일이 바뀌면 다시 실행한다 (doc_id 기준 upsert).
실행 전 STORAGE_MODE=persistent, DATABASE_URL, OPENAI_API_KEY가 설정돼 있어야 한다.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from backend.app.core.config import get_settings
from backend.app.core.db import ensure_schema
from backend.app.repositories.document_repository import insert_chunks
from backend.app.schemas.tools import ChunkInput


def _load_cards() -> list[ChunkInput]:
    cards_dir = PROJECT_ROOT / "data" / "animal_cards"
    chunks: list[ChunkInput] = []
    for path in sorted(cards_dir.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            card = json.load(f)
        chunks.append(
            ChunkInput(
                doc_id=card["doc_id"],
                collection=card["collection"],
                title=card["title"],
                page=card.get("page"),
                text=card["text"],
                keywords=card.get("keywords", []),
            )
        )
    return chunks


def main() -> None:
    settings = get_settings()
    if settings.STORAGE_MODE != "persistent":
        raise SystemExit("STORAGE_MODE=persistent로 설정한 뒤 실행하세요.")

    ensure_schema()
    chunks = _load_cards()
    insert_chunks(chunks)
    print(f"{len(chunks)}개 동물 정보카드를 적재했습니다.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: 실행 (docker-compose postgres 필요, OPENAI_API_KEY 필요)**

Run: `STORAGE_MODE=persistent DATABASE_URL=postgresql://zoo:zoo@127.0.0.1:5432/zoo python scripts/seed_animal_cards.py`
Expected: `"N개 동물 정보카드를 적재했습니다."` 출력, `N`은 `data/animal_cards/*.json` 파일 개수와 동일

- [ ] **Step 3: 적재 결과 확인**

Run: `docker compose -f infra/docker-compose.yml exec postgres psql -U zoo -d zoo -c "SELECT count(*) FROM document_chunks WHERE collection = 'animal_cards';"`
Expected: Step 2의 `N`과 동일한 개수

- [ ] **Step 4: 사용자 검토 대기**

---

## Task 7: `session_repository` / `trace_repository` — Redis 구현

**Files:**
- Modify: `backend/app/repositories/session_repository.py`
- Modify: `backend/app/repositories/trace_repository.py`
- Test: `tests/data/test_session_and_trace_repository_redis.py`

**Interfaces:**
- Consumes: `backend.app.core.redis_client.get_redis_client` (Task 3)
- Produces: 기존 시그니처 그대로 (`create_session`, `validate_session`, `save_run`, `list_runs`, `clear_session`) — `agent_orchestration_service.py`는 변경 없음

- [ ] **Step 1: 기존 회귀 테스트 기준선 확인**

Run: `python -m pytest tests/data/test_session_and_trace_repository.py -v`
Expected: 전부 PASS

- [ ] **Step 2: 실패하는 Redis 통합 테스트 작성 — `tests/data/test_session_and_trace_repository_redis.py`**

```python
"""STORAGE_MODE=persistent 경로의 session/trace 저장소를 실제 Redis로 검증한다."""

from __future__ import annotations

import time

import pytest

from backend.app.core.config import Settings

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _persistent_settings(monkeypatch: pytest.MonkeyPatch):
    from backend.app.core import config as config_module
    from backend.app.core import redis_client as redis_client_module

    redis_client_module._reset_client_for_tests()
    test_settings = Settings(
        _env_file=None,
        STORAGE_MODE="persistent",
        REDIS_URL="redis://127.0.0.1:6380/0",
        SESSION_TTL_SECONDS=1,
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: test_settings)
    monkeypatch.setattr(config_module, "try_get_settings", lambda: test_settings)

    client = redis_client_module.get_redis_client(url=test_settings.REDIS_URL)
    yield client
    for key in client.scan_iter("session:test:*"):
        client.delete(key)
    for key in client.scan_iter("trace:test:*"):
        client.delete(key)


def test_redis_session_roundtrip_and_ttl_expiry() -> None:
    from backend.app.repositories import session_repository, trace_repository

    session_id = session_repository.create_session()
    assert session_repository.validate_session(session_id) is True

    trace_repository.save_run(session_id, "run_1", "completed", [{"owner": "runtime"}])
    assert trace_repository.list_runs(session_id) == [
        {"run_id": "run_1", "status": "completed", "trace": [{"owner": "runtime"}]}
    ]

    time.sleep(1.5)  # SESSION_TTL_SECONDS=1 초과 대기

    assert session_repository.validate_session(session_id) is False
    assert trace_repository.list_runs(session_id) == []
```

- [ ] **Step 3: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/data/test_session_and_trace_repository_redis.py -v -m integration`
Expected: FAIL (현재는 STORAGE_MODE를 무시하고 항상 In-Memory 사용 → TTL이 실제 Redis에 반영되지 않음)

- [ ] **Step 4: `session_repository.py`를 STORAGE_MODE 분기로 리팩터링**

파일 상단 import에 추가:

```python
from backend.app.core.redis_client import get_redis_client
```

기존 `create_session`, `validate_session` 함수 이름을 `_create_session_memory`, `_validate_session_memory`로 바꾸고, 파일 끝(`_reset_for_tests` 앞)에 아래 내용 추가 후 공개 함수를 재정의:

```python
def _create_session_redis() -> str:
    session_id = f"guest-{secrets.token_urlsafe(16)}"
    client = get_redis_client()
    client.set(f"session:{session_id}", "1", ex=_ttl_seconds())
    return session_id


def _validate_session_redis(session_id: str) -> bool:
    if not session_id:
        return False
    client = get_redis_client()
    exists = client.exists(f"session:{session_id}") == 1
    if not exists:
        return False
    client.expire(f"session:{session_id}", _ttl_seconds())
    return True


def _use_redis() -> bool:
    settings = try_get_settings()
    return settings is not None and settings.STORAGE_MODE == "persistent"


def create_session(*, now: datetime | None = None) -> str:
    """추측 어려운 새 게스트 세션 ID를 발급하고 등록한다."""
    if _use_redis():
        return _create_session_redis()
    return _create_session_memory(now=now)


def validate_session(session_id: str, *, now: datetime | None = None) -> bool:
    """등록되고 만료되지 않은 세션인지 확인한다."""
    if _use_redis():
        return _validate_session_redis(session_id)
    return _validate_session_memory(session_id, now=now)
```

`_reset_for_tests()`에 Redis 정리도 추가:

```python
def _reset_for_tests() -> None:
    """테스트 전용: 모듈 전역 상태를 초기화한다."""
    with _lock:
        _sessions.clear()
    if _use_redis():
        client = get_redis_client()
        for key in client.scan_iter("session:guest-*"):
            client.delete(key)
```

- [ ] **Step 5: `trace_repository.py`를 STORAGE_MODE 분기로 리팩터링**

파일 상단 import에 추가:

```python
import json

from backend.app.core.config import try_get_settings
from backend.app.core.redis_client import get_redis_client
```

기존 `save_run`, `list_runs`, `clear_session` 함수 이름을 `_save_run_memory`, `_list_runs_memory`, `_clear_session_memory`로 바꾸고, 파일 끝에 추가:

```python
def _use_redis() -> bool:
    settings = try_get_settings()
    return settings is not None and settings.STORAGE_MODE == "persistent"


def _ttl_seconds() -> int:
    settings = try_get_settings()
    return settings.SESSION_TTL_SECONDS if settings is not None else 7200


def _save_run_redis(session_id: str, run_id: str, status: str, trace: list[dict]) -> None:
    entry = json.dumps({"run_id": run_id, "status": status, "trace": trace}, ensure_ascii=False)
    client = get_redis_client()
    key = f"trace:{session_id}"
    client.rpush(key, entry)
    client.ltrim(key, -_MAX_RUNS_PER_SESSION, -1)
    client.expire(key, _ttl_seconds())


def _list_runs_redis(session_id: str) -> list[dict]:
    client = get_redis_client()
    raw_entries = client.lrange(f"trace:{session_id}", 0, -1)
    return [json.loads(entry) for entry in raw_entries]


def _clear_session_redis(session_id: str) -> None:
    get_redis_client().delete(f"trace:{session_id}")


def save_run(session_id: str, run_id: str, status: str, trace: list[dict]) -> None:
    """세션의 실행 기록에 한 run을 추가한다."""
    if _use_redis():
        _save_run_redis(session_id, run_id, status, trace)
    else:
        _save_run_memory(session_id, run_id, status, trace)


def list_runs(session_id: str) -> list[dict]:
    """세션의 실행 기록을 저장된 순서 그대로 반환한다."""
    if _use_redis():
        return _list_runs_redis(session_id)
    return _list_runs_memory(session_id)


def clear_session(session_id: str) -> None:
    """세션 만료/삭제 시 연결된 Trace를 전부 제거한다."""
    if _use_redis():
        _clear_session_redis(session_id)
    else:
        _clear_session_memory(session_id)
```

- [ ] **Step 6: 테스트 실행**

Run: `python -m pytest tests/data/test_session_and_trace_repository_redis.py -v -m integration`
Expected: PASS

- [ ] **Step 7: 기존 회귀 테스트 재실행**

Run: `python -m pytest tests/data/test_session_and_trace_repository.py -v`
Expected: 전부 PASS (STORAGE_MODE=memory 경로는 그대로)

- [ ] **Step 8: 전체 회귀 테스트**

Run: `python -m pytest -q -m "not integration and not live"`
Expected: 실패 0건

- [ ] **Step 9: 사용자 검토 대기**

---

## Task 8: `session_memory_repository` (신규)

**Files:**
- Create: `backend/app/repositories/session_memory_repository.py`
- Test: `tests/data/test_session_memory_repository.py`

**Interfaces:**
- Consumes: `backend.app.core.redis_client.get_redis_client` (Task 3)
- Produces: `get_recent(session_id: str) -> list[dict]`, `append_message(session_id: str, role: str, text: str) -> None` — Task 9가 사용

- [ ] **Step 1: 실패하는 테스트 작성 (메모리 모드 + Redis 모드 둘 다)**

```python
"""session_memory_repository의 메모리/Redis 두 경로를 검증한다."""

from __future__ import annotations

import pytest

from backend.app.core.config import Settings
from backend.app.repositories import session_memory_repository as repo


@pytest.fixture(autouse=True)
def _reset():
    repo._reset_for_tests()
    yield
    repo._reset_for_tests()


def test_memory_mode_keeps_last_n_turns_in_order() -> None:
    repo.append_message("session_1", "user", "안녕")
    repo.append_message("session_1", "agent", "안녕하세요")
    repo.append_message("session_1", "user", "호랑이 어디 있어?")

    history = repo.get_recent("session_1")
    assert [item["text"] for item in history] == ["안녕", "안녕하세요", "호랑이 어디 있어?"]
    assert history[0]["role"] == "user"


def test_memory_mode_trims_to_max_turns(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.core import config as config_module

    monkeypatch.setattr(
        config_module, "try_get_settings",
        lambda: Settings(_env_file=None, SESSION_MEMORY_MAX_TURNS=2),
    )
    for i in range(4):
        repo.append_message("session_2", "user", f"message-{i}")

    history = repo.get_recent("session_2")
    assert [item["text"] for item in history] == ["message-2", "message-3"]


@pytest.mark.integration
def test_redis_mode_roundtrip(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.core import config as config_module
    from backend.app.core import redis_client as redis_client_module

    redis_client_module._reset_client_for_tests()
    test_settings = Settings(
        _env_file=None,
        STORAGE_MODE="persistent",
        REDIS_URL="redis://127.0.0.1:6380/0",
    )
    monkeypatch.setattr(config_module, "try_get_settings", lambda: test_settings)
    client = redis_client_module.get_redis_client(url=test_settings.REDIS_URL)
    client.delete("session_memory:redis_test")

    repo.append_message("redis_test", "user", "레디스 테스트")
    history = repo.get_recent("redis_test")

    assert history == [{"role": "user", "text": "레디스 테스트"}]
    client.delete("session_memory:redis_test")
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/data/test_session_memory_repository.py -v`
Expected: FAIL (`ModuleNotFoundError`)

- [ ] **Step 3: `backend/app/repositories/session_memory_repository.py` 작성**

```python
"""세션 대화 기억 저장소 (plan.md Phase 7 선반영).

- STORAGE_MODE=memory: In-Memory dict (프로세스 재시작 시 소멸, 기본값)
- STORAGE_MODE=persistent: Redis List, TTL=SESSION_TTL_SECONDS
- 두 모드 모두 SESSION_MEMORY_MAX_TURNS개까지만 최신 순으로 유지한다.
"""

from __future__ import annotations

import json
from collections import defaultdict, deque
from threading import Lock
from typing import TypedDict

from backend.app.core.config import try_get_settings
from backend.app.core.redis_client import get_redis_client

_DEFAULT_MAX_TURNS = 6
_DEFAULT_TTL_SECONDS = 7200


class _MessageEntry(TypedDict):
    role: str
    text: str


_messages: dict[str, deque[_MessageEntry]] = {}
_lock = Lock()


def _max_turns() -> int:
    settings = try_get_settings()
    return settings.SESSION_MEMORY_MAX_TURNS if settings is not None else _DEFAULT_MAX_TURNS


def _ttl_seconds() -> int:
    settings = try_get_settings()
    return settings.SESSION_TTL_SECONDS if settings is not None else _DEFAULT_TTL_SECONDS


def _use_redis() -> bool:
    settings = try_get_settings()
    return settings is not None and settings.STORAGE_MODE == "persistent"


def _append_memory(session_id: str, role: str, text: str) -> None:
    with _lock:
        if session_id not in _messages or _messages[session_id].maxlen != _max_turns():
            _messages[session_id] = deque(_messages.get(session_id, ()), maxlen=_max_turns())
        _messages[session_id].append({"role": role, "text": text})


def _get_recent_memory(session_id: str) -> list[_MessageEntry]:
    with _lock:
        return list(_messages.get(session_id, ()))


def _append_redis(session_id: str, role: str, text: str) -> None:
    client = get_redis_client()
    key = f"session_memory:{session_id}"
    client.rpush(key, json.dumps({"role": role, "text": text}, ensure_ascii=False))
    client.ltrim(key, -_max_turns(), -1)
    client.expire(key, _ttl_seconds())


def _get_recent_redis(session_id: str) -> list[_MessageEntry]:
    client = get_redis_client()
    raw_entries = client.lrange(f"session_memory:{session_id}", 0, -1)
    return [json.loads(entry) for entry in raw_entries]


def append_message(session_id: str, role: str, text: str) -> None:
    """세션에 메시지 한 건을 추가하고, 오래된 것부터 max_turns개까지만 유지한다."""
    if _use_redis():
        _append_redis(session_id, role, text)
    else:
        _append_memory(session_id, role, text)


def get_recent(session_id: str) -> list[_MessageEntry]:
    """저장된 순서(오래된 것 -> 최신) 그대로 최근 메시지를 반환한다."""
    if _use_redis():
        return _get_recent_redis(session_id)
    return _get_recent_memory(session_id)


def _reset_for_tests() -> None:
    """테스트 전용: 메모리 상태를 초기화한다 (Redis 키는 각 테스트가 직접 정리)."""
    with _lock:
        _messages.clear()
```

- [ ] **Step 4: 테스트 실행**

Run: `python -m pytest tests/data/test_session_memory_repository.py -v -m "not integration"`
Expected: 메모리 모드 테스트 2건 PASS

Run: `python -m pytest tests/data/test_session_memory_repository.py -v -m integration`
Expected: Redis 모드 테스트 1건 PASS

- [ ] **Step 5: 사용자 검토 대기**

---

## Task 9: 세션 대화 기억을 Agent 응답에 연결

**Files:**
- Modify: `backend/app/agents/runtime.py`
- Modify: `backend/app/services/agent_orchestration_service.py`
- Test: `tests/agent/test_runtime.py` (케이스 추가), `tests/agent/test_agent_orchestration_service.py` (케이스 추가)

**Interfaces:**
- Consumes: `session_memory_repository.get_recent/append_message` (Task 8)
- Produces: `run_agent(request, profile, *, provider, executor, settings, conversation_history=None)` — 기존 호출부(`conversation_history` 생략 시 `None`)는 변경 없이 동작

- [ ] **Step 1: 기존 회귀 테스트 기준선 확인**

Run: `python -m pytest tests/agent/test_runtime.py tests/agent/test_agent_orchestration_service.py -v`
Expected: 전부 PASS

- [ ] **Step 2: `runtime.py`에 실패하는 테스트 추가 — `tests/agent/test_runtime.py`**

```python
def test_conversation_history_is_appended_to_instructions() -> None:
    """이전 대화가 있으면 Provider에 전달되는 instructions에 포함되어야 한다."""
    provider = ScriptedMockProvider(
        [ModelTurn(response_id="response_1", text="이어서 답변합니다.")]
    )

    asyncio.run(
        run_agent(
            AgentAskRequest(message="그럼 먹이는 언제야?", session_id="session_1"),
            get_agent_profile("zoo_guide"),
            provider=provider,
            executor=create_executor(FakeMcpClient()),
            settings=RuntimeSettings(),
            conversation_history=[
                {"role": "user", "text": "호랑이는 어디 살아?"},
                {"role": "agent", "text": "맹수관에서 서식합니다."},
            ],
        )
    )

    sent_instructions = provider.call_history[0].instructions
    assert "호랑이는 어디 살아?" in sent_instructions
    assert "맹수관에서 서식합니다." in sent_instructions


def test_no_conversation_history_leaves_instructions_unchanged() -> None:
    """history가 없으면 instructions는 Profile 원본과 같아야 한다."""
    provider = ScriptedMockProvider(
        [ModelTurn(response_id="response_1", text="답변")]
    )
    profile = get_agent_profile("zoo_guide")

    asyncio.run(
        run_agent(
            AgentAskRequest(message="질문", session_id="session_1"),
            profile,
            provider=provider,
            executor=create_executor(FakeMcpClient()),
            settings=RuntimeSettings(),
        )
    )

    assert provider.call_history[0].instructions == profile.instructions
```

이 두 테스트는 `tests/agent/test_runtime.py`에 이미 있는 `get_agent_profile`(import), `create_executor(mcp_client)`, `FakeMcpClient` 헬퍼를 그대로 재사용한다 (파일 상단 참고, 새로 정의하지 않는다). `ScriptedMockProvider.call_history[0].instructions`는 Step 3에서 `ProviderCall`에 필드를 추가해야 존재한다.

- [ ] **Step 3: `ScriptedMockProvider.next_turn`이 `instructions`를 기록하도록 확장**

`backend/app/providers/mock_provider.py`의 `ProviderCall`에 필드 추가:

```python
@dataclass(frozen=True)
class ProviderCall:
    """Provider가 받은 한 번의 판단 요청 기록이다."""

    question: str
    instructions: str
    previous_response_id: str | None
    tool_names: tuple[str, ...]
    tool_result_names: tuple[str, ...]
```

`ScriptedMockProvider.next_turn` 안의 `ProviderCall(...)` 생성 부분에 `instructions=instructions,` 추가하고, 파일 맨 위 `del instructions` 줄은 제거한다.

- [ ] **Step 4: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/agent/test_runtime.py -v`
Expected: 새 테스트 2건 FAIL (`run_agent`에 `conversation_history` 파라미터 없음, `ProviderCall`에 `instructions` 없음)

- [ ] **Step 5: `runtime.py` 수정 — `conversation_history` 파라미터 추가 및 instructions 증강**

`run_agent` 시그니처 수정 (`backend/app/agents/runtime.py:30`):

```python
async def run_agent(
    request: AgentAskRequest,
    profile: AgentProfile,
    *,
    provider: ModelProvider,
    executor: ToolExecutor,
    settings: RuntimeSettings,
    conversation_history: list[dict] | None = None,
) -> AgentAskResponse:
```

`_run_loop` 호출부(같은 파일, `_run_loop(` 호출 지점)에 `conversation_history=conversation_history,` 인자 추가.

`_run_loop` 시그니처와 본문 수정:

```python
async def _run_loop(
    *,
    request: AgentAskRequest,
    profile: AgentProfile,
    provider: ModelProvider,
    executor: ToolExecutor,
    settings: RuntimeSettings,
    state: AgentState,
    conversation_history: list[dict] | None = None,
) -> AgentAskResponse:
    """Model 호출, Tool 실행, 결과 재전달의 반복 처리를 수행한다."""
    tool_schemas = await executor.get_tool_definitions(profile)
    previous_response_id: str | None = None
    instructions = _build_instructions(profile.instructions, conversation_history)

    # 다음 Provider 호출에는 바로 직전 턴에서 실행한 결과만 전달한다.
    previous_turn_outputs: list[ToolCallRecord] = []
```

`_run_loop` 안의 `provider.next_turn(...)` 호출에서 `instructions=profile.instructions`를 `instructions=instructions`로 변경.

파일에 헬퍼 함수 추가 (`RuntimeSettings` 클래스 정의 아래):

```python
def _build_instructions(
    base_instructions: str,
    conversation_history: list[dict] | None,
) -> str:
    """최근 대화 기록을 별도 LLM 요약 없이 텍스트로 이어붙인다."""
    if not conversation_history:
        return base_instructions

    lines = ["", "최근 대화:"]
    for message in conversation_history:
        speaker = "사용자" if message["role"] == "user" else "에이전트"
        lines.append(f"{speaker}: {message['text']}")

    return base_instructions + "\n".join(lines)
```

- [ ] **Step 6: 테스트 실행**

Run: `python -m pytest tests/agent/test_runtime.py -v`
Expected: 전부 PASS

- [ ] **Step 7: `agent_orchestration_service.py`에 실패하는 테스트 추가 — `tests/agent/test_agent_orchestration_service.py`**

```python
class FakeSessionMemoryRepository:
    """대화 기억 조회/저장을 흉내 내는 테스트용 저장소다."""

    def __init__(self) -> None:
        self.stored: dict[str, list[dict]] = {}

    def get_recent(self, session_id: str) -> list[dict]:
        return self.stored.get(session_id, [])

    def append_message(self, session_id: str, role: str, text: str) -> None:
        self.stored.setdefault(session_id, []).append({"role": role, "text": text})


def test_service_reads_and_appends_session_memory() -> None:
    """handle_ask는 실행 전 history를 읽고, 실행 후 질문/답변을 저장해야 한다."""
    session_repository = FakeSessionRepository()
    trace_repository = FakeTraceRepository()
    session_memory_repository = FakeSessionMemoryRepository()
    session_memory_repository.stored["session_existing"] = [
        {"role": "user", "text": "호랑이는 어디 살아?"}
    ]

    service = create_service(
        session_repository=session_repository,
        trace_repository=trace_repository,
        provider=ScriptedMockProvider(
            [ModelTurn(response_id="response_1", text="맹수관에서 서식합니다.")]
        ),
        session_memory_repository=session_memory_repository,
    )

    response = asyncio.run(
        service.handle_ask(
            AgentAskRequest(message="먹이는 뭐 먹어?", session_id="session_existing")
        )
    )

    stored = session_memory_repository.stored["session_existing"]
    assert stored[-2] == {"role": "user", "text": "먹이는 뭐 먹어?"}
    assert stored[-1] == {"role": "agent", "text": response.final_answer}
```

`create_service` 헬퍼(같은 파일 상단)를 아래처럼 수정한다 — `session_memory_repository`를 기본값 있는 선택 인자로 추가해, 이 값을 넘기지 않는 기존 3개 테스트(`test_service_creates_session_and_saves_trace` 등)가 계속 그대로 통과하게 한다:

```python
def create_service(
    *,
    session_repository: FakeSessionRepository,
    trace_repository: FakeTraceRepository,
    provider: ScriptedMockProvider,
    session_memory_repository: FakeSessionMemoryRepository | None = None,
) -> AgentOrchestrationService:
    """테스트 Fake 의존성을 조립한 Service를 생성한다."""

    def fake_rag_search(query: str, collection: str) -> ToolRunResult:
        """이 테스트에서는 RAG 실행이 발생하면 실패시킨다."""
        raise AssertionError(f"예상하지 못한 RAG 호출: {query}, {collection}")

    executor = ToolExecutor(
        rag_search=fake_rag_search,
        mcp_client=FakeMcpClient(),
    )

    return AgentOrchestrationService(
        session_repository=session_repository,
        trace_repository=trace_repository,
        session_memory_repository=session_memory_repository or FakeSessionMemoryRepository(),
        provider=provider,
        executor=executor,
        settings=RuntimeSettings(),
    )
```

- [ ] **Step 8: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/agent/test_agent_orchestration_service.py -v`
Expected: 새 테스트 FAIL (`AgentOrchestrationService.__init__`에 `session_memory_repository` 인자 없음)

- [ ] **Step 9: `agent_orchestration_service.py` 수정**

`SessionMemoryRepositoryProtocol` 추가 (`TraceRepositoryProtocol` 클래스 아래):

```python
class SessionMemoryRepositoryProtocol(Protocol):
    """Service가 세션 대화 기억 저장소에 요구하는 최소 기능이다."""

    def get_recent(self, session_id: str) -> list[dict]:
        """세션의 최근 대화 기록을 오래된 것부터 반환한다."""

    def append_message(self, session_id: str, role: str, text: str) -> None:
        """세션 대화 기록에 메시지 한 건을 추가한다."""
```

`AgentOrchestrationService.__init__` 시그니처에 파라미터 추가:

```python
    def __init__(
        self,
        *,
        session_repository: SessionRepositoryProtocol,
        trace_repository: TraceRepositoryProtocol,
        session_memory_repository: SessionMemoryRepositoryProtocol,
        provider: ModelProvider,
        executor: ToolExecutor,
        settings: RuntimeSettings,
    ) -> None:
        """Runtime과 저장소 의존성을 생성자에서 주입한다."""
        self._session_repository = session_repository
        self._trace_repository = trace_repository
        self._session_memory_repository = session_memory_repository
        self._provider = provider
        self._executor = executor
        self._settings = settings
```

`handle_ask` 본문 수정:

```python
    async def handle_ask(self, request: AgentAskRequest) -> AgentAskResponse:
        """질문 요청을 실행하고 Trace를 저장한 뒤 API 응답을 반환한다."""
        session_id = self._resolve_session_id(request.session_id)
        request_with_session = request.model_copy(
            update={"session_id": session_id}
        )
        profile = self._get_profile()
        history = self._session_memory_repository.get_recent(session_id)

        response = await run_agent(
            request_with_session,
            profile,
            provider=self._provider,
            executor=self._executor,
            settings=self._settings,
            conversation_history=history,
        )

        self._trace_repository.save_run(
            session_id=response.session_id,
            run_id=response.run_id,
            status=response.status,
            trace=[item.model_dump(mode="json") for item in response.trace],
        )
        self._session_memory_repository.append_message(
            session_id, "user", request.message
        )
        self._session_memory_repository.append_message(
            session_id, "agent", response.final_answer
        )

        return response
```

- [ ] **Step 10: 테스트 실행**

Run: `python -m pytest tests/agent/test_agent_orchestration_service.py -v`
Expected: 전부 PASS (기존 `create_service` 호출부도 Step 7에서 함께 수정했으므로 회귀 없음)

- [ ] **Step 11: `backend/app/main.py`에 `session_memory_repository` 배선 추가**

`main.py` import에 `from backend.app.repositories import session_memory_repository` 추가하고, `AgentOrchestrationService(...)` 생성 호출에 `session_memory_repository=session_memory_repository,` 인자 추가.

- [ ] **Step 12: 전체 회귀 테스트**

Run: `python -m pytest -q -m "not integration and not live"`
Expected: 실패 0건

- [ ] **Step 13: 사용자 검토 대기**

---

## Task 10: 헬스체크 확장 + STORAGE_MODE=persistent 종단 검증

**Files:**
- Modify: `backend/app/routers/health_router.py`
- Test: `tests/ui_mcp/test_health_admin_router.py` (케이스 추가), `tests/ui_mcp/test_main_integration_persistent.py` (신규)

**Interfaces:**
- Consumes: `backend.app.core.db.get_connection_pool`, `backend.app.core.redis_client.get_redis_client`

- [ ] **Step 1: `health_router.py`에 실패하는 테스트 추가**

```python
class FakePersistenceCheck:
    def __init__(self, postgres_ok: bool, redis_ok: bool) -> None:
        self.postgres_ok = postgres_ok
        self.redis_ok = redis_ok

    def check_postgres(self) -> bool:
        return self.postgres_ok

    def check_redis(self) -> bool:
        return self.redis_ok


def test_health_reports_persistent_storage_status() -> None:
    app = FastAPI()
    app.include_router(
        create_health_router(
            FakeMcpHealth(True),
            app_mode="mock",
            storage="persistent",
            persistence_check=FakePersistenceCheck(True, True),
        )
    )
    response = TestClient(app).get("/api/health")
    assert response.status_code == 200
    assert response.json()["storage"] == "persistent"
    assert response.json()["postgres"] == "ok"
    assert response.json()["redis"] == "ok"
```

- [ ] **Step 2: 테스트 실행 (실패 확인)**

Run: `python -m pytest tests/ui_mcp/test_health_admin_router.py -v`
Expected: 새 테스트 FAIL (`create_health_router`에 `persistence_check` 인자 없음)

- [ ] **Step 3: `health_router.py` 수정**

```python
"""Backend와 MCP 상태를 구분해 반환하는 health Router."""

from __future__ import annotations

from typing import Literal, Protocol

from fastapi import APIRouter
from fastapi.responses import JSONResponse


class McpHealthProtocol(Protocol):
    async def check_health(self) -> bool: ...


class PersistenceHealthProtocol(Protocol):
    def check_postgres(self) -> bool: ...
    def check_redis(self) -> bool: ...


def create_health_router(
    mcp_client: McpHealthProtocol,
    *,
    app_mode: Literal["mock", "openai"],
    storage: Literal["memory", "persistent"] = "memory",
    persistence_check: PersistenceHealthProtocol | None = None,
) -> APIRouter:
    router = APIRouter(tags=["health"])

    @router.get("/api/health")
    async def health() -> JSONResponse:
        mcp_ok = await mcp_client.check_health()
        payload: dict[str, object] = {
            "status": "ok" if mcp_ok else "degraded",
            "backend": "ok",
            "mcp": "ok" if mcp_ok else "unavailable",
            "storage": storage,
            "app_mode": app_mode,
        }
        status_code = 200 if mcp_ok else 503

        if storage == "persistent" and persistence_check is not None:
            postgres_ok = persistence_check.check_postgres()
            redis_ok = persistence_check.check_redis()
            payload["postgres"] = "ok" if postgres_ok else "unavailable"
            payload["redis"] = "ok" if redis_ok else "unavailable"
            if not (postgres_ok and redis_ok):
                status_code = 503
                payload["status"] = "degraded"

        return JSONResponse(status_code=status_code, content=payload)

    return router
```

- [ ] **Step 4: 테스트 실행**

Run: `python -m pytest tests/ui_mcp/test_health_admin_router.py -v`
Expected: 전부 PASS

- [ ] **Step 5: `backend/app/core/db.py`, `backend/app/core/redis_client.py`에 헬스체크 함수 추가**

`db.py` 끝에 추가:

```python
def check_postgres() -> bool:
    """Postgres 연결이 살아있는지 가볍게 확인한다."""
    try:
        pool = get_connection_pool()
        with pool.connection() as conn:
            conn.execute("SELECT 1")
        return True
    except Exception:
        return False
```

`redis_client.py` 끝에 추가:

```python
def check_redis() -> bool:
    """Redis 연결이 살아있는지 가볍게 확인한다."""
    try:
        return get_redis_client().ping() is True
    except Exception:
        return False
```

- [ ] **Step 6: `main.py`에 persistence_check 배선 추가**

`main.py` import에 추가:

```python
from backend.app.core import db as db_module
from backend.app.core import redis_client as redis_client_module
```

작은 어댑터 클래스를 `create_app` 위에 추가:

```python
class _PersistenceHealth:
    """core/db.py, core/redis_client.py의 함수를 health_router 계약으로 묶는다."""

    def check_postgres(self) -> bool:
        return db_module.check_postgres()

    def check_redis(self) -> bool:
        return redis_client_module.check_redis()
```

`create_health_router(...)` 호출에 `persistence_check=_PersistenceHealth() if settings.STORAGE_MODE == "persistent" else None,` 인자 추가.

- [ ] **Step 7: 종단 통합 테스트 작성 — `tests/ui_mcp/test_main_integration_persistent.py`**

```python
"""STORAGE_MODE=persistent로 main.py를 띄워 /api/health를 검증한다 (실제 Postgres/Redis 필요)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.core.db import ensure_schema, get_connection_pool
from backend.app.main import create_app

pytestmark = pytest.mark.integration


def test_health_ok_when_postgres_and_redis_reachable() -> None:
    settings = Settings(
        _env_file=None,
        APP_MODE="mock",
        STORAGE_MODE="persistent",
        DATABASE_URL="postgresql://zoo:zoo@127.0.0.1:5432/zoo",
        REDIS_URL="redis://127.0.0.1:6380/0",
        MCP_SERVER_URL="http://127.0.0.1:1/mcp",  # 이 테스트는 MCP는 검사하지 않음
    )
    ensure_schema(get_connection_pool(dsn=settings.DATABASE_URL))

    with TestClient(create_app(settings)) as client:
        response = client.get("/api/health")

    assert response.json()["storage"] == "persistent"
    assert response.json()["postgres"] == "ok"
    assert response.json()["redis"] == "ok"
```

- [ ] **Step 8: 테스트 실행**

Run: `python -m pytest tests/ui_mcp/test_main_integration_persistent.py -v -m integration`
Expected: PASS

- [ ] **Step 9: 전체 회귀 테스트 (마지막 확인)**

Run: `python -m pytest -q -m "not integration and not live"`
Run: `python -m pytest -q -m integration`
Expected: 두 실행 모두 실패 0건

- [ ] **Step 10: 사용자 검토 대기 — 이 서브프로젝트(1/5) 완료 보고**

Step 1~9 결과, 새로 생기거나 바뀐 파일 목록, `docker compose -f infra/docker-compose.yml ps` 결과를 사용자에게 보여준다. 커밋은 사용자가 명시적으로 요청할 때만 실행한다. 승인되면 서브프로젝트 2(문서 업로드 + PDF RAG 변환)의 브레인스토밍으로 넘어간다.
