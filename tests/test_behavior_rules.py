from dataclasses import replace

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.world.engine import World
from les_slimes.world.modes import WorldMode


def test_declarative_rule_can_override_behavior():
    cfg = replace(
        WorldConfig(),
        initial_slimes=1,
        initial_food=0,
        max_food=0,
        food_spawn_probability=0.0,
        base_reproduction_probability=0.0,
    )
    world = World(cfg)
    slime = next(iter(world.slimes.values()))
    slime.energy = 20.0
    x, y = slime.x, slime.y
    rule = world.add_behavior_rule(
        {
            "name": "Rest when low energy",
            "priority": 100,
            "conditions": [{"type": "energy_below", "value": 30}],
            "action": "rest",
            "parameters": {},
        },
        source="test",
    )
    world.step(1)
    assert slime.current_action == f"rule:{rule.id}:rest"
    assert slime.x == x and slime.y == y


def test_behavior_rule_roundtrip_is_exact(tmp_path):
    cfg = replace(WorldConfig(), initial_slimes=2, initial_food=2, max_food=3)
    world = World(cfg)
    world.add_behavior_rule(
        {
            "name": "Go to center when old",
            "priority": 10,
            "conditions": [{"type": "age_above", "value": 100}],
            "action": "move_to_point",
            "parameters": {"x": 60.0, "y": 40.0},
        },
        source="observer",
    )
    repo = SQLiteRepository(tmp_path / "rules.sqlite")
    repo.save_world(world)
    restored = repo.load_world()
    assert restored.state_digest() == world.state_digest()
    assert list(restored.behavior_rules) == list(world.behavior_rules)


def test_invalid_rule_is_rejected_and_experiment_is_locked():
    cfg = replace(WorldConfig(), initial_slimes=1, initial_food=0, max_food=1)
    sandbox = World(cfg)
    with pytest.raises(ValueError):
        sandbox.add_behavior_rule(
            {"name": "Bad", "conditions": [], "action": "execute_python"}
        )

    experiment = World(cfg, mode=WorldMode.EXPERIMENT)
    with pytest.raises(PermissionError):
        experiment.add_behavior_rule(
            {"name": "Rest", "conditions": [], "action": "rest"}
        )
