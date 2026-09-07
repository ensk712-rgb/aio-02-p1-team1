"""시나리오 평가 실행기 (최두나 소유, 작업지시서 v1.1 5장/10.3절).

시나리오 JSON 배열을 읽어 **실행 중인 Backend를 실제 HTTP로 호출**하고,
응답의 status/tool_calls/sources를 시나리오의 expected와 비교한다.
문장 전체 일치는 요구하지 않고, LLM Judge도 쓰지 않는다 (10.3절).

지금은 POST /api/agent/ask가 아직 구현되지 않았다(손영민 담당, Gate 0 이후).
이 모듈은 그 API가 준비되는 즉시 그대로 붙을 수 있도록 계약만 먼저 고정해 둔
"실행기 골격"이다 — 서버에 연결할 수 없으면 예외를 올리지 않고 각 시나리오를
outcome="SKIP"으로 기록한다.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

ASK_PATH = "/api/agent/ask"


def load_scenarios(scenario_paths: list[str | Path]) -> list[dict[str, Any]]:
    """여러 시나리오 JSON 파일(각각 배열)을 읽어 하나의 목록으로 합친다."""
    scenarios: list[dict[str, Any]] = []
    for raw_path in scenario_paths:
        path = Path(raw_path)
        with path.open(encoding="utf-8") as f:
            payload = json.load(f)
        if not isinstance(payload, list):
            raise ValueError(f"{path}는 시나리오 배열(JSON list)이어야 한다")
        scenarios.extend(payload)
    return scenarios


def _evaluate(scenario: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
    """문장 전체 일치 대신 상태·Tool·출처 개수만 비교한다."""
    expected = scenario["expected"]
    actual_status = response.get("status")
    tool_names = {call.get("name") for call in response.get("tool_calls", [])}
    sources_count = len(response.get("sources", []))

    failures: list[str] = []

    if actual_status != expected["status"]:
        failures.append(f"status: expected={expected['status']!r} actual={actual_status!r}")

    missing = set(expected.get("required_tools", [])) - tool_names
    if missing:
        failures.append(f"required_tools 누락: {sorted(missing)}")

    forbidden_hit = set(expected.get("forbidden_tools", [])) & tool_names
    if forbidden_hit:
        failures.append(f"forbidden_tools 호출됨: {sorted(forbidden_hit)}")

    min_sources = expected.get("min_sources", 0)
    if sources_count < min_sources:
        failures.append(f"min_sources 미달: expected>={min_sources} actual={sources_count}")

    answer = response.get("final_answer", "")
    if not isinstance(answer, str):
        answer = ""
    forbidden_fragments = expected.get("forbidden_answer_fragments", [])
    leaked_fragments = [fragment for fragment in forbidden_fragments if fragment in answer]
    if leaked_fragments:
        failures.append(f"금지 답변 포함: {leaked_fragments}")

    return {
        "id": scenario["id"],
        "priority": scenario.get("priority"),
        "message": scenario["message"],
        "outcome": "PASS" if not failures else "FAIL",
        "failures": failures,
        "actual_response": response,
    }


def _skip_result(scenario: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "id": scenario["id"],
        "priority": scenario.get("priority"),
        "message": scenario["message"],
        "outcome": "SKIP",
        "failures": [reason],
        "actual_response": None,
    }


async def run_scenarios(
    base_url: str,
    scenario_paths: list[str | Path],
    *,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """시나리오를 읽어 base_url의 /api/agent/ask를 실제로 호출하고 결과를 모은다.

    client: 테스트에서 httpx.MockTransport로 만든 AsyncClient를 주입할 수 있다.
    생략하면 base_url로 실제 HTTP 연결을 시도한다.
    """
    scenarios = load_scenarios(scenario_paths)
    owns_client = client is None
    http_client = client or httpx.AsyncClient(base_url=base_url, timeout=10.0)

    results: list[dict[str, Any]] = []
    try:
        for scenario in scenarios:
            setup = scenario.get("setup")
            if isinstance(setup, dict) and setup:
                results.append(
                    _skip_result(
                        scenario,
                        "장애 주입 전용 시나리오입니다. tests/ui_mcp의 대응 시험으로 판정하세요.",
                    )
                )
                continue
            try:
                response = await http_client.post(
                    ASK_PATH,
                    json={"message": scenario["message"], "session_id": None},
                )
            except httpx.ConnectError:
                results.append(
                    _skip_result(
                        scenario,
                        f"{base_url}{ASK_PATH}에 연결할 수 없음 "
                        "(API 미구현이거나 서버가 기동되지 않음)",
                    )
                )
                continue
            except httpx.TimeoutException:
                results.append(_skip_result(scenario, f"{base_url}{ASK_PATH} 응답 timeout"))
                continue

            if response.status_code != 200:
                results.append(
                    {
                        "id": scenario["id"],
                        "priority": scenario.get("priority"),
                        "message": scenario["message"],
                        "outcome": "FAIL",
                        "failures": [f"HTTP {response.status_code}: {response.text[:200]}"],
                        "actual_response": None,
                    }
                )
                continue

            results.append(_evaluate(scenario, response.json()))
    finally:
        if owns_client:
            await http_client.aclose()

    return results


def summarize(results: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"PASS": 0, "FAIL": 0, "SKIP": 0}
    for result in results:
        summary[result["outcome"]] += 1
    return summary
