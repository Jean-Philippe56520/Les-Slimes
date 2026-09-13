from dataclasses import replace

from les_slimes.analytics import detect_emergence
from les_slimes.config import WorldConfig
from les_slimes.world.engine import World


def test_player_signal_can_be_learned_as_food_predictor():
    cfg = replace(
        WorldConfig(),
        seed=31,
        initial_slimes=1,
        initial_food=0,
        max_food=20,
        food_spawn_probability=0.0,
        base_reproduction_probability=0.0,
        initial_energy=10.0,
        food_nutrition=5.0,
        eat_radius=5.0,
        signal_radius=20.0,
        signal_learning_rate=0.22,
    )
    world = World(cfg)
    slime = next(iter(world.slimes.values()))

    for _ in range(4):
        world.player_emit_signal("S1", slime.x, slime.y, radius=20.0)
        world.player_deposit_food(slime.x, slime.y, 1)
        world.step(1)

    assert slime.signal_food_associations["S1"] >= cfg.signal_emit_threshold

    world.player_emit_signal(
        "S1",
        min(cfg.width, slime.x + 10.0),
        slime.y,
        radius=30.0,
    )
    slime.energy = min(slime.energy, cfg.forage_energy_threshold - 1.0)
    world.step(1)
    assert slime.current_action.startswith("follow_signal_S1")


def test_proximity_builds_social_familiarity():
    cfg = replace(
        WorldConfig(),
        seed=71,
        initial_slimes=2,
        initial_food=0,
        max_food=0,
        food_spawn_probability=0.0,
        base_reproduction_probability=0.0,
        social_update_interval=1,
        social_interaction_radius=10.0,
    )
    world = World(cfg)
    a, b = sorted(world.slimes.values(), key=lambda slime: slime.id)
    a.x = b.x = 20.0
    a.y = b.y = 20.0
    world.step(1)

    assert b.id in a.relations
    assert a.id in b.relations
    assert a.relations[b.id].familiarity > 0.0
    assert b.relations[a.id].familiarity > 0.0


def test_shared_signal_is_detected_as_emergence_candidate():
    cfg = replace(
        WorldConfig(),
        initial_slimes=10,
        initial_food=0,
        max_food=0,
        food_spawn_probability=0.0,
        base_reproduction_probability=0.0,
    )
    world = World(cfg)
    for slime in list(world.slimes.values())[:4]:
        slime.signal_food_associations["S2"] = 0.8

    candidates = detect_emergence(world)
    shared = [candidate for candidate in candidates if candidate.kind == "shared_signal_food"]
    assert shared
    assert shared[0].evidence["signal"] == "S2"


def test_learned_signal_can_transmit_from_slime_to_slime():
    cfg = replace(
        WorldConfig(),
        seed=101,
        initial_slimes=2,
        initial_food=0,
        max_food=10,
        food_spawn_probability=0.0,
        base_reproduction_probability=0.0,
        initial_energy=10.0,
        food_nutrition=5.0,
        eat_radius=5.0,
        signal_radius=20.0,
        signal_emit_probability=1.0,
        signal_emit_cooldown=1,
    )
    world = World(cfg)
    source, learner = sorted(world.slimes.values(), key=lambda slime: slime.id)
    source.x = learner.x = 25.0
    source.y = learner.y = 25.0
    source.signal_food_associations["S1"] = 0.9

    world.player_deposit_food(25.0, 25.0, 2)
    world.step(1)

    assert learner.signal_food_associations.get("S1", 0.0) > 0.0
    assert any(event.type == "slime_signal" for event in world.pending_events)
    assert any(event.type == "signal_food_learning" for event in world.pending_events)


def test_social_memory_is_bounded():
    cfg = replace(
        WorldConfig(),
        seed=123,
        initial_slimes=8,
        initial_food=0,
        max_food=0,
        food_spawn_probability=0.0,
        base_reproduction_probability=0.0,
        social_update_interval=1,
        social_interaction_radius=100.0,
        max_relations_per_slime=3,
    )
    world = World(cfg)
    for slime in world.slimes.values():
        slime.x = 20.0
        slime.y = 20.0
    world.step(2)
    assert all(len(slime.relations) <= 3 for slime in world.slimes.values())
