from dataclasses import replace

from les_slimes.config import WorldConfig
from les_slimes.world.engine import World


def test_starvation_can_cause_extinction():
    cfg = replace(
        WorldConfig(),
        seed=7,
        initial_slimes=8,
        initial_food=0,
        max_food=0,
        food_spawn_probability=0.0,
        initial_energy=3.0,
        base_metabolic_cost=0.6,
        move_energy_cost=0.2,
        low_energy_health_threshold=10.0,
    )
    world = World(cfg)
    world.step(100)
    assert len(world.slimes) == 0
    assert world.deaths_total == 8


def test_reproduction_creates_lineage():
    cfg = replace(
        WorldConfig(),
        seed=19,
        initial_slimes=4,
        initial_food=40,
        max_food=80,
        initial_energy=95.0,
        maturity_age_ticks=0,
        reproduction_cooldown_ticks=1,
        reproduction_energy_threshold=40.0,
        reproduction_energy_cost=10.0,
        birth_energy=10.0,
        base_reproduction_probability=1.0,
        food_spawn_probability=1.0,
        base_metabolic_cost=0.0,
        move_energy_cost=0.0,
    )
    world = World(cfg)
    world.step(1)
    children = [s for s in world.slimes.values() if s.parent_id is not None]
    assert children
    assert all(child.generation == 1 for child in children)
