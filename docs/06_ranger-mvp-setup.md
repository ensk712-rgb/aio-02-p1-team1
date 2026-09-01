# 레인저 에이전트 MVP 실행 방법

`plan.md` 1장에 정의한 MVP 범위(RAG + 조회 Tool + 예약 승인 흐름, 로그인·SSE·MCP·Multimodal 제외)의 첫 baseline입니다.

## 0. 전제 조건 (이미 떠 있음)

이 프로젝트는 `docker ps`로 확인되는 아래 컨테이너를 그대로 사용합니다. 새로 띄울 필요 없습니다.

- `aidevs-pgvector` (pgvector/pgvector:pg16, `127.0.0.1:5433`) — `documents`, `conversation_messages` 테이블 재사용
- `aidevs-redis` (redis:7, `127.0.0.1:6379`) — 승인 대기(pending action) TTL 저장
- Ollama (`127.0.0.1:11434`, `embeddinggemma` 모델) — RAG 임베딩, 무료·로컬
- `backend/.env`의 `OPENAI_API_KEY` — 답변 생성과 Tool 선택(Tool Calling)에 사용

## 1. 의존성 설치

```bash
pip install -r requirements.txt
```

## 2. RAG 문서 색인 (최초 1회, 문서 바뀔 때마다 재실행)

```bash
cd backend
python scripts/ingest.py
```

`data/animal_card_tiger.md`, `data/habitat_marine.md`, `data/faq.md` 3종을 chunk해 `documents` 테이블에 `collection_name=ranger_zoo_documents`로 저장합니다. 기존 색인은 실행할 때마다 지우고 다시 씁니다.

## 3. 백엔드 실행

```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

확인: `GET http://127.0.0.1:8000/api/health` → `{"status": "ok"}`

## 4. 프론트엔드 실행

```bash
streamlit run frontend/app.py
```

## 5. 동작 확인 시나리오

| 질문 | 기대 경로 |
|---|---|
| "이 호랑이는 몇 살이야?" | RAG — 동물 정보카드에서 근거 답변 |
| "물개 먹이시간 알려줘" | TOOL — `get_feeding_schedule` |
| "맹수사 오늘 휴장이야?" | TOOL — `check_closure_status` |
| "15시 사육사체험 2명 예약해줘" | TOOL(승인 필요) — 확인 카드 표시 → 확인 버튼 클릭 시 실제 예약 |
| "이 호랑이 성격 어때?" (자료에 없음) | RAG — "확인할 수 없는 내용이에요" |

## 다음으로 남은 것 (MVP 이후)

- 로그인 · 어드민 콘솔 (이원민)
- SSE 스트리밍 응답 (이원민)
- MCP Server 분리 (이원민)
- Multimodal: STT/TTS, 사진으로 동물 찾기 (이원민)
- 평가 시나리오 자동화 (최두나, `plan.md` 9장)
- `agents/routing_agent.py`, `tools/zoo_tools.py`, 승인 흐름 고도화 (손영민)

세부 담당은 `plan.md` 9장 역할 분담을 따릅니다.
