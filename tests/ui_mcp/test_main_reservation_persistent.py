"""RESERVATION_STORAGE_MODE=persistent일 때 main.py가 Postgres 저장소를 쓰는지 검증한다."""

from __future__ import annotations

import pytest

from backend.app.core.config import Settings

pytestmark = pytest.mark.integration


def _capture_reservations(monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    import backend.app.main as main_module

    captured: dict[str, object] = {}

    def _fake_create_reservation_router(reservations, sessions, approvals):
        captured["reservations"] = reservations
        from backend.app.routers.reservation_router import create_reservation_router as real
        return real(reservations, sessions, approvals)

    monkeypatch.setattr(main_module, "create_reservation_router", _fake_create_reservation_router)
    return captured


def test_create_app_wires_postgres_reservation_repositories_when_persistent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.core import db as db_module
    from backend.app.main import create_app
    from backend.app.repositories.reservation_repository import PostgresReservationRepository

    db_module._reset_pool_for_tests()
    settings = Settings(
        _env_file=None,
        RESERVATION_STORAGE_MODE="persistent",
        DATABASE_URL="postgresql://zoo:zoo@127.0.0.1:5432/zoo",
    )
    captured = _capture_reservations(monkeypatch)

    create_app(settings)

    assert isinstance(captured["reservations"], PostgresReservationRepository)


def test_create_app_defaults_to_memory_reservation_repository(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.app.main import create_app
    from backend.app.repositories.reservation_repository import ReservationRepository

    settings = Settings(_env_file=None)  # RESERVATION_STORAGE_MODE 기본값 memory
    assert settings.RESERVATION_STORAGE_MODE == "memory"
    captured = _capture_reservations(monkeypatch)

    create_app(settings)

    assert isinstance(captured["reservations"], ReservationRepository)
