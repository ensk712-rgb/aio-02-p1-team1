"""Agent Router의 HTTP 요청 검증과 오류 상태 코드를 검증한다."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.routers.agent_router import create_agent_router
from backend.app.schemas.agent import AgentAskRequest, AgentAskResponse
from backend.app.services.agent_orchestration_service import InvalidSessionError


class FakeAgentService:
    """Router 테스트에서 정해진 응답을 반환하는 가짜 Agent Service다."""

    def __init__(self) -> None:
        self.received_requests: list[AgentAskRequest] = []
        self.received_auth_session_ids: list[str | None] = []
        self.raise_invalid_session = False
        self.raise_unexpected_error = False

    async def handle_ask(
        self,
        request: AgentAskRequest,
        *,
        auth_session_id: str | None = None,
    ) -> AgentAskResponse:
        """요청과 로그인 세션을 기록하고 설정에 맞는 응답 또는 예외를 반환한다."""
        self.received_requests.append(request)
        self.received_auth_session_ids.append(auth_session_id)

        if self.raise_invalid_session:
            raise InvalidSessionError("가짜 만료된 세션")

        if self.raise_unexpected_error:
            raise RuntimeError("내부 구현 상세사항은 HTTP로 노출하면 안 됩니다.")

        return AgentAskResponse(
            run_id="run_router_test",
            agent_id="zoo_guide",
            session_id=request.session_id or "session_router_test",
            intent=None,
            status="completed",
            termination_reason="model_finished",
            final_answer="테스트 응답입니다.",
            sources=[],
            tool_calls=[],
            pending_action=None,
            trace=[],
        )


def create_client(service: FakeAgentService) -> TestClient:
    """Fake Service가 연결된 독립 FastAPI 테스트 앱을 생성한다."""
    app = FastAPI()
    app.include_router(create_agent_router(service))
    return TestClient(app)


def test_ask_agent_returns_service_response() -> None:
    """정상 JSON 요청은 Service 응답을 HTTP 200으로 반환해야 한다."""
    service = FakeAgentService()
    client = create_client(service)

    response = client.post(
        "/api/agent/ask",
        json={"message": "펭귄 먹이시간 알려줘", "session_id": None},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "completed"
    assert response.json()["session_id"] == "session_router_test"
    assert service.received_requests[0].message == "펭귄 먹이시간 알려줘"
    assert service.received_auth_session_ids == [None]


def test_ask_agent_forwards_auth_session_header() -> None:
    """예약용 로그인 세션 헤더는 Agent Service까지 전달되어야 한다."""
    service = FakeAgentService()
    client = create_client(service)

    response = client.post(
        "/api/agent/ask",
        json={"message": "사육사 체험 2명 예약해 줘", "session_id": None},
        headers={"X-Auth-Session": "auth_router_test"},
    )

    assert response.status_code == 200
    assert service.received_auth_session_ids == ["auth_router_test"]


def test_ask_agent_rejects_unknown_request_field() -> None:
    """정의되지 않은 JSON 필드는 HTTP 422로 거절해야 한다."""
    service = FakeAgentService()
    client = create_client(service)

    response = client.post(
        "/api/agent/ask",
        json={
            "message": "펭귄 먹이시간 알려줘",
            "session_id": None,
            "tool_name": "delete_database",
        },
    )

    assert response.status_code == 422
    assert service.received_requests == []


def test_ask_agent_returns_403_for_invalid_session() -> None:
    """유효하지 않은 대화 세션은 일반 안내 문장과 HTTP 403을 반환해야 한다."""
    service = FakeAgentService()
    service.raise_invalid_session = True
    client = create_client(service)

    response = client.post(
        "/api/agent/ask",
        json={"message": "질문", "session_id": "session_forged"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "유효하지 않거나 만료된 세션입니다."


def test_ask_agent_hides_unexpected_error_details() -> None:
    """예상하지 못한 예외의 내부 상세 정보는 HTTP 응답에 노출하면 안 된다."""
    service = FakeAgentService()
    service.raise_unexpected_error = True
    client = create_client(service)

    response = client.post(
        "/api/agent/ask",
        json={"message": "질문", "session_id": None},
    )

    assert response.status_code == 500
    assert response.json()["detail"] == (
        "요청 처리 중 문제가 발생했습니다. 잠시 후 다시 시도해 주세요."
    )
    assert "내부 구현" not in response.text


def test_stream_agent_returns_delta_and_done_events() -> None:
    service = FakeAgentService()
    client = create_client(service)

    response = client.post(
        "/api/agent/ask/stream",
        json={"message": "펭귄 먹이시간 알려줘"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert "event: delta" in response.text
    assert '"text": "테스트 응답입니다."' in response.text
    assert "event: done" in response.text
    assert '"session_id": "session_router_test"' in response.text
