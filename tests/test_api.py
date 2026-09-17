from datetime import UTC, datetime

from fastapi.testclient import TestClient

from les_slimes.api import ActorAuthenticator, create_app, hash_token
from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.governance.models import PowerLevel
from les_slimes.governance.service import GovernanceAdminService
from les_slimes.runtime import ActorPermission, CanonicalRuntime, RuntimeStorage
from les_slimes.world.engine import World


def build_api(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=9901,
                width=30.0,
                height=20.0,
                initial_slimes=5,
                initial_food=6,
                max_food=30,
                food_spawn_probability=0.0,
                tick_duration_seconds=1.0,
            )
        )
    )
    CanonicalRuntime(repo).ensure_initialized(datetime(2026, 9, 17, 12, 0, tzinfo=UTC))
    storage = RuntimeStorage(repo)
    tokens = {
        "father": "creator-test-token",
        "herald": "herald-test-token",
        "order": "order-test-token",
        "chaos": "chaos-test-token",
    }
    authenticator = ActorAuthenticator(
        storage,
        {actor_id: hash_token(token) for actor_id, token in tokens.items()},
    )
    return repo, storage, tokens, TestClient(create_app(repo, authenticator=authenticator))


def auth(token):
    return {"Authorization": f"Bearer {token}"}


def test_public_world_reads_do_not_mutate_canonical_digest(tmp_path):
    repo, _storage, _tokens, client = build_api(tmp_path)
    before = repo.load_world().state_digest()

    health = client.get("/health")
    world = client.get("/world")
    slimes = client.get("/world/slimes")

    assert health.status_code == 200
    assert health.json()["status"] == "ok"
    assert world.status_code == 200
    assert world.json()["state_digest"] == before
    assert slimes.status_code == 200
    assert len(slimes.json()["slimes"]) == 5
    assert repo.load_world().state_digest() == before


def test_bearer_token_resolves_actor_server_side(tmp_path):
    _repo, _storage, tokens, client = build_api(tmp_path)

    response = client.get("/me", headers=auth(tokens["herald"]))

    assert response.status_code == 200
    assert response.json()["id"] == "herald"
    assert response.json()["kind"] == "herald"


def test_missing_and_invalid_credentials_are_rejected(tmp_path):
    _repo, _storage, _tokens, client = build_api(tmp_path)

    assert client.get("/me").status_code == 401
    assert client.get("/me", headers=auth("not-a-token")).status_code == 401


def test_unconfigured_authentication_fails_closed(tmp_path):
    repo, storage, _tokens, _client = build_api(tmp_path)
    client = TestClient(create_app(repo, authenticator=ActorAuthenticator(storage, {})))

    assert client.get("/me", headers=auth("anything")).status_code == 503


def test_client_cannot_inject_actor_id_into_command(tmp_path):
    _repo, storage, tokens, client = build_api(tmp_path)

    response = client.post(
        "/commands",
        headers=auth(tokens["chaos"]),
        json={
            "actor_id": "father",
            "command_type": "deposit_food",
            "payload": {"x": 2.0, "y": 3.0, "count": 1},
            "idempotency_key": "spoofed-father",
        },
    )

    assert response.status_code == 422
    assert storage.pending_commands() == []


def test_command_is_attributed_to_authenticated_actor(tmp_path):
    _repo, storage, tokens, client = build_api(tmp_path)

    response = client.post(
        "/commands",
        headers=auth(tokens["chaos"]),
        json={
            "command_type": "deposit_food",
            "payload": {"x": 2.0, "y": 3.0, "count": 1},
            "idempotency_key": "chaos-api-command",
        },
    )

    assert response.status_code == 201
    assert response.json()["actor_id"] == "chaos"
    pending = storage.pending_commands()
    assert len(pending) == 1
    assert pending[0].actor_id == "chaos"


def test_herald_cannot_use_creator_admin_routes(tmp_path):
    _repo, _storage, tokens, client = build_api(tmp_path)

    response = client.put(
        "/admin/actors/order/permissions",
        headers=auth(tokens["herald"]),
        json={
            "permissions": [ActorPermission.DEPOSIT_FOOD.value],
            "reason": "attempted herald administration",
        },
    )

    assert response.status_code == 403


def test_creator_can_administer_governance_through_trusted_service(tmp_path):
    repo, storage, tokens, client = build_api(tmp_path)

    permission_response = client.put(
        "/admin/actors/order/permissions",
        headers=auth(tokens["father"]),
        json={
            "permissions": [ActorPermission.DEPOSIT_FOOD.value],
            "reason": "creator delegates a test permission",
        },
    )
    power_response = client.put(
        "/admin/actors/order/power",
        headers=auth(tokens["father"]),
        json={"power_level": int(PowerLevel.MIRACLE), "reason": "creator test delegation"},
    )

    assert permission_response.status_code == 200
    assert power_response.status_code == 200
    assert storage.get_actor("order").can(ActorPermission.DEPOSIT_FOOD)
    assert GovernanceAdminService(repo).storage.validate_audit_chain()


def test_journal_and_proposal_are_attributed_to_authenticated_actor(tmp_path):
    repo, _storage, tokens, client = build_api(tmp_path)

    journal = client.post(
        "/journals",
        headers=auth(tokens["herald"]),
        json={"entry_type": "observation", "content": "Message carried by the Herald."},
    )
    proposal = client.post(
        "/proposals",
        headers=auth(tokens["chaos"]),
        json={
            "proposal_type": "experiment_proposal",
            "title": "Explore a controlled variation",
            "payload": {"factor": "food_spawn_probability"},
        },
    )

    assert journal.status_code == 201
    assert journal.json()["actor_id"] == "herald"
    assert proposal.status_code == 201
    assert proposal.json()["actor_id"] == "chaos"

    with repo._connect() as conn:
        journal_actor = conn.execute(
            "SELECT actor_id FROM divine_journal_entries WHERE id = ?",
            (journal.json()["id"],),
        ).fetchone()["actor_id"]
        proposal_actor = conn.execute(
            "SELECT actor_id FROM divine_proposals WHERE id = ?",
            (proposal.json()["id"],),
        ).fetchone()["actor_id"]
    assert journal_actor == "herald"
    assert proposal_actor == "chaos"


def test_inactive_actor_token_is_rejected(tmp_path):
    repo, _storage, tokens, client = build_api(tmp_path)
    GovernanceAdminService(repo).set_active("chaos", False, reason="test suspension")

    response = client.get("/me", headers=auth(tokens["chaos"]))

    assert response.status_code == 403
