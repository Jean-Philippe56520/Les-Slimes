import inspect

import pytest

from les_slimes.divine import (
    CURRENT_READINESS,
    DivineShadowCycleService,
)


class FakeGateway:
    def __init__(self, actor_id="chaos"):
        self.actor_id = actor_id
        self.calls = []

    def identity_status(self, meta):
        self.calls.append(("identity_status", meta))
        return {"identity": self.actor_id, "status": "bound"}

    def laws_main_sha(self, meta):
        self.calls.append(("laws_main_sha", meta))
        return "a" * 40

    def world_observe(self, meta):
        self.calls.append(("world_observe", meta))
        return {"tick": 123, "state_digest": "world-digest"}

    def governance_status(self, meta):
        self.calls.append(("governance_status", meta))
        return {"actors": [{"actor_id": self.actor_id}]}

    def journal_append(self, meta, *, entry_type, content, world_tick=None, context=None):
        self.calls.append(
            ("journal_append", meta, entry_type, content, world_tick, context)
        )
        return {"id": 17, "actor_id": self.actor_id}


META = {"openai/session": "s", "openai/subject": "u"}


def test_shadow_cycle_observes_and_journals_without_execution_surface():
    gateway = FakeGateway("chaos")
    service = DivineShadowCycleService(gateway)

    result = service.run(
        META,
        observation="Diversité mesurée sans intervention.",
        context={"seed_count": 4},
    )

    assert result.actor_id == "chaos"
    assert result.source_main_sha == "a" * 40
    assert result.world_tick == 123
    assert result.world_state_digest == "world-digest"
    assert result.journal_id == 17
    assert result.mode == "shadow"

    call_names = [call[0] for call in gateway.calls]
    assert call_names == [
        "identity_status",
        "laws_main_sha",
        "world_observe",
        "governance_status",
        "journal_append",
    ]
    assert "enqueue_command" not in call_names
    assert "law_submit" not in call_names


def test_shadow_cycle_rejects_non_divine_operational_identity():
    service = DivineShadowCycleService(FakeGateway("father"))
    with pytest.raises(PermissionError, match="ORDER_OR_CHAOS"):
        service.run(META, observation="No execution.")


def test_shadow_cycle_requires_observation():
    service = DivineShadowCycleService(FakeGateway("order"))
    with pytest.raises(ValueError, match="observation"):
        service.run(META, observation="   ")


def test_shadow_service_has_no_promulgation_or_world_command_method():
    names = {name for name, _ in inspect.getmembers(DivineShadowCycleService, inspect.isfunction)}
    assert "promulgate" not in names
    assert "enqueue_command" not in names
    assert "execute" not in names


def test_current_readiness_marks_shadow_ready_but_autonomy_disabled():
    assert CURRENT_READINESS.shadow_ready
    assert not CURRENT_READINESS.production_mcp_adapter
    assert not CURRENT_READINESS.production_providers
    assert not CURRENT_READINESS.canonical_h24_verified
    assert not CURRENT_READINESS.autonomous_scheduling_enabled
    assert not CURRENT_READINESS.autonomous_ready
