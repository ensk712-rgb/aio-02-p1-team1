"""애플리케이션 설정.

작업지시서 v1.1 5장/12.1절 계약:
- 환경변수와 같은 이름의 필드를 사용한다.
- PROJECT_ROOT/DATA_DIR은 __file__ 기준 절대경로로 계산한다.
- 다른 모듈은 .env를 다시 읽거나 별도 기본값을 만들지 않고 이 Settings를 통해서만 값을 얻는다.
"""

from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> 프로젝트 루트는 세 단계 위
PROJECT_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 실행 모드
    APP_MODE: Literal["mock", "openai"] = "mock"
    STORAGE_MODE: Literal["memory", "persistent"] = "memory"

    # OpenAI Provider
    OPENAI_MODEL: str = "gpt-4.1-mini"
    OPENAI_API_KEY: str = ""

    # 관리자 인증
    ADMIN_TOKEN: str = ""

    # MCP 연결
    MCP_SERVER_URL: str = "http://192.100.200.199:8100/mcp"
    MCP_HOST: str = "127.0.0.1"
    MCP_PORT: int = 8100

    # Backend 자체 주소
    BACKEND_URL: str = "http://192.100.200.198:8000/"
    CORS_ALLOW_ORIGINS: str = "http://localhost:8501"

    # RAG 설정
    RAG_TOP_K: int = 3
    RAG_MIN_SCORE: float = 0.5

    # P1: pgvector/Redis 전환 (STORAGE_MODE=persistent일 때만 사용)
    DATABASE_URL: str = ""
    REDIS_URL: str = ""
    SESSION_MEMORY_MAX_TURNS: int = 6
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_RETRY_COUNT: int = 1

    # Runtime 실행 한도
    MAX_AGENT_STEPS: int = 6
    MAX_SAME_TOOL_CALLS: int = 2
    MAX_TOOL_CALLS: int = 8
    RUN_TIMEOUT_SECONDS: int = 90
    MCP_TIMEOUT_SECONDS: int = 10
    MCP_RETRY_COUNT: int = 1

    # P1: 예약 승인 / 세션
    PENDING_TTL_SECONDS: int = 120
    SESSION_TTL_SECONDS: int = 7200

    # 예약/확인대기 영구 저장 (STORAGE_MODE의 pgvector/Redis 전환과는 별개 스위치다 —
    # 예약만 먼저 Postgres로 옮기고 RAG/세션은 memory로 남겨두는 조합도 가능해야 한다)
    RESERVATION_STORAGE_MODE: Literal["memory", "persistent"] = "memory"

    # 교육용 Mock "지금" 기준 시각. 비우면 실제 Asia/Seoul 현재 시간을 쓴다.
    # 승인 TTL·세션 TTL·전체 timeout에는 적용하지 않는다(실제 시계 사용).
    DEMO_NOW: str = ""

    # P1-B: 맞춤 코스 추천 날씨 Tool (Open-Meteo). 비상업용 Forecast API는 키
    # 없이도 호출 가능하므로 비워 둬도 된다 — 나중에 유료/커머셜 티어로 옮길
    # 때만 채운다(P1-B 계획서 §5.2.1).
    OPEN_METEO_API_KEY: str = ""

    @property
    def project_root(self) -> Path:
        return PROJECT_ROOT

    @property
    def data_dir(self) -> Path:
        return DATA_DIR

    def demo_now_datetime(self) -> "datetime | None":
        """DEMO_NOW를 timezone 포함 datetime으로 변환한다. 비어 있으면 None."""
        if not self.DEMO_NOW:
            return None
        return datetime.fromisoformat(self.DEMO_NOW)


@lru_cache
def get_settings() -> Settings:
    """프로세스 전체에서 재사용하는 단일 Settings 인스턴스."""
    return Settings()


class _LazySettings:
    """`from app.core.config import settings`를 지원하기 위한 지연 프록시.

    모듈 import 시점에 바로 Settings()를 생성하면 .env에 이 프로젝트와 무관한
    값(다른 실습의 APP_MODE 등)이 남아 있을 때 아무 코드도 실행하지 않았는데도
    import 자체가 깨진다. 실제 속성에 접근하는 시점까지 생성을 미뤄서
    get_settings()/try_get_settings()와 동일한 지연 로딩 원칙을 지킨다.
    """

    def __getattr__(self, name: str):
        return getattr(get_settings(), name)


# 다른 모듈에서 `from app.core.config import settings`로 바로 쓸 수 있도록 하는
# 모듈 레벨 싱글턴(지연 로딩). 실제로는 get_settings()와 동일한 인스턴스를 가리킨다.
settings = _LazySettings()


def try_get_settings() -> "Settings | None":
    """Settings 로딩에 실패해도 예외를 올리지 않는 버전.

    .env에 이 프로젝트와 무관한 값(예: 다른 실습의 APP_MODE)이 남아 있어도
    PROJECT_ROOT/DATA_DIR처럼 __file__ 기준으로 계산되는 경로는 항상 접근 가능해야
    하므로, 그런 값에 의존하지 않는 모듈은 이 함수로 임계값(RAG_MIN_SCORE 등)만
    선택적으로 읽고 실패 시 자체 기본값을 쓴다.
    """
    try:
        return get_settings()
    except Exception:
        return None
