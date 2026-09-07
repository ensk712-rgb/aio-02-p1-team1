# 손영민 P0 작업 보고서

## 담당 범위

- Agent 공통 Schema
- `zoo_guide` Agent Profile과 Registry
- Mock/OpenAI Provider
- Tool Registry와 안전 Executor
- Agent Runtime
- Agent Orchestration Service
- `POST /api/agent/ask` Router
- 정책·반복·금지 요청 테스트
- Agent 정책 평가 시나리오

## 실행 환경

- Python: 3.12.7
- 가상환경: `.venv`
- 테스트 도구: pytest 8.4.2
- 실행 위치: 프로젝트 루트

## 실행 명령

```bash
source .venv/bin/activate
python -m pytest tests/agent tests/integration/policy -v