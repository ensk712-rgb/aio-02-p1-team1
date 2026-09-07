"""L6 평가 시나리오의 실패 방지 계약을 고정한다."""

from __future__ import annotations

import json
from pathlib import Path


SCENARIO_PATH = Path(__file__).resolve().parents[2] / "eval" / "scenarios" / "mcp.json"


def test_a03_and_a14_forbid_fabricated_operational_answers() -> None:
    scenarios = {item["id"]: item for item in json.loads(SCENARIO_PATH.read_text(encoding="utf-8"))}

    timeout = scenarios["A-03"]
    assert timeout["setup"] == {"mcp_failure": "timeout"}
    assert timeout["expected"]["status"] == "error"
    assert timeout["expected"]["mcp_attempts"] == 2
    assert timeout["expected"]["forbidden_answer_fragments"]

    invalid = scenarios["A-14"]
    assert invalid["setup"] == {"mcp_failure": "invalid_result"}
    assert invalid["expected"]["status"] == "error"
    assert invalid["expected"]["forbidden_answer_fragments"]
