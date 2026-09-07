"""C5 확인 테스트: 평가 실행기 골격 (최두나 소유).

httpx.MockTransport로 가짜 Backend 응답을 만들어, 실제 서버 없이도
run_scenarios()의 비교 로직과 SKIP 처리를 검증한다. asyncio.run()으로
직접 실행해 pytest-asyncio 없이도 async 함수를 테스트한다.
"""

import asyncio
import json

import httpx
import pytest

from backend.app.services import eval_service


def _scenario_file(tmp_path, scenarios):
    path = tmp_path / "scenarios.json"
    path.write_text(json.dumps(scenarios), encoding="utf-8")
    return path


def _run(base_url, scenario_paths, transport):
    async def _inner():
        async with httpx.AsyncClient(transport=transport, base_url=base_url) as client:
            return await eval_service.run_scenarios(base_url, scenario_paths, client=client)

    return asyncio.run(_inner())


SCENARIO_N01 = {
    "id": "N-01",
    "priority": "P0",
    "message": "호랑이는 어디에서 살고 무엇을 먹어?",
    "expected": {
        "status": "completed",
        "required_tools": ["retrieve_animal_info"],
        "forbidden_tools": [],
        "min_sources": 1,
    },
}


def test_pass_when_response_matches_expected(tmp_path):
    scenario_path = _scenario_file(tmp_path, [SCENARIO_N01])

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/agent/ask"
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "tool_calls": [{"name": "retrieve_animal_info"}],
                "sources": [{"doc_id": "ANIMAL-TIGER", "title": "호랑이", "page": 1, "score": 0.8}],
            },
        )

    results = _run("http://test", [scenario_path], httpx.MockTransport(handler))

    assert results[0]["outcome"] == "PASS"
    assert results[0]["failures"] == []


def test_fail_when_status_mismatches(tmp_path):
    scenario_path = _scenario_file(tmp_path, [SCENARIO_N01])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"status": "error", "tool_calls": [], "sources": []})

    results = _run("http://test", [scenario_path], httpx.MockTransport(handler))

    assert results[0]["outcome"] == "FAIL"
    assert any("status" in f for f in results[0]["failures"])


def test_fail_when_required_tool_missing(tmp_path):
    scenario_path = _scenario_file(tmp_path, [SCENARIO_N01])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "tool_calls": [],
                "sources": [{"doc_id": "ANIMAL-TIGER", "title": "호랑이", "page": 1, "score": 0.8}],
            },
        )

    results = _run("http://test", [scenario_path], httpx.MockTransport(handler))

    assert results[0]["outcome"] == "FAIL"
    assert any("required_tools" in f for f in results[0]["failures"])


def test_fail_when_forbidden_tool_called(tmp_path):
    scenario = {
        **SCENARIO_N01,
        "expected": {**SCENARIO_N01["expected"], "forbidden_tools": ["reserve_experience_program"]},
    }
    scenario_path = _scenario_file(tmp_path, [scenario])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "tool_calls": [
                    {"name": "retrieve_animal_info"},
                    {"name": "reserve_experience_program"},
                ],
                "sources": [{"doc_id": "ANIMAL-TIGER", "title": "호랑이", "page": 1, "score": 0.8}],
            },
        )

    results = _run("http://test", [scenario_path], httpx.MockTransport(handler))

    assert results[0]["outcome"] == "FAIL"
    assert any("forbidden_tools" in f for f in results[0]["failures"])


def test_fail_when_min_sources_not_met(tmp_path):
    scenario_path = _scenario_file(tmp_path, [SCENARIO_N01])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"status": "completed", "tool_calls": [{"name": "retrieve_animal_info"}], "sources": []},
        )

    results = _run("http://test", [scenario_path], httpx.MockTransport(handler))

    assert results[0]["outcome"] == "FAIL"
    assert any("min_sources" in f for f in results[0]["failures"])


def test_fail_when_forbidden_answer_fragment_is_present(tmp_path):
    scenario = {
        **SCENARIO_N01,
        "expected": {
            **SCENARIO_N01["expected"],
            "forbidden_answer_fragments": ["허위 운영시간"],
        },
    }
    scenario_path = _scenario_file(tmp_path, [scenario])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "status": "completed",
                "tool_calls": [{"name": "retrieve_animal_info"}],
                "sources": [{"doc_id": "ANIMAL-TIGER"}],
                "final_answer": "허위 운영시간을 안내합니다.",
            },
        )

    results = _run("http://test", [scenario_path], httpx.MockTransport(handler))
    assert results[0]["outcome"] == "FAIL"
    assert any("금지 답변" in failure for failure in results[0]["failures"])


def test_skip_when_scenario_requires_failure_injection(tmp_path):
    scenario = {**SCENARIO_N01, "setup": {"mcp_failure": "timeout"}}
    scenario_path = _scenario_file(tmp_path, [scenario])
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return httpx.Response(200, json={})

    results = _run("http://test", [scenario_path], httpx.MockTransport(handler))
    assert results[0]["outcome"] == "SKIP"
    assert "장애 주입" in results[0]["failures"][0]
    assert called is False


def test_skip_when_backend_unreachable(tmp_path):
    """API가 아직 구현되지 않았거나 서버가 꺼져 있으면 SKIP으로 기록하고 예외를 올리지 않는다."""
    scenario_path = _scenario_file(tmp_path, [SCENARIO_N01])

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused", request=request)

    results = _run("http://test", [scenario_path], httpx.MockTransport(handler))

    assert results[0]["outcome"] == "SKIP"
    assert len(results[0]["failures"]) == 1


def test_fail_when_http_error_status(tmp_path):
    scenario_path = _scenario_file(tmp_path, [SCENARIO_N01])

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="internal error")

    results = _run("http://test", [scenario_path], httpx.MockTransport(handler))

    assert results[0]["outcome"] == "FAIL"
    assert "500" in results[0]["failures"][0]


def test_load_scenarios_merges_multiple_files(tmp_path):
    path_a = _scenario_file(tmp_path, [SCENARIO_N01])
    scenario_b = {**SCENARIO_N01, "id": "N-01b"}
    path_b = tmp_path / "b.json"
    path_b.write_text(json.dumps([scenario_b]), encoding="utf-8")

    scenarios = eval_service.load_scenarios([path_a, path_b])

    assert [s["id"] for s in scenarios] == ["N-01", "N-01b"]


def test_load_scenarios_rejects_non_list_payload(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"not": "a list"}), encoding="utf-8")

    with pytest.raises(ValueError):
        eval_service.load_scenarios([path])


def test_summarize_counts_outcomes():
    results = [
        {"outcome": "PASS"},
        {"outcome": "PASS"},
        {"outcome": "FAIL"},
        {"outcome": "SKIP"},
    ]
    assert eval_service.summarize(results) == {"PASS": 2, "FAIL": 1, "SKIP": 1}
