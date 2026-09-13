from dataclasses import replace

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.world.engine import World


def compact_config(**overrides):
    base = WorldConfig(
        seed=123456,
        width=50.0,
        height=40.0,
        initial_slimes=24,
        initial_food=60,
        max_food=90,
        checkpoint_interval=50,
    )
    return replace(base, **overrides)


def test_same_seed_produces_same_world():
    cfg = compact_config()
    a = World(cfg)
    b = World(cfg)
    a.step(800)
    b.step(800)
    assert a.state_digest() == b.state_digest()


def test_save_restore_continues_exactly(tmp_path):
    cfg = compact_config()
    uninterrupted = World(cfg)
    interrupted = World(cfg)

    uninterrupted.step(1200)

    interrupted.step(500)
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(interrupted)
    restored = repo.load_world()
    assert restored.state_digest() == interrupted.state_digest()

    restored.step(700)
    assert restored.state_digest() == uninterrupted.state_digest()
