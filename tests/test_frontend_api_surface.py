from datetime import UTC, datetime

from fastapi.testclient import TestClient

from les_slimes.api.app import CORS_ORIGINS_ENV, create_app
from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.runtime import CanonicalRuntime
from les_slimes.world.engine import World


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=1204,
                width=40.0,
                height=25.0,
                initial_slimes=4,
                initial_food=7,
                max_food=30,
                food_spawn_probability=0.0,
            )
        )
    )
    CanonicalRuntime(repo).ensure_initialized(datetime(2026, 9, 17, 12, 0, tzinfo=UTC))
    return repo


def test_public_food_projection_is_read_only(tmp_path):
    repo = build_repo(tmp_path)
    before = repo.load_world().state_digest()
    client = TestClient(create_app(repo))

    response = client.get("/world/foods")

    assert response.status_code == 200
    payload = response.json()
    assert payload["tick"] == 0
    assert len(payload["foods"]) == 7
    assert {"id", "x", "y", "nutrition"} <= set(payload["foods"][0])
    assert repo.load_world().state_digest() == before


def test_configured_frontend_origin_receives_cors_headers(tmp_path, monkeypatch):
    repo = build_repo(tmp_path)
    origin = "https://les-slimes.example"
    monkeypatch.setenv(CORS_ORIGINS_ENV, origin)
    client = TestClient(create_app(repo))

    response = client.options(
        "/world",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == origin


def test_unlisted_origin_is_not_granted_cors_access(tmp_path, monkeypatch):
    repo = build_repo(tmp_path)
    monkeypatch.setenv(CORS_ORIGINS_ENV, "https://allowed.example")
    client = TestClient(create_app(repo))

    response = client.get("/world", headers={"Origin": "https://not-allowed.example"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
