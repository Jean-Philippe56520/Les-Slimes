from datetime import UTC, datetime

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.governance.models import BudgetKind, PowerLevel
from les_slimes.governance.service import GovernanceAdminService
from les_slimes.runtime import ActorPermission, CanonicalRuntime, CanonicalWorldWorker, RuntimeStorage
from les_slimes.world.engine import World


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=908,
                width=20.0,
                height=20.0,
                initial_slimes=3,
                initial_food=3,
                max_food=15,
                food_spawn_probability=0.0,
                tick_duration_seconds=1.0,
            )
        )
    )
    return repo


def test_legacy_runtime_actor_is_backfilled_to_observation_and_does_not_poison_queue(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    runtime = RuntimeStorage(repo)
    runtime.upsert_actor(
        actor_id="legacy-god",
        kind="god",
        display_name="Legacy God",
        permissions=[ActorPermission.DEPOSIT_FOOD],
    )
    runtime.enqueue_command(
        actor_id="legacy-god",
        command_type="deposit_food",
        payload={"x": 1.0, "y": 1.0, "count": 1},
        idempotency_key="legacy-god-command",
        created_at_utc=start,
    )

    worker = CanonicalWorldWorker(repo, holder_id="legacy-backfill", clock=lambda: start)
    assert worker.governance.get_actor_state("legacy-god").max_power_level == PowerLevel.OBSERVATION
    result = worker.run_until(start)

    assert result.commands_applied == 0
    assert result.commands_rejected == 1
    assert RuntimeStorage(repo).pending_commands() == []


def test_rejection_transaction_rolls_back_as_a_unit_on_crash(tmp_path, monkeypatch):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = GovernanceAdminService(repo)
    admin.set_permissions("order", [ActorPermission.DEPOSIT_FOOD], reason="test", now_utc=start)
    admin.set_power_level("order", PowerLevel.MIRACLE, reason="test", now_utc=start)
    runtime = RuntimeStorage(repo)
    command = runtime.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 2.0, "y": 2.0, "count": 1},
        idempotency_key="reject-atomic-crash",
        created_at_utc=start,
    )

    worker = CanonicalWorldWorker(repo, holder_id="reject-crash", clock=lambda: start)

    def crash_audit(*args, **kwargs):
        raise RuntimeError("simulated rejection crash")

    monkeypatch.setattr(worker.governance, "append_audit_in_transaction", crash_audit)
    with pytest.raises(RuntimeError, match="simulated rejection crash"):
        worker.run_until(start)

    with repo._connect() as conn:
        command_row = conn.execute(
            "SELECT status FROM runtime_commands WHERE id = ?", (command.id,)
        ).fetchone()
        intervention_row = conn.execute(
            "SELECT status FROM divine_interventions WHERE command_id = ?", (command.id,)
        ).fetchone()
    assert command_row["status"] == "pending"
    assert intervention_row["status"] == "proposed"

    admin.adjust_budget("order", BudgetKind.MIRACLE, 1, reason="authority changed after rollback", now_utc=start)
    recovery = CanonicalWorldWorker(repo, holder_id="reject-recovery", clock=lambda: start)
    result = recovery.run_until(start)
    assert result.commands_applied == 1
    assert RuntimeStorage(repo).pending_commands() == []
