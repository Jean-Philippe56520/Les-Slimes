from __future__ import annotations

import os

import pytest

psycopg = pytest.importorskip("psycopg")

from les_slimes.config import WorldConfig
from les_slimes.database.postgres_repo import PostgreSQLRepository
from les_slimes.database.scope import PersistenceScope, get_persistence_scope
from les_slimes.experiments.forks import create_experiment_fork
from les_slimes.world.engine import World


TEST_DSN = os.getenv("LES_SLIMES_TEST_POSTGRES_URL", "").strip()
pytestmark = pytest.mark.skipif(not TEST_DSN, reason="PostgreSQL integration DSN is not configured")


def test_postgres_canonical_world_can_fork_into_isolated_sqlite_experiment(tmp_path):
    with psycopg.connect(TEST_DSN, autocommit=True) as conn:
        conn.execute("DROP SCHEMA IF EXISTS public CASCADE")
        conn.execute("CREATE SCHEMA public")

    canonical = PostgreSQLRepository(TEST_DSN)
    world = World(
        WorldConfig(
            seed=9917,
            width=28.0,
            height=18.0,
            initial_slimes=6,
            initial_food=8,
            max_food=30,
            food_spawn_probability=0.0,
        )
    )
    world.step(25)
    canonical.save_world(world)
    source_digest = canonical.load_world().state_digest()

    experiment, manifest = create_experiment_fork(
        canonical,
        tmp_path / "experiment.sqlite",
        experiment_id="pg-fork-test",
        condition="control",
        source_git_commit="integration-test",
    )

    assert manifest.source_digest == source_digest
    assert experiment.load_world().state_digest() == source_digest
    assert get_persistence_scope(experiment) == PersistenceScope.NON_CANONICAL_EXPERIMENT
    with experiment._connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
    assert "runtime_commands" not in tables
    assert not any(name.startswith("divine_") for name in tables)
