"""Frontend HTTP Client의 성공/실패 변환 시험."""

from __future__ import annotations

import httpx
import pytest

from frontend.clients.agent_client import AgentClient, AgentClientError


def test_ask_omits_empty_session_id(monkeypatch) -> None:
    captured = {}

    def fake_request(method, url, **kwargs):
        captured.update(kwargs["json"])
        return httpx.Response(200, json={"status": "completed"})

    monkeypatch.setattr(httpx, "request", fake_request)
    response = AgentClient("http://backend").ask("질문", None)
    assert response["status"] == "completed"
    assert captured == {"message": "질문"}


@pytest.mark.parametrize(
    ("exception", "kind"),
    [
        (httpx.ConnectError("offline"), "connection"),
        (httpx.ReadTimeout("slow"), "timeout"),
    ],
)
def test_transport_errors_are_sanitized(monkeypatch, exception, kind) -> None:
    def fail(*args, **kwargs):
        raise exception

    monkeypatch.setattr(httpx, "request", fail)
    with pytest.raises(AgentClientError) as captured:
        AgentClient("http://backend").get_health()
    assert captured.value.kind == kind
    assert "offline" not in str(captured.value)
    assert "slow" not in str(captured.value)


def test_non_success_and_invalid_json_are_not_success(monkeypatch) -> None:
    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: httpx.Response(503, json={"status": "degraded"}),
    )
    with pytest.raises(AgentClientError) as http_error:
        AgentClient("http://backend").get_health()
    assert http_error.value.kind == "http"

    monkeypatch.setattr(
        httpx,
        "request",
        lambda *args, **kwargs: httpx.Response(200, text="not-json"),
    )
    with pytest.raises(AgentClientError) as invalid:
        AgentClient("http://backend").get_health()
    assert invalid.value.kind == "invalid_response"
