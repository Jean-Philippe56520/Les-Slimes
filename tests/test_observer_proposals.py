from dataclasses import replace

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.observer import ObserverProposal, proposal_to_command
from les_slimes.world.engine import World


def test_observer_behavior_proposal_converts_to_command_without_mutating_world():
    world = World(replace(WorldConfig(), initial_slimes=1, initial_food=0, max_food=1))
    before = world.state_digest()
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

    command_type, payload = proposal_to_command(proposal)

    assert command_type == "add_behavior_rule"
    assert payload["rule"]["name"] == "Observer rest rule"
    assert world.state_digest() == before
    assert world.behavior_rules == {}


def test_analytical_observer_proposal_never_becomes_command():
    proposal = ObserverProposal.from_dict(
        {
            "type": "hypothesis",
            "summary": "Test hypothesis",
            "confidence": 0.5,
            "evidence": ["test"],
            "parameters": {},
        }
    )
    assert proposal_to_command(proposal) is None


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
