"""평가 실행 진입점 (최두나 소유, 작업지시서 v1.1 12.2절).

사용법:
    python -m eval.run --base-url http://127.0.0.1:8000

Backend가 아직 없거나 /api/agent/ask가 구현되기 전에 실행해도 에러 없이
각 시나리오가 SKIP으로 표시된다. API가 붙으면 같은 명령으로 실제 평가가 된다.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from backend.app.services.eval_service import run_scenarios, summarize

# Windows 콘솔/파일 리다이렉션은 기본적으로 시스템 로케일(cp949 등)로 stdout을 여는
# 경우가 있어 한글 출력이 깨진다. 명시적으로 UTF-8로 강제한다.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8")
        except Exception:
            pass

SCENARIOS_DIR = Path(__file__).parent / "scenarios"
DEFAULT_SCENARIO_FILES = ["rag.json", "mcp.json", "agent.json"]


def _default_scenario_paths() -> list[Path]:
    return [
        SCENARIOS_DIR / name
        for name in DEFAULT_SCENARIO_FILES
        if (SCENARIOS_DIR / name).exists()
    ]


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Zoo Visit Guide 시나리오 평가 실행기")
    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
        help="평가할 Backend 주소 (기본: http://127.0.0.1:8000)",
    )
    parser.add_argument(
        "--scenarios",
        nargs="*",
        default=None,
        help="평가할 시나리오 JSON 경로들 (기본: eval/scenarios/ 아래 존재하는 파일 전부)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    scenario_paths = args.scenarios or _default_scenario_paths()

    if not scenario_paths:
        print("실행할 시나리오 파일이 없습니다 (eval/scenarios/*.json 확인).", file=sys.stderr)
        return 1

    results = asyncio.run(run_scenarios(args.base_url, scenario_paths))

    for result in results:
        print(f"[{result['outcome']}] {result['id']}: {result['message']}")
        for failure in result["failures"]:
            print(f"    - {failure}")

    summary = summarize(results)
    print(
        f"\n총 {len(results)}개 중 PASS {summary['PASS']} / "
        f"FAIL {summary['FAIL']} / SKIP {summary['SKIP']}"
    )

    # SKIP만 있고 FAIL이 없으면(=API 미구현 상태) 0으로 통과시켜, Gate 0 이전
    # 단계에서 이 스크립트 자체가 CI를 깨지 않게 한다. FAIL이 하나라도 있으면 1.
    return 0 if summary["FAIL"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
