# 빌드 컨텍스트는 프로젝트 루트여야 한다. mcp_server/server.py가
# `from backend.app.core.config import get_settings`로 backend 코드를 그대로
# import하기 때문에 backend 패키지도 함께 담아야 한다. compose.yml에서
#   build: { context: ., dockerfile: mcp_server/Dockerfile }
# 로 지정한다.
FROM python:3.12-slim

WORKDIR /app

COPY mcp_server/requirements.txt mcp_server/requirements.txt
RUN pip install --no-cache-dir -r mcp_server/requirements.txt

# mcp_server 자체 코드 + settings를 위해 필요한 backend 코드를 복사한다.
# (.env는 이미지에 담지 않고 실행 시 env_file로 주입 — backend/.env를 그대로 쓴다.)
COPY mcp_server mcp_server
COPY backend backend

ENV PYTHONPATH=/app
EXPOSE 8100

CMD ["python", "-m", "mcp_server.server"]
