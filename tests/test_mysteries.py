from dataclasses import replace

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.observer import ObserverProposal, apply_proposal
from les_slimes.world.engine import World


def test_mystery_can_affect_slime_without_exposing_effect_in_public_view():
    cfg = replace(
        WorldConfig(),
        initial_slimes=1,
        initial_food=0,
        max_food=0,
        food_spawn_probability=0.0,
        base_reproduction_probability=0.0,
        mystery_trigger_cooldown=1,
    )
    world = World(cfg)
    slime = next(iter(world.slimes.values()))
    mystery = world.add_mystery(
        {
            "public_label": "Obélisque silencieux",
            "x": slime.x,
            "y": slime.y,
            "radius": 10.0,
            "effect": "energy_delta",
            "parameters": {"amount": 10.0},
        }
    )
    before = slime.energy
    world.step(1)
    assert slime.energy > before
    assert "effect" not in mystery.public_dict()
    assert mystery.trigger_count >= 1


def test_mystery_persists_exactly(tmp_path):
    cfg = replace(WorldConfig(), initial_slimes=1, initial_food=0, max_food=1)
    world = World(cfg)
    world.add_mystery(
        {
            "public_label": "Pierre inconnue",
            "x": 10.0,
            "y": 10.0,
            "radius": 2.0,
            "effect": "memory_amplify",
            "parameters": {"factor": 1.2},
        }
    )
    repo = SQLiteRepository(tmp_path / "mystery.sqlite")
    repo.save_world(world)
    restored = repo.load_world()
    assert restored.state_digest() == world.state_digest()


def test_observer_can_propose_safe_mystery():
    world = World(replace(WorldConfig(), initial_slimes=1, initial_food=0, max_food=1))
    proposal = ObserverProposal.from_dict(
        {
            "type": "mystery_proposal",
            "summary": "Introduce a hidden signal source.",
            "confidence": 0.6,
            "evidence": ["Sandbox narrative intervention"],
            "parameters": {
                "mystery": {
                    "public_label": "Fragment X",
                    "x": 5.0,
                    "y": 5.0,
                    "radius": 2.0,
                    "effect": "signal_pulse",
                    "parameters": {"signal": "S3", "radius": 8.0}
                }
            },
        }
    )
    result = apply_proposal(world, proposal)
    assert result["applied"] is True
    assert result["mystery_id"] in world.mysteries
