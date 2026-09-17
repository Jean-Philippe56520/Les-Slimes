from datetime import UTC, datetime, timedelta

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.experiments import create_experiment_fork
from les_slimes.governance import (
    BudgetKind,
    DivineGovernanceService,
    GovernanceAdminService,
    GovernanceStorage,
    JournalEntryType,
    PowerLevel,
    SanctionType,
)
from les_slimes.runtime import ActorPermission, CanonicalRuntime, CanonicalWorldWorker, RuntimeStorage
from les_slimes.world.engine import World


def build_repo(tmp_path, name="world.sqlite"):
    repo = SQLiteRepository(tmp_path / name)
    repo.save_world(
        World(
            WorldConfig(
                seed=777,
                width=30.0,
                height=20.0,
                initial_slimes=6,
                initial_food=8,
                max_food=40,
                food_spawn_probability=0.0,
                tick_duration_seconds=1.0,
            )
        )
    )
    return repo


def grant_miracle(repo, actor_id, start, *, budget=1, observer=False):
    admin = GovernanceAdminService(repo)
    permissions = [ActorPermission.DEPOSIT_FOOD]
    if observer:
        permissions.append(ActorPermission.APPLY_OBSERVER_PROPOSAL)
    admin.set_permissions(actor_id, permissions, reason="test grant", now_utc=start)
    admin.set_power_level(actor_id, PowerLevel.MIRACLE, reason="test grant", now_utc=start)
    if budget:
        admin.adjust_budget(actor_id, BudgetKind.MIRACLE, budget, reason="test grant", now_utc=start)
    return admin


def test_default_gods_are_observation_only(tmp_path):
    repo = build_repo(tmp_path)
    governance = GovernanceStorage(repo)
    assert governance.get_actor_state("order").max_power_level == PowerLevel.OBSERVATION
    assert governance.get_actor_state("chaos").max_power_level == PowerLevel.OBSERVATION
    assert governance.get_actor_state("father").max_power_level == PowerLevel.TRANSGRESSION


def test_budget_is_debited_exactly_once_on_success(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = grant_miracle(repo, "order", start, budget=2)
    storage = RuntimeStorage(repo)
    storage.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 3.0, "y": 4.0, "count": 1},
        idempotency_key="budget-once",
        created_at_utc=start,
    )

    result = CanonicalWorldWorker(repo, holder_id="g1", clock=lambda: start).run_until(start)
    assert result.commands_applied == 1
    assert admin.storage.budget_balance("order", BudgetKind.MIRACLE) == 1

    with repo._connect() as conn:
        intervention = conn.execute(
            "SELECT * FROM divine_interventions WHERE command_id IS NOT NULL"
        ).fetchone()
        ledger = conn.execute(
            "SELECT * FROM divine_budget_ledger WHERE intervention_id = ?",
            (intervention["id"],),
        ).fetchall()
    assert intervention["status"] == "executed"
    assert len(ledger) == 1
    assert ledger[0]["delta"] == -1


def test_zero_budget_rejects_without_world_mutation(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    grant_miracle(repo, "chaos", start, budget=0)
    storage = RuntimeStorage(repo)
    before = repo.load_world().state_digest()
    storage.enqueue_command(
        actor_id="chaos",
        command_type="deposit_food",
        payload={"x": 3.0, "y": 4.0, "count": 1},
        idempotency_key="no-budget",
        created_at_utc=start,
    )

    result = CanonicalWorldWorker(repo, holder_id="g2", clock=lambda: start).run_until(start)
    assert result.commands_applied == 0
    assert result.commands_rejected == 1
    assert repo.load_world().state_digest() == before


def test_miracle_sanction_blocks_action_without_spending_budget(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = grant_miracle(repo, "order", start, budget=1)
    admin.impose_sanction(
        "order",
        SanctionType.DENY_MIRACLE,
        reason="test sanction",
        now_utc=start,
    )
    storage = RuntimeStorage(repo)
    storage.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 3.0, "y": 4.0, "count": 1},
        idempotency_key="sanctioned",
        created_at_utc=start,
    )

    result = CanonicalWorldWorker(repo, holder_id="g3", clock=lambda: start).run_until(start)
    assert result.commands_rejected == 1
    assert admin.storage.budget_balance("order", BudgetKind.MIRACLE) == 1


def test_expired_sanction_no_longer_blocks(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    later = start + timedelta(minutes=2)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = grant_miracle(repo, "order", start, budget=1)
    admin.impose_sanction(
        "order",
        SanctionType.DENY_MIRACLE,
        reason="temporary",
        now_utc=start,
        expires_at_utc=start + timedelta(minutes=1),
    )
    storage = RuntimeStorage(repo)
    storage.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 3.0, "y": 4.0, "count": 1},
        idempotency_key="after-sanction",
        created_at_utc=start,
    )

    result = CanonicalWorldWorker(repo, holder_id="g4", clock=lambda: later).run_until(later)
    assert result.commands_applied == 1
    assert admin.storage.budget_balance("order", BudgetKind.MIRACLE) == 0


def test_observer_proposal_requires_double_permission(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = grant_miracle(repo, "order", start, budget=2, observer=False)
    storage = RuntimeStorage(repo)
    storage.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 1.0, "y": 1.0, "count": 1},
        idempotency_key="observer-no-approval",
        created_at_utc=start,
        source_proposal_id=1,
    )
    first = CanonicalWorldWorker(repo, holder_id="g5a", clock=lambda: start).run_until(start)
    assert first.commands_rejected == 1
    assert admin.storage.budget_balance("order", BudgetKind.MIRACLE) == 2

    admin.set_permissions(
        "order",
        [ActorPermission.DEPOSIT_FOOD, ActorPermission.APPLY_OBSERVER_PROPOSAL],
        reason="allow observer approval",
        now_utc=start,
    )
    storage.enqueue_command(
        actor_id="order",
        command_type="deposit_food",
        payload={"x": 2.0, "y": 2.0, "count": 1},
        idempotency_key="observer-approved",
        created_at_utc=start,
        source_proposal_id=2,
    )
    second = CanonicalWorldWorker(repo, holder_id="g5b", clock=lambda: start).run_until(start)
    assert second.commands_applied == 1
    assert admin.storage.budget_balance("order", BudgetKind.MIRACLE) == 1


def test_crash_after_world_commit_does_not_double_debit(tmp_path, monkeypatch):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    CanonicalRuntime(repo).ensure_initialized(start)
    admin = grant_miracle(repo, "chaos", start, budget=2)
    storage = RuntimeStorage(repo)
    command = storage.enqueue_command(
        actor_id="chaos",
        command_type="deposit_food",
        payload={"x": 5.0, "y": 5.0, "count": 1},
        idempotency_key="crash-after-commit",
        created_at_utc=start,
    )

    worker = CanonicalWorldWorker(repo, holder_id="crashing", clock=lambda: start)
    original_mark = worker.storage.mark_applied

    def crash_mark(*args, **kwargs):
        raise RuntimeError("simulated status crash")

    monkeypatch.setattr(worker.storage, "mark_applied", crash_mark)
    with pytest.raises(RuntimeError, match="simulated status crash"):
        worker.run_until(start)

    assert admin.storage.budget_balance("chaos", BudgetKind.MIRACLE) == 1
    assert RuntimeStorage(repo).pending_commands()[0].id == command.id

    recovery = CanonicalWorldWorker(repo, holder_id="recovery", clock=lambda: start)
    result = recovery.run_until(start)
    assert result.commands_applied == 0
    assert admin.storage.budget_balance("chaos", BudgetKind.MIRACLE) == 1
    assert RuntimeStorage(repo).pending_commands() == []

    with repo._connect() as conn:
        debits = conn.execute(
            "SELECT * FROM divine_budget_ledger WHERE delta < 0"
        ).fetchall()
    assert len(debits) == 1


def test_governance_changes_do_not_change_world_digest(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    before = repo.load_world().state_digest()
    admin = GovernanceAdminService(repo)
    admin.set_permissions("order", [ActorPermission.DEPOSIT_FOOD], reason="test", now_utc=start)
    admin.set_power_level("order", PowerLevel.MIRACLE, reason="test", now_utc=start)
    admin.adjust_budget("order", BudgetKind.MIRACLE, 5, reason="test", now_utc=start)
    admin.impose_sanction("chaos", SanctionType.DENY_DECREE, reason="test", now_utc=start)
    after = repo.load_world().state_digest()
    assert after == before


def test_audit_chain_detects_tampering(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    admin = GovernanceAdminService(repo)
    admin.adjust_budget("order", BudgetKind.MIRACLE, 2, reason="allocation", now_utc=start)
    admin.set_power_level("order", PowerLevel.MIRACLE, reason="grant", now_utc=start)
    assert admin.storage.validate_audit_chain()

    with repo._connect() as conn:
        conn.execute(
            "UPDATE divine_audit_log SET payload_json = ? WHERE sequence = 1",
            ('{"tampered":true}',),
        )
        conn.commit()
    assert not admin.storage.validate_audit_chain()


def test_only_father_can_administer_governance(tmp_path):
    repo = build_repo(tmp_path)
    admin = GovernanceAdminService(repo)
    with pytest.raises(PermissionError, match="Father"):
        admin.adjust_budget(
            "chaos",
            BudgetKind.MIRACLE,
            1,
            reason="self grant",
            performed_by="chaos",
        )


def test_proposals_and_journals_do_not_require_execution_budget(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineGovernanceService(repo)
    proposal_id = service.propose(
        "order",
        "law",
        "A law proposal",
        {"summary": "Proposal only; no autonomous execution"},
    )
    journal_id = service.journal(
        "order",
        JournalEntryType.HYPOTHESIS,
        "A hypothesis without world mutation",
    )
    assert proposal_id > 0
    assert journal_id > 0


def test_experiment_fork_does_not_copy_governance(tmp_path):
    repo = build_repo(tmp_path)
    start = datetime(2026, 9, 17, 12, 0, tzinfo=UTC)
    admin = GovernanceAdminService(repo)
    admin.adjust_budget("order", BudgetKind.MIRACLE, 10, reason="canonical only", now_utc=start)

    fork_path = tmp_path / "experiment.sqlite"
    fork, _ = create_experiment_fork(
        repo,
        fork_path,
        experiment_id="EXP-GOV",
        condition="control",
        source_git_commit="test-commit",
    )
    with fork._connect() as conn:
        tables = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'divine_%'"
            )
        }
    assert tables == set()
