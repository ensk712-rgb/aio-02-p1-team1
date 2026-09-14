# 빌드 컨텍스트는 프로젝트 루트여야 한다 (backend/app이 `from backend.app...`처럼
# 저장소 루트 기준 절대 import를 쓰기 때문). compose.yml에서
#   build: { context: ., dockerfile: backend/Dockerfile }
# 로 지정한다.
FROM python:3.12-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# backend 패키지 전체(app/, scripts/, __init__.py)와, Settings.DATA_DIR이 가리키는
# data/를 그대로 복사한다. .env는 이미지에 담지 않고 실행 시 env_file로 주입한다.
COPY backend backend
COPY data data

ENV PYTHONPATH=/app
EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
