from dataclasses import replace

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.observer import ObserverProposal, apply_proposal
from les_slimes.world.engine import World


def test_observer_behavior_proposal_applies_through_safe_rule_engine():
    world = World(replace(WorldConfig(), initial_slimes=1, initial_food=0, max_food=1))
    proposal = ObserverProposal.from_dict(
        {
            "type": "behavior_candidate",
            "summary": "Low-energy Slimes rest.",
            "confidence": 0.8,
            "evidence": ["Repeated low-energy immobility"],
            "parameters": {
                "rule": {
                    "name": "Observer rest rule",
                    "priority": 50,
                    "conditions": [{"type": "energy_below", "value": 30}],
                    "action": "rest",
                    "parameters": {},
                }
            },
        }
    )
    result = apply_proposal(world, proposal)
    assert result["applied"] is True
    assert result["rule_id"] in world.behavior_rules


def test_observer_proposal_inbox_persists(tmp_path):
    repo = SQLiteRepository(tmp_path / "observer.sqlite")
    world = World(replace(WorldConfig(), initial_slimes=1, initial_food=0, max_food=1))
    repo.save_world(world)
    proposal = {
        "type": "hypothesis",
        "summary": "Test hypothesis",
        "confidence": 0.5,
        "evidence": ["test"],
        "parameters": {},
    }
    proposal_id = repo.add_observer_proposal(world.tick, proposal)
    row = repo.get_observer_proposal(proposal_id)
    assert row["status"] == "pending"
    repo.update_observer_proposal(proposal_id, status="reviewed", result={"ok": True})
    row = repo.get_observer_proposal(proposal_id)
    assert row["status"] == "reviewed"
