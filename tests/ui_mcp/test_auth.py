import sqlite3

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.auth.repository import UserRepository
from backend.app.routers.auth_router import create_auth_router


def _client(tmp_path) -> tuple[TestClient, UserRepository]:
    repository = UserRepository(tmp_path / "auth.sqlite3")
    app = FastAPI()
    app.include_router(create_auth_router(repository))
    return TestClient(app), repository


def test_database_contains_only_test_user_with_hashed_password(tmp_path) -> None:
    _, repository = _client(tmp_path)
    with sqlite3.connect(repository.database_path) as connection:
        row = connection.execute("SELECT id, password_hash FROM users").fetchone()
    assert row[0] == "TEST"
    assert row[1] != "1234"


def test_login_accepts_matching_database_user_without_returning_password(tmp_path) -> None:
    client, _ = _client(tmp_path)
    response = client.post("/api/auth/login", json={"user_id": "TEST", "password": "1234"})
    assert response.status_code == 200
    assert response.json() == {"authenticated": True, "user_id": "TEST"}
    assert "password" not in response.text.lower()
    assert "1234" not in response.text


def test_login_rejects_wrong_credentials_with_same_generic_message(tmp_path) -> None:
    client, _ = _client(tmp_path)
    wrong_password = client.post("/api/auth/login", json={"user_id": "TEST", "password": "wrong"})
    unknown_user = client.post("/api/auth/login", json={"user_id": "UNKNOWN", "password": "wrong"})
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json() == unknown_user.json()
    assert "wrong" not in wrong_password.text


def test_login_forbids_extra_fields(tmp_path) -> None:
    client, _ = _client(tmp_path)
    response = client.post(
        "/api/auth/login",
        json={"user_id": "TEST", "password": "1234", "role": "admin"},
    )
    assert response.status_code == 422
