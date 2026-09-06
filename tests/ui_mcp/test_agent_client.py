import httpx
import pytest

from frontend.clients.agent_client import AgentClient, AgentClientError


def test_login_uses_auth_contract_without_returning_password(monkeypatch) -> None:
    seen = {}

    def fake_request(method, url, **kwargs):
        seen.update(method=method, url=url, json=kwargs["json"])
        return httpx.Response(
            200,
            json={"authenticated": True, "user_id": "TEST"},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx, "request", fake_request)
    result = AgentClient("http://backend").login("TEST", "secret-value")

    assert seen == {
        "method": "POST",
        "url": "http://backend/api/auth/login",
        "json": {"user_id": "TEST", "password": "secret-value"},
    }
    assert result == {"authenticated": True, "user_id": "TEST"}
    assert "password" not in result
    assert "secret-value" not in str(result)


def test_ask_sends_only_message_and_session(monkeypatch) -> None:
    seen = {}
    def fake_request(method, url, **kwargs):
        seen.update(method=method, url=url, json=kwargs["json"])
        return httpx.Response(200, json={"status": "completed", "final_answer": "ok"}, request=httpx.Request(method, url))
    monkeypatch.setattr(httpx, "request", fake_request)
    result = AgentClient("http://backend").ask("먹이시간", None)
    assert result["status"] == "completed"
    assert seen["json"] == {"message": "먹이시간"}


def test_ask_includes_existing_session_id(monkeypatch) -> None:
    seen = {}

    def fake_request(method, url, **kwargs):
        seen.update(method=method, url=url, json=kwargs["json"])
        return httpx.Response(200, json={"status": "completed", "final_answer": "ok"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "request", fake_request)
    AgentClient("http://backend").ask("먹이시간", "session-1")

    assert seen["json"] == {"message": "먹이시간", "session_id": "session-1"}


def test_http_failure_becomes_safe_ui_error(monkeypatch) -> None:
    def fail(*args, **kwargs):
        raise httpx.ConnectError("token=must-not-leak")
    monkeypatch.setattr(httpx, "request", fail)
    with pytest.raises(AgentClientError) as caught:
        AgentClient().get_health()
    assert "token" not in str(caught.value)


def test_http_status_failure_is_not_reported_as_connection_failure(monkeypatch) -> None:
    def fail(method, url, **kwargs):
        return httpx.Response(
            502,
            json={"detail": "database password=must-not-leak"},
            request=httpx.Request(method, url),
        )

    monkeypatch.setattr(httpx, "request", fail)
    with pytest.raises(AgentClientError) as caught:
        AgentClient().ask("판다는 어디에 있어?")

    assert str(caught.value) == "백엔드 요청 처리에 실패했습니다. (HTTP 502)"
    assert "password" not in str(caught.value)
