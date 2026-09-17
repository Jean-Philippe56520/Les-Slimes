from datetime import UTC, datetime
from pathlib import Path

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.runtime import CanonicalRuntime, CanonicalWorldWorker, RuntimeStorage
from les_slimes.world.engine import World


ROOT = Path(__file__).resolve().parents[1]


def _repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=44,
                initial_slimes=2,
                initial_food=1,
                max_food=10,
                food_spawn_probability=0.0,
            )
        )
    )
    return repo


def test_extended_canonical_commands_apply_only_through_worker(tmp_path):
    repo = _repo(tmp_path)
    now = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(now)
    storage = RuntimeStorage(repo)

    command = storage.enqueue_command(
        actor_id="father",
        command_type="add_behavior_rule",
        payload={
            "rule": {
                "name": "Rest when weak",
                "priority": 50,
                "conditions": [{"type": "energy_below", "value": 20}],
                "action": "rest",
                "parameters": {},
            }
        },
        idempotency_key="rule-1",
        created_at_utc=now,
        source_proposal_id=7,
    )

    assert repo.load_world().behavior_rules == {}
    assert command.source_proposal_id == 7

    result = CanonicalWorldWorker(repo, holder_id="test-worker").run_until(now)
    world = repo.load_world()

    assert result.commands_applied == 1
    assert len(world.behavior_rules) == 1
    rule = next(iter(world.behavior_rules.values()))
    assert rule.source == "observer"


def test_invalid_payload_is_rejected_before_queue_insert(tmp_path):
    storage = RuntimeStorage(_repo(tmp_path))
    try:
        storage.enqueue_command(
            actor_id="father",
            command_type="deposit_food",
            payload={"x": "bad", "y": 2, "count": 1},
            idempotency_key="invalid",
            created_at_utc=datetime(2026, 9, 17, 12, 0, tzinfo=UTC),
        )
    except ValueError:
        pass
    else:
        raise AssertionError("invalid canonical command payload was accepted")
    assert storage.pending_commands() == []


def test_interfaces_cannot_reintroduce_direct_canonical_mutation():
    guarded = {
        "dashboard/app.py": [
            "world.step(",
            "world.player_deposit_food(",
            "world.player_emit_signal(",
            "apply_proposal(",
            "repo.save_world(world)",
            "world.mode",
        ],
        "src/les_slimes/observer/proposals.py": [
            "world.add_behavior_rule(",
            "world.add_mystery(",
            "world.player_deposit_food(",
            "world.player_emit_signal(",
        ],
        "src/les_slimes/cli.py": [
            "world.step(",
            "world.player_deposit_food(",
            "world.player_emit_signal(",
            "apply_proposal(",
        ],
    }

    for relative_path, forbidden in guarded.items():
        text = (ROOT / relative_path).read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"{relative_path} bypasses canonical boundary via {token}"
