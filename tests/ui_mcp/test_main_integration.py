"""실제 MCP Server와 FastAPI main 조립의 N-01~N-04 연결 시험."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.repositories import session_repository, trace_repository

PROJECT_ROOT = Path(__file__).resolve().parents[2]
TEST_PORT = 18101


def _wait_for_port(process: subprocess.Popen[str], timeout: float = 10) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            raise AssertionError(f"MCP Server 조기 종료: {stdout} {stderr}")
        try:
            with socket.create_connection(("127.0.0.1", TEST_PORT), timeout=0.2):
                return
        except OSError:
            time.sleep(0.05)
    raise AssertionError("MCP Server 시작 timeout")


@pytest.mark.integration
def test_main_connects_n01_to_n04_through_real_mcp() -> None:
    env = os.environ.copy()
    env.update({"APP_MODE": "mock", "MCP_HOST": "127.0.0.1", "MCP_PORT": str(TEST_PORT)})
    process = subprocess.Popen(
        [sys.executable, "-m", "mcp_server.server"],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        _wait_for_port(process)
        session_repository._reset_for_tests()
        trace_repository._reset_for_tests()
        settings = Settings(
            _env_file=None,
            APP_MODE="mock",
            MCP_SERVER_URL=f"http://127.0.0.1:{TEST_PORT}/mcp",
            ADMIN_TOKEN="integration-admin",
            DEMO_NOW="2026-09-07T12:00:00+09:00",
        )
        with TestClient(create_app(settings)) as client:
            cases = [
                ("호랑이는 어디에서 살고 무엇을 먹어?", "retrieve_animal_info"),
                ("해양관의 다음 먹이시간을 알려 줘.", "get_feeding_schedule"),
                ("오늘 쉬는 전시관이 있는지 알려 줘.", "check_closure_status"),
                ("정문에서 해양관까지 가는 경로를 알려 줘.", "find_habitat_route"),
            ]
            session_id = None
            for message, expected_tool in cases:
                payload = {"message": message}
                if session_id:
                    payload["session_id"] = session_id
                response = client.post("/api/agent/ask", json=payload)
                assert response.status_code == 200, response.text
                body = response.json()
                assert body["status"] == "completed", {
                    "expected_tool": expected_tool,
                    "status": body["status"],
                    "reason": body["termination_reason"],
                    "answer": body["final_answer"],
                    "trace": body["trace"],
                }
                assert body["tool_calls"][0]["name"] == expected_tool
                assert body["tool_calls"][0]["result"]["success"] is True
                if expected_tool == "retrieve_animal_info":
                    assert body["sources"]
                session_id = body["session_id"]

            trace = client.get(
                f"/api/admin/trace?session_id={session_id}",
                headers={"Authorization": "Bearer integration-admin"},
            )
            assert trace.status_code == 200
            assert len(trace.json()["runs"]) == 4
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
