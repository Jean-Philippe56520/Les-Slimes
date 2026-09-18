from __future__ import annotations

import inspect

import pytest

from les_slimes.config import WorldConfig
from les_slimes.database.sqlite_repo import SQLiteRepository
from les_slimes.divine import (
    ArchiveItem,
    DivineActorGateway,
    DivineSessionBindingService,
)
from les_slimes.divine.access import (
    CHAOS_PROPOSALS_FOLDER_ID,
    ORDER_PROPOSALS_FOLDER_ID,
)
from les_slimes.world.engine import World


ORDER_META = {
    "openai/session": "order-chat-session",
    "openai/subject": "same-human-subject",
}
CHAOS_META = {
    "openai/session": "chaos-chat-session",
    "openai/subject": "same-human-subject",
}
FATHER_META = {
    "openai/session": "father-chat-session",
    "openai/subject": "same-human-subject",
}


def build_repo(tmp_path):
    repo = SQLiteRepository(tmp_path / "world.sqlite")
    repo.save_world(
        World(
            WorldConfig(
                seed=8113,
                width=20.0,
                height=15.0,
                initial_slimes=4,
                initial_food=5,
                max_food=20,
                food_spawn_probability=0.0,
            )
        )
    )
    sessions = DivineSessionBindingService(repo)
    sessions.bind(
        session_id=ORDER_META["openai/session"],
        subject_id=ORDER_META["openai/subject"],
        actor_id="order",
    )
    sessions.bind(
        session_id=CHAOS_META["openai/session"],
        subject_id=CHAOS_META["openai/subject"],
        actor_id="chaos",
    )
    sessions.bind(
        session_id=FATHER_META["openai/session"],
        subject_id=FATHER_META["openai/subject"],
        actor_id="father",
    )
    return repo


class FakeGitProvider:
    def __init__(self):
        self.calls: list[tuple] = []

    def read_file(self, repository_full_name, path, ref):
        self.calls.append(("read", repository_full_name, path, ref))
        return f"{ref}:{path}"

    def search_code(self, repository_full_name, query):
        self.calls.append(("search", repository_full_name, query))
        return [{"path": "src/les_slimes/world/engine.py", "text": "World"}]

    def get_ref_sha(self, repository_full_name, ref):
        self.calls.append(("sha", repository_full_name, ref))
        return "a" * 40


class FakeArchiveProvider:
    def __init__(self):
        self.calls: list[tuple] = []
        self.search_results: list[ArchiveItem] = []

    def search_descendants(self, root_id, query, *, limit):
        self.calls.append(("search", root_id, query, limit))
        return list(self.search_results)

    def read_text(self, item_id):
        self.calls.append(("read", item_id))
        return f"content:{item_id}"

    def create_text(self, parent_id, *, name, content):
        self.calls.append(("create", parent_id, name, content))
        return ArchiveItem(
            id=f"item-{len(self.calls)}",
            name=name,
            mime_type="text/plain",
            scope_root_id=parent_id,
        )

    def update_text(self, item_id, *, content):
        self.calls.append(("update", item_id, content))


class FakeApiProvider:
    def __init__(self, actor_id):
        self.actor_id = actor_id
        self.calls: list[tuple] = []

    def request(self, method, path, *, body=None, query=None):
        self.calls.append((method, path, body, query))
        return {"actor": self.actor_id, "method": method, "path": path, "body": body}


class FakeApiFactory:
    def __init__(self):
        self.created_for: list[str] = []
        self.providers: dict[str, FakeApiProvider] = {}

    def for_actor(self, actor_id):
        self.created_for.append(actor_id)
        provider = self.providers.get(actor_id)
        if provider is None:
            provider = FakeApiProvider(actor_id)
            self.providers[actor_id] = provider
        return provider


def gateway(tmp_path):
    repo = build_repo(tmp_path)
    git = FakeGitProvider()
    archive = FakeArchiveProvider()
    api_factory = FakeApiFactory()
    return DivineActorGateway(
        repo,
        git_provider=git,
        archive_provider=archive,
        api_provider_factory=api_factory,
    ), git, archive, api_factory


def test_identity_status_uses_session_binding_not_project_name_or_actor_argument(tmp_path):
    g, _git, _archive, _api = gateway(tmp_path)

    order = g.identity_status(ORDER_META)
    chaos = g.identity_status(CHAOS_META)

    assert order["identity"] == "order"
    assert order["proposal_workspace_id"] == ORDER_PROPOSALS_FOLDER_ID
    assert order["git_access"] == "read_only"
    assert chaos["identity"] == "chaos"
    assert chaos["proposal_workspace_id"] == CHAOS_PROPOSALS_FOLDER_ID


def test_actorial_methods_expose_no_actor_id_parameter():
    for method_name in (
        "laws_main_sha",
        "laws_read",
        "laws_search",
        "archives_manifest",
        "archives_search",
        "archives_create_proposal_text",
        "world_observe",
        "world_slimes",
        "world_foods",
        "governance_status",
        "journal_append",
        "proposal_create",
    ):
        signature = inspect.signature(getattr(DivineActorGateway, method_name))
        assert "actor_id" not in signature.parameters


def test_world_provider_is_selected_from_bound_session(tmp_path):
    g, _git, _archive, api = gateway(tmp_path)

    assert g.world_observe(CHAOS_META)["actor"] == "chaos"
    assert g.journal_append(
        ORDER_META,
        entry_type="observation",
        content="Measured continuity.",
    )["actor"] == "order"

    assert api.created_for == ["chaos", "order"]
    assert api.providers["order"].calls[-1][2] == {
        "entry_type": "observation",
        "content": "Measured continuity.",
    }


def test_archive_write_parent_is_derived_from_bound_actor(tmp_path):
    g, _git, archive, _api = gateway(tmp_path)

    g.archives_create_proposal_text(CHAOS_META, name="chaos-law.md", content="patch")
    g.archives_create_proposal_text(ORDER_META, name="order-law.md", content="patch")

    assert ("create", CHAOS_PROPOSALS_FOLDER_ID, "chaos-law.md", "patch") in archive.calls
    assert ("create", ORDER_PROPOSALS_FOLDER_ID, "order-law.md", "patch") in archive.calls


def test_archive_discovery_capability_survives_across_calls(tmp_path):
    g, _git, archive, _api = gateway(tmp_path)
    archive.search_results = [
        ArchiveItem(
            id="chaos-proposal",
            name="proposal.md",
            mime_type="text/plain",
            scope_root_id=CHAOS_PROPOSALS_FOLDER_ID,
        )
    ]

    found = g.archives_search_proposals(CHAOS_META, query="proposal")
    assert found[0].id == "chaos-proposal"
    assert g.archives_read(CHAOS_META, item_id="chaos-proposal") == "content:chaos-proposal"


def test_unbound_or_wrong_subject_fails_before_any_provider_call(tmp_path):
    g, git, archive, api = gateway(tmp_path)

    with pytest.raises(PermissionError, match="UNBOUND"):
        g.laws_main_sha(
            {
                "openai/session": "unknown-session",
                "openai/subject": "same-human-subject",
            }
        )
    with pytest.raises(PermissionError, match="SUBJECT_MISMATCH"):
        g.archives_manifest(
            {
                "openai/session": ORDER_META["openai/session"],
                "openai/subject": "another-subject",
            }
        )

    assert git.calls == []
    assert archive.calls == []
    assert api.created_for == []


def test_missing_openai_metadata_fails_closed(tmp_path):
    g, _git, _archive, _api = gateway(tmp_path)

    with pytest.raises(PermissionError, match="SESSION_METADATA_MISSING"):
        g.identity_status({"openai/subject": "subject"})
    with pytest.raises(PermissionError, match="SUBJECT_METADATA_MISSING"):
        g.identity_status({"openai/session": "session"})


def test_father_binding_is_visible_to_identity_but_not_divine_tool_surface(tmp_path):
    g, git, _archive, _api = gateway(tmp_path)

    assert g.identity_status(FATHER_META)["identity"] == "father"
    with pytest.raises(PermissionError, match="ORDER_OR_CHAOS"):
        g.laws_main_sha(FATHER_META)
    assert git.calls == []
