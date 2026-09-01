"""환경변수를 한곳에서 읽어 settings로 제공합니다.

`backend/.env`를 always 기준으로 읽기 때문에, uvicorn이나 scripts를 어느 위치에서
실행하든 같은 값을 봅니다. providers/*, repositories/*, services/*가 모두 이 settings를
사용합니다.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore")

    # LLM Provider (providers/registry.py가 그대로 사용)
    llm_provider: str = "openai"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = ""
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_model: str = "llama3.2"
    request_timeout_seconds: float = 60

    # RAG 임베딩 (Ollama 로컬 임베딩 — 무료, API 키 불필요)
    ollama_embedding_model: str = "embeddinggemma"
    ranger_collection: str = "ranger_zoo_documents"
    rag_min_score: float = 0.35

    # 저장소
    database_url: str = "postgresql://agent_user:agent_password@127.0.0.1:5433/agent_db"
    redis_url: str = "redis://127.0.0.1:6379/0"
    pending_action_ttl_seconds: int = 120


settings = Settings()
