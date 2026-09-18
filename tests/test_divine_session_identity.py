from datetime import UTC, datetime, timedelta

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.divine import DivineSessionBindingService
from les_slimes.governance.service import GovernanceAdminService
from les_slimes.governance.storage import GovernanceStorage
from les_slimes.world.engine import World


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=9911,
                width=20.0,
                height=15.0,
                initial_slimes=4,
                initial_food=5,
                max_food=20,
                food_spawn_probability=0.0,
            )
        )
    )
    return repo


def test_father_binds_and_resolves_session_without_storing_raw_identifiers(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineSessionBindingService(repo)
    now = datetime(2026, 9, 18, 8, 0, tzinfo=UTC)

    binding = service.bind(
        session_id="chat-session-order",
        subject_id="user-subject",
        actor_id="order",
        now_utc=now,
    )
    assert binding.actor_id == "order"
    assert binding.active
    assert binding.session_hash != "chat-session-order"
    assert binding.subject_hash != "user-subject"

    resolved = service.resolve(
        session_id="chat-session-order",
        subject_id="user-subject",
        now_utc=now + timedelta(seconds=5),
    )
    assert resolved.actor_id == "order"
    assert resolved.last_seen_at_utc == now + timedelta(seconds=5)

    with repo._connect() as conn:
        row = conn.execute("SELECT * FROM divine_session_bindings").fetchone()
    assert "chat-session-order" not in tuple(str(value) for value in row)
    assert "user-subject" not in tuple(str(value) for value in row)
    assert GovernanceStorage(repo).validate_audit_chain()


def test_non_father_cannot_bind_or_revoke(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineSessionBindingService(repo)
    with pytest.raises(PermissionError, match="Father"):
        service.bind(
            session_id="s1",
            subject_id="u1",
            actor_id="chaos",
            performed_by="chaos",
        )

    service.bind(session_id="s1", subject_id="u1", actor_id="chaos")
    with pytest.raises(PermissionError, match="Father"):
        service.revoke(session_id="s1", reason="attempt", performed_by="chaos")


def test_unbound_revoked_subject_mismatch_and_inactive_actor_fail_closed(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineSessionBindingService(repo)

    with pytest.raises(PermissionError, match="UNBOUND"):
        service.resolve(session_id="unknown", subject_id="u1")

    service.bind(session_id="s1", subject_id="u1", actor_id="chaos")
    with pytest.raises(PermissionError, match="SUBJECT_MISMATCH"):
        service.resolve(session_id="s1", subject_id="u2")

    service.revoke(session_id="s1", reason="rotate conversation")
    with pytest.raises(PermissionError, match="REVOKED"):
        service.resolve(session_id="s1", subject_id="u1")

    service.bind(session_id="s2", subject_id="u1", actor_id="order")
    GovernanceAdminService(repo).set_active("order", False, reason="test suspension")
    with pytest.raises(PermissionError, match="ACTOR_INACTIVE"):
        service.resolve(session_id="s2", subject_id="u1")


def test_session_cannot_be_silently_rebound_to_another_actor(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineSessionBindingService(repo)
    service.bind(session_id="s1", subject_id="u1", actor_id="order")

    with pytest.raises(PermissionError, match="already bound"):
        service.bind(session_id="s1", subject_id="u1", actor_id="chaos")

    service.revoke(session_id="s1", reason="retire chat")
    with pytest.raises(PermissionError, match="already bound"):
        service.bind(session_id="s1", subject_id="u1", actor_id="chaos")


def test_binding_is_limited_to_known_divine_communication_actors(tmp_path):
    repo = build_repo(tmp_path)
    service = DivineSessionBindingService(repo)
    with pytest.raises(ValueError):
        service.bind(session_id="s1", subject_id="u1", actor_id="observer")
