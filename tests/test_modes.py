from dataclasses import replace

import pytest

from les_slimes.config import WorldConfig
from les_slimes.world.engine import World
from les_slimes.world.modes import WorldMode


def test_experiment_mode_blocks_external_interventions():
    cfg = replace(WorldConfig(), initial_slimes=1, initial_food=0, max_food=1)
    world = World(cfg, mode=WorldMode.EXPERIMENT)

    with pytest.raises(PermissionError):
        world.player_deposit_food(1.0, 1.0)
    with pytest.raises(PermissionError):
        world.player_emit_signal("S1", 1.0, 1.0)


def test_mode_is_part_of_state_digest():
    cfg = replace(WorldConfig(), initial_slimes=1, initial_food=0, max_food=1)
    sandbox = World(cfg, mode=WorldMode.SANDBOX)
    experiment = World(cfg, mode=WorldMode.EXPERIMENT)
    assert sandbox.state_digest() != experiment.state_digest()


def test_mode_survives_sqlite_roundtrip(tmp_path):
    from les_slimes.database.sqlite_repo import SQLiteRepository

    cfg = replace(WorldConfig(), initial_slimes=2, initial_food=1, max_food=2)
    world = World(cfg, mode=WorldMode.OBSERVATION)
    repo = SQLiteRepository(tmp_path / "mode.sqlite")
    repo.save_world(world)
    restored = repo.load_world()
    assert restored.mode is WorldMode.OBSERVATION
    assert restored.state_digest() == world.state_digest()
