from datetime import UTC, datetime

from fastapi.testclient import TestClient

from les_slimes.api import create_app
from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.runtime import CanonicalRuntime
from les_slimes.world.engine import World


def build_client(tmp_path):
    repo = SQLiteRepository(tmp_path / "frontend.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=2468,
                width=40.0,
                height=24.0,
                initial_slimes=7,
                initial_food=9,
                max_food=40,
                food_spawn_probability=0.0,
                tick_duration_seconds=1.0,
            )
        )
    )
    CanonicalRuntime(repo).ensure_initialized(datetime(2026, 9, 17, 12, 0, tzinfo=UTC))
    app = create_app(repo, cors_origins=["https://les-slimes.example"])
    return repo, TestClient(app)


def test_frontend_world_projections_are_read_only(tmp_path):
    repo, client = build_client(tmp_path)
    before = repo.load_world().state_digest()

    world = client.get("/world")
    slimes = client.get("/world/slimes")
    foods = client.get("/world/foods")

    assert world.status_code == 200
    assert slimes.status_code == 200
    assert foods.status_code == 200
    assert world.json()["state_digest"] == before
    assert slimes.json()["tick"] == world.json()["tick"]
    assert foods.json()["tick"] == world.json()["tick"]
    assert len(slimes.json()["slimes"]) == 7
    assert len(foods.json()["foods"]) == 9
    assert repo.load_world().state_digest() == before


def test_frontend_cors_is_explicitly_allowlisted(tmp_path):
    _repo, client = build_client(tmp_path)

    allowed = client.options(
        "/world",
        headers={
            "Origin": "https://les-slimes.example",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/world",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://les-slimes.example"
    assert "access-control-allow-origin" not in denied.headers
