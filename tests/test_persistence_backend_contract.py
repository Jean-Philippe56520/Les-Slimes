from datetime import UTC, datetime

from les_slimes.config import WorldConfig
from les_slimes.database.base import RelationalRepository
from les_slimes.database.scope import PersistenceScope, get_persistence_scope
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.runtime import CanonicalRuntime, RuntimeStorage
from les_slimes.world.engine import World


def test_sqlite_implements_relational_repository_contract(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")

    assert isinstance(repo, RelationalRepository)
    assert repo.backend_name == "sqlite"
    assert not repo.storage_exists()

    repo.save_world(
        World(
            WorldConfig(
                seed=444,
                width=20.0,
                height=12.0,
                initial_slimes=3,
                initial_food=4,
                max_food=20,
                food_spawn_probability=0.0,
            )
        )
    )

    assert repo.storage_exists()
    assert get_persistence_scope(repo) == PersistenceScope.CANONICAL
    with repo._connect() as conn:
        assert repo.table_exists(conn, "metadata")
        assert "last_signal_emit_tick" in repo.column_names(conn, "slimes")


def test_canonical_runtime_uses_repository_transaction_primitives(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    world = World(
        WorldConfig(
            seed=445,
            width=20.0,
            height=12.0,
            initial_slimes=3,
            initial_food=4,
            max_food=20,
            food_spawn_probability=0.0,
            tick_duration_seconds=1.0,
        )
    )
    repo.save_world(world)
    runtime = CanonicalRuntime(repo)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    runtime.ensure_initialized(start)
    RuntimeStorage(repo)

    before = repo.load_world().state_digest()
    result = runtime.advance_to(datetime(2026, 9, 17, 12, 0, 5, tzinfo=UTC))
    after = repo.load_world()

    assert result.ticks_advanced == 5
    assert after.tick == 5
    assert after.state_digest() != before
    assert result.state_digest == after.state_digest()
