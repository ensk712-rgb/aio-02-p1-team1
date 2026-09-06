"""레인저 에이전트 백엔드 진입점입니다.

MVP 범위: RAG(동물 지식) + Tool(실시간 정보·체험 예약 승인 흐름) 하나의 챗봇 경로만
제공합니다. 로그인은 DB 값 일치만 확인하는 최소 범위이며, SSE와 Multimodal은 이후 스프린트에서 추가합니다
(plan.md 1장 MVP 범위 참고).
"""

from fastapi import FastAPI

from app.routers.agent_router import agent_router
from app.routers.auth_router import auth_router

app = FastAPI(title="레인저 에이전트 · MVP")
app.include_router(auth_router)
app.include_router(agent_router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
