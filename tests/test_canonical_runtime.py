from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.runtime import CanonicalRuntime
from les_slimes.world.engine import World


def compact_config(**overrides):
    base = WorldConfig(
        seed=987654,
        width=50.0,
        height=40.0,
        tick_duration_seconds=2.0,
        initial_slimes=24,
        initial_food=60,
        max_food=90,
        checkpoint_interval=50,
    )
    return replace(base, **overrides)


def test_advance_to_replays_only_complete_ticks(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(World(compact_config()))
    runtime = CanonicalRuntime(repo, batch_size=3)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    runtime.ensure_initialized(start)

    result = runtime.advance_to(start + timedelta(seconds=11))

    assert result.ticks_advanced == 5
    assert result.current_tick == 5
    assert result.batches == 2
    assert result.last_simulated_at_utc == start + timedelta(seconds=10)

    second = runtime.advance_to(start + timedelta(seconds=12))
    assert second.ticks_advanced == 1
    assert second.current_tick == 6


def test_interrupted_catch_up_matches_uninterrupted_digest(tmp_path):
    cfg = compact_config(tick_duration_seconds=1.0)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)

    uninterrupted = World(cfg)
    uninterrupted.step(1200)

    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(World(cfg))
    runtime = CanonicalRuntime(repo, batch_size=137)
    runtime.ensure_initialized(start)

    first = runtime.advance_to(start + timedelta(seconds=500))
    assert first.current_tick == 500

    restarted = CanonicalRuntime(repo, batch_size=113)
    second = restarted.advance_to(start + timedelta(seconds=1200))

    assert second.current_tick == 1200
    assert second.state_digest == uninterrupted.state_digest()
    assert repo.load_world().state_digest() == uninterrupted.state_digest()


def test_runtime_reconciles_metadata_from_saved_world_tick(tmp_path):
    cfg = compact_config()
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(World(cfg))
    runtime = CanonicalRuntime(repo)
    runtime.ensure_initialized(start)

    world = repo.load_world()
    world.step(7)
    repo.save_world(world)

    metadata = CanonicalRuntime(repo).metadata()
    assert metadata.last_simulated_at_utc == start + timedelta(seconds=14)


def test_runtime_rejects_naive_timestamps(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(World(compact_config()))
    runtime = CanonicalRuntime(repo)

    with pytest.raises(ValueError):
        runtime.ensure_initialized(datetime(2026, 9, 17, 12, 0))
