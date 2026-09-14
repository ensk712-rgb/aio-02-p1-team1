# 빌드 컨텍스트는 프로젝트 루트여야 한다 (frontend/*.py가 `from frontend.bootstrap...`처럼
# 저장소 루트 기준 절대 import를 쓰기 때문). compose.yml에서
#   build: { context: ., dockerfile: frontend/Dockerfile }
# 로 지정한다.
FROM python:3.12-slim

WORKDIR /app

COPY frontend/requirements.txt frontend/requirements.txt
RUN pip install --no-cache-dir -r frontend/requirements.txt

# frontend 패키지 전체(app.py, bootstrap.py, app_pages/, components/, clients/,
# styles.py, ui.py, resources/, image/, __init__.py)를 그대로 복사한다.
# .env는 이미지에 담지 않고 실행 시 env_file로 주입한다.
COPY frontend frontend

ENV PYTHONPATH=/app
EXPOSE 8501

CMD ["streamlit", "run", "frontend/app.py", "--server.address=0.0.0.0", "--server.port=8501"]
